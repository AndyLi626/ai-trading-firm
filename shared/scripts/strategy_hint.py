#!/usr/bin/env python3
"""
strategy_hint.py — P1.5 이벤트 트리거 LLM 접목
트리거: anomaly_detector / market_pulse 이상 / emergency_requests
budget ok → LLM 분석; degrade → 규칙 엔진; stop → 규칙만, 0 tokens

Input:  /tmp/oc_facts/emergency_scan_result.json
        /tmp/oc_facts/anomaly_events.json
        memory/market/MARKET_PULSE.json (고정 경로)
Output: /tmp/oc_facts/event_proposals.json (append, risk_gate=pending)
"""
import sys, os, json, uuid, subprocess
from datetime import datetime, timezone

sys.path.insert(0, "/home/lishopping913/.openclaw/workspace/shared/tools")
sys.path.insert(0, "/home/lishopping913/.openclaw/workspace/shared/scripts")

WS      = "/home/lishopping913/.openclaw/workspace"
FACTS   = "/tmp/oc_facts"
now_utc = datetime.now(timezone.utc)


# ── Budget gate ───────────────────────────────────────────────────────────────
def _budget_mode() -> str:
    """ok / degrade / stop"""
    try:
        import budget_guard as bg
        r = bg.check_budget("research", 2000)
        return r.get("action", "ok")
    except Exception:
        return "ok"


# ── Rules engine (no LLM, deterministic) ─────────────────────────────────────
def _rules_hint(symbol: str, pct_day: float, sentiment: str) -> dict:
    if pct_day > 1.5:
        action, conf = "long_bias", "medium"
    elif pct_day < -1.5:
        action, conf = "short_bias", "medium"
    else:
        action, conf = "hold", "low"
    if sentiment == "Bearish" and action == "long_bias":
        action, conf = "hold", "low"
    return {"action": action, "reason": f"pct_day={pct_day:+.2f}% sentiment={sentiment}",
            "confidence": conf, "source": "rules_engine"}


# ── LLM hint (Anthropic claude-haiku, lightweight) ───────────────────────────
def _llm_hint(symbol: str, pct_day: float, sentiment: str,
              chain_id: str, tier: str) -> dict:
    """
    tier=0 → claude-haiku-4-5 (빠름)
    tier=1 → claude-sonnet-4-6 (정확)
    """
    model = "anthropic/claude-sonnet-4-6" if tier == "1" else "anthropic/claude-haiku-4-5"
    key_path = os.path.expanduser("~/.openclaw/secrets/anthropic_api_key.txt")
    try:
        import urllib.request
        api_key = open(key_path).read().strip()
        prompt  = (
            f"Symbol {symbol} moved {pct_day:+.2f}% today. "
            f"Sentiment: {sentiment}. chain_id={chain_id}. "
            "Reply JSON only: {\"action\":\"long|short|hold\","
            "\"reason\":\"<1 sentence>\",\"confidence\":\"low|medium|high\"}"
        )
        body = json.dumps({
            "model":      model.split("/")[-1],
            "max_tokens": 80,
            "messages":   [{"role": "user", "content": prompt}]
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"x-api-key": api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"}
        )
        r    = json.loads(urllib.request.urlopen(req, timeout=10).read())
        text = r["content"][0]["text"].strip()
        hint = json.loads(text)
        hint["source"]   = f"llm:{model.split('/')[-1]}"
        hint["_tokens"]  = r.get("usage", {}).get("input_tokens", 0) + \
                           r.get("usage", {}).get("output_tokens", 0)
        hint["chain_id"] = chain_id
        return hint
    except Exception as e:
        h = _rules_hint(symbol, pct_day, sentiment)
        h["source"]      = f"rules_fallback (llm_error: {str(e)[:40]})"
        h["chain_id"]    = chain_id
        return h


# ── RiskLite gate ─────────────────────────────────────────────────────────────
def _risk_gate(proposal: dict) -> dict:
    """risk_review_lite.py 통과 여부 확인"""
    try:
        r = subprocess.run(
            [sys.executable,
             os.path.join(WS, "shared/scripts/risk_review_lite.py")],
            input=json.dumps(proposal), capture_output=True,
            text=True, timeout=15
        )
        if r.returncode == 0:
            verdict = json.loads(r.stdout).get("verdict", "REJECT")
            return {"risk_gate": verdict.lower(), "risk_detail": verdict}
        return {"risk_gate": "pending", "risk_detail": "risk_script_error"}
    except Exception as e:
        return {"risk_gate": "pending", "risk_detail": f"exception:{str(e)[:40]}"}


# ── 트리거 감지 ───────────────────────────────────────────────────────────────
def _detect_trigger() -> tuple[str, dict]:
    """(trigger_type, scan_data) 반환"""
    # 1. emergency_scan_result
    try:
        scan = json.load(open(f"{FACTS}/emergency_scan_result.json"))
        if scan.get("triggered") or scan.get("alerts"):
            return "emergency", scan
    except Exception:
        pass

    # 2. anomaly_events
    try:
        events = json.load(open(f"{FACTS}/anomaly_events.json"))
        if isinstance(events, list) and events:
            latest = events[-1]
            if latest.get("severity") in ("tier0", "tier1", "Tier0", "Tier1"):
                return "anomaly", {"chain_id": latest.get("chain_id"), "anomaly": latest}
    except Exception:
        pass

    # 3. market_pulse 이상 (±1% 이상)
    try:
        for mp_path in [
            f"{WS}/memory/market/MARKET_PULSE.json",
            f"{FACTS}/MARKET_PULSE.json",
        ]:
            if not os.path.exists(mp_path):
                continue
            mp = json.load(open(mp_path))
            movers = [q for q in mp.get("quotes", {}).values()
                      if abs(q.get("pct_change_day") or 0) > 1.0]
            if movers:
                return "market_pulse", {"quotes": mp.get("quotes", {}),
                                        "chain_id": mp.get("run_id"),
                                        "trigger": "market_pulse"}
    except Exception:
        pass

    return "none", {}


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    trigger, scan = _detect_trigger()

    if trigger == "none":
        print(json.dumps({"status": "no_trigger", "proposals_written": 0}))
        return

    mode      = _budget_mode()
    chain_id  = scan.get("chain_id") or str(uuid.uuid4())
    quotes    = scan.get("quotes") or {}
    sentiment = scan.get("sentiment_label", "Neutral")

    # budget stop → 규칙 엔진만 (0 tokens)
    if mode == "stop":
        mode = "degrade"

    proposals_file = f"{FACTS}/event_proposals.json"
    try:
        proposals = json.load(open(proposals_file))
    except Exception:
        proposals = []

    # dedup
    if any(p.get("chain_id") == chain_id for p in proposals):
        print(json.dumps({"status": "dedup_skip", "chain_id": chain_id}))
        return

    # tier 결정 (anomaly tier0/tier1 → sonnet)
    anomaly = scan.get("anomaly", {})
    tier    = "1" if anomaly.get("severity", "").lower() in ("tier0","tier1") else "0"

    new_proposals = []
    tokens_used   = 0
    symbols       = list(quotes.keys()) or ["SPY"]

    for sym in symbols:
        q       = quotes.get(sym, {})
        pct_day = q.get("pct_change_day") or 0

        if mode == "ok":
            hint = _llm_hint(sym, pct_day, sentiment, chain_id, tier)
            tokens_used += hint.pop("_tokens", 0)
        else:
            hint = _rules_hint(sym, pct_day, sentiment)
            hint["chain_id"] = chain_id

        proposal = {
            "proposal_id":  str(uuid.uuid4()),
            "chain_id":     chain_id,
            "symbol":       sym,
            "hint":         hint,
            "budget_mode":  mode,
            "trigger":      trigger,
            "created_at":   now_utc.isoformat(),
            "status":       "pending_risk_review",
            "risk_gate":    "pending",
            "sources": [
                f"MARKET_PULSE.json:as_of={scan.get('as_of_utc',now_utc.isoformat()[:16])}",
                f"trigger={trigger}:chain_id={chain_id}",
            ]
        }

        # RiskLite gate
        risk = _risk_gate(proposal)
        proposal.update(risk)
        new_proposals.append(proposal)

    proposals.extend(new_proposals)
    os.makedirs(FACTS, exist_ok=True)
    json.dump(proposals, open(proposals_file, "w"), indent=2)

    # token accounting
    try:
        from token_meter import record_run
        record_run(str(uuid.uuid4()), "research", "strategy_hint",
                   llm_calls=len([p for p in new_proposals
                                  if "llm:" in p["hint"].get("source","")]),
                   total_input=tokens_used // 2, total_output=tokens_used // 2,
                   duration_sec=0.5, status="ok")
    except Exception:
        pass

    result = {
        "status":            "ok",
        "trigger":           trigger,
        "chain_id":          chain_id,
        "proposals_written": len(new_proposals),
        "budget_mode":       mode,
        "tokens_used":       tokens_used,
        "risk_gates":        [p["risk_gate"] for p in new_proposals],
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
