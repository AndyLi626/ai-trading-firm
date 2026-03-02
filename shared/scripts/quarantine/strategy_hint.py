#!/usr/bin/env python3
import os
"""
strategy_hint.py — 轻量假设生成。
预算 ok → LLM 摘要；degrade → 纯规则；stop → 跳过写 audit。
必须通过 run_with_budget 调用，或内部自检。
Input: reads /tmp/oc_facts/emergency_scan_result.json
Output: /tmp/oc_facts/event_proposals.json (append)
"""
import sys, os, json, uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/scripts'))

FACTS   = "/tmp/oc_facts"
WS = os.path.expanduser('~/.openclaw/workspace')
now_utc = datetime.now(timezone.utc)

# ── Budget gate ───────────────────────────────────────────────────────────────
def budget_mode():
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable,
             os.path.join(WS, "shared/scripts/check_budget_status.py")],
            capture_output=True, text=True, timeout=10
        )
        d = json.loads(r.stdout)
        pct = d.get("bot_daily", {}).get("research", {}).get("pct", 0)
        if pct >= 95: return "stop"
        if pct >= 85: return "degrade"
        return "ok"
    except Exception:
        return "ok"   # fail-open

# ── Rules engine (no LLM) ─────────────────────────────────────────────────────
def rules_hint(symbol, pct_day, sentiment_label):
    direction = "bullish" if (pct_day or 0) > 0 else "bearish"
    if abs(pct_day or 0) >= 3.0:
        strength = "strong"
    elif abs(pct_day or 0) >= 1.5:
        strength = "moderate"
    else:
        strength = "weak"

    action = "monitor"
    if strength in ("strong", "moderate") and direction == "bullish":
        action = "consider_long"
    elif strength in ("strong", "moderate") and direction == "bearish":
        action = "consider_short_or_reduce"

    return {
        "action": action,
        "direction": direction,
        "strength": strength,
        "reason": f"{symbol} pct_day={pct_day:.2f}% ({strength} {direction})",
        "confidence": "low",
        "source": "rules_engine"
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    scan_file = os.path.join(FACTS, "emergency_scan_result.json")
    proposals_file = os.path.join(FACTS, "event_proposals.json")

    if not os.path.exists(scan_file):
        print(json.dumps({"status": "no_scan_result"}))
        return

    scan = json.load(open(scan_file))
    if scan.get("status") != "done":
        print(json.dumps({"status": "scan_not_done"}))
        return

    mode = budget_mode()

    # Budget stop → write audit, skip
    if mode == "stop":
        alerts = json.load(open(f"{FACTS}/ops_alerts.json")) if os.path.exists(f"{FACTS}/ops_alerts.json") else []
        alerts.append({"type": "strategy_hint_budget_stop", "ts": now_utc.isoformat(),
                       "chain_id": scan.get("chain_id")})
        json.dump(alerts, open(f"{FACTS}/ops_alerts.json", "w"), indent=2)
        print(json.dumps({"status": "budget_stop", "mode": mode}))
        return

    proposals = json.load(open(proposals_file)) if os.path.exists(proposals_file) else []
    chain_id  = scan.get("chain_id", str(uuid.uuid4()))

    # Dedup: skip if chain_id already processed
    if any(p.get("chain_id") == chain_id for p in proposals):
        print(json.dumps({"status": "dedup_skip", "chain_id": chain_id}))
        return

    symbols    = scan.get("symbols", [])
    market_data = scan.get("market_data", {})
    quotes     = market_data.get("quotes", {}) if isinstance(market_data, dict) else {}

    new_proposals = []
    tokens_used = 0

    for sym in symbols:
        q = quotes.get(sym, {})
        pct_day = q.get("pct_change_day") or 0
        sentiment = scan.get("sentiment_label", "Neutral")

        if mode == "ok":
            # LLM-based hint (lightweight prompt via exec)
            hint = _llm_hint(sym, pct_day, sentiment, chain_id)
            tokens_used += hint.pop("_tokens", 0)
        else:
            # degrade: pure rules
            hint = rules_hint(sym, pct_day, sentiment)

        proposal = {
            "proposal_id": str(uuid.uuid4()),
            "chain_id":    chain_id,
            "symbol":      sym,
            "hint":        hint,
            "budget_mode": mode,
            "trigger":     scan.get("trigger", "emergency"),
            "created_at":  now_utc.isoformat(),
            "status":      "pending_risk_review"
        }
        new_proposals.append(proposal)

    proposals.extend(new_proposals)
    json.dump(proposals, open(proposals_file, "w"), indent=2)

    # record_run for token accounting
    try:
        from token_meter import record_run
        record_run(str(uuid.uuid4()), "research", "strategy_hint",
                   llm_calls=len([p for p in new_proposals if p["hint"].get("source") != "rules_engine"]),
                   total_input=tokens_used // 2, total_output=tokens_used // 2,
                   duration_sec=0.5, status="ok")
    except Exception:
        pass

    try:
        import sys as _sys; _sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
        from run_registry import registry_set as _rs
        _rs(f"strategy_hint:multi", "ok", f"{len(new_proposals)} proposals")
    except Exception:
        pass
    print(json.dumps({
        "status": "ok",
        "proposals_written": len(new_proposals),
        "chain_id": chain_id,
        "budget_mode": mode,
        "tokens_used": tokens_used
    }))


def _llm_hint(symbol, pct_day, sentiment, chain_id):
    """
    Minimal LLM call via exec. Falls back to rules on error.
    Returns hint dict with optional _tokens field.
    """
    try:
        prompt = (
            f"Symbol {symbol} moved {pct_day:+.2f}% today. "
            f"News sentiment: {sentiment}. "
            "In 1 sentence: what's the most likely interpretation and a candidate action? "
            "Reply as JSON: {\"action\": str, \"reason\": str, \"confidence\": low|medium|high}"
        )
        # Use a local quick exec approach — write prompt to temp, read result
        # This avoids sessions_spawn overhead
        import tempfile, subprocess
        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        tf.write(prompt); tf.close()
        # For now: use rules engine (LLM exec not reliable in script context)
        # TODO P1.5: wire to openclaw sessions_spawn with reference-task
        hint = rules_hint(symbol, pct_day, sentiment)
        hint["source"] = "rules_engine_deferred_llm"
        os.unlink(tf.name)
        return hint
    except Exception:
        return rules_hint(symbol, pct_day, sentiment)


if __name__ == "__main__":
    main()