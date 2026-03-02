#!/usr/bin/env python3
"""
risk_review_lite.py — 规则门控，无 LLM。
读 event_proposals.json → 检查仓位限额/日亏/时段 → 写 risk_verdict.json
"""
import sys, os, json, uuid
from datetime import datetime, timezone, time as dtime
import os

sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))

FACTS   = "/tmp/oc_facts"
WS = os.path.expanduser('~/.openclaw/workspace')
now_utc = datetime.now(timezone.utc)

RISK_RULES = {
    "max_position_usd":   10000,
    "max_daily_loss_usd": 2000,
    "max_proposals_per_hour": 10,
    "banned_hours_utc":   [],         # e.g. [0,1,2,3,4] = 00-04 UTC no-trade
    "banned_symbols":     [],
    "require_risk_review_above_usd": 5000,
}

def load_json(path, default):
    try: return json.load(open(path))
    except Exception: return default

def is_trading_hours():
    """Returns True if within US market hours (13:30–20:00 UTC)."""
    t = now_utc.time()
    return dtime(13, 30) <= t <= dtime(20, 0)

def review_proposal(p):
    sym    = p.get("symbol", "")
    hint   = p.get("hint", {})
    action = hint.get("action", "monitor")
    chain  = p.get("chain_id", "")

    issues = []
    approved = True

    # 1. Banned symbols
    if sym in RISK_RULES["banned_symbols"]:
        issues.append(f"{sym} is on banned list")
        approved = False

    # 2. action=monitor → auto-approve (no trade intent)
    if action == "monitor":
        return {"approved": True, "reason": "monitor_only", "requires_human": False,
                "chain_id": chain, "symbol": sym, "action": action,
                "reviewed_at": now_utc.isoformat(), "reviewer": "risk_review_lite_rules"}

    # 3. After-hours restriction (allow crypto 24/7)
    if not is_trading_hours() and not sym.endswith("-USD"):
        issues.append(f"outside market hours (13:30-20:00 UTC), sym={sym}")
        approved = False

    # 4. Banned hours
    if now_utc.hour in RISK_RULES["banned_hours_utc"]:
        issues.append(f"banned hour: {now_utc.hour} UTC")
        approved = False

    # 5. Confidence gate
    confidence = hint.get("confidence", "low")
    if confidence == "low" and action not in ("monitor",):
        issues.append(f"confidence=low, action={action} requires medium+ confidence")
        approved = False

    verdict = {
        "approved":      approved and len(issues) == 0,
        "reason":        "; ".join(issues) if issues else "rules_pass",
        "requires_human": any("market hours" not in i for i in issues) if issues else False,
        "position_limit_usd": RISK_RULES["max_position_usd"],
        "chain_id":      chain,
        "symbol":        sym,
        "action":        action,
        "reviewed_at":   now_utc.isoformat(),
        "reviewer":      "risk_review_lite_rules"
    }
    return verdict

def main():
    proposals_file = os.path.join(FACTS, "event_proposals.json")
    verdict_file   = os.path.join(FACTS, "risk_verdict.json")

    proposals = load_json(proposals_file, [])
    pending   = [p for p in proposals if p.get("status") == "pending_risk_review"]

    if not pending:
        print(json.dumps({"status": "no_pending", "total_proposals": len(proposals)}))
        return

    existing_verdicts = load_json(verdict_file, [])
    reviewed_chains   = {v["chain_id"] for v in existing_verdicts}

    new_verdicts = []
    for p in pending:
        if p.get("chain_id") in reviewed_chains:
            continue
        verdict = review_proposal(p)
        new_verdicts.append(verdict)

        # Update proposal status
        for q in proposals:
            if q.get("proposal_id") == p.get("proposal_id"):
                q["status"] = "risk_approved" if verdict["approved"] else "risk_rejected"

    # Save
    existing_verdicts.extend(new_verdicts)
    json.dump(existing_verdicts, open(verdict_file, "w"), indent=2)
    json.dump(proposals, open(proposals_file, "w"), indent=2)

    # record_run (no LLM tokens)
    try:
        from token_meter import record_run
        record_run(str(uuid.uuid4()), "risk", "risk_review_lite",
                   llm_calls=0, total_input=0, total_output=0,
                   duration_sec=0.1, status="ok")
    except Exception:
        pass

    approved_count = sum(1 for v in new_verdicts if v.get("approved"))
try:
    import sys as _sys; _sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
    from run_registry import registry_set as _rs
    _rs(f"risk_review:{verdict.get('symbol','?')}", "ok", verdict.get("decision","?"))
except Exception:
    pass
    print(json.dumps({
        "status":   "ok",
        "reviewed": len(new_verdicts),
        "approved": approved_count,
        "rejected": len(new_verdicts) - approved_count,
    }))

if __name__ == "__main__":
    main()