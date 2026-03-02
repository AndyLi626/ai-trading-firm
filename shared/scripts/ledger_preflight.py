#!/usr/bin/env python3
"""
ledger_preflight.py — proposal 预检。
输入：sys.argv[1] 或 stdin（proposal 文本）
输出：ALREADY_DONE / PARTIAL / NEW_WORK + 证据位置 + 冲突检测
"""
import sys, os, json, re
from datetime import datetime, timezone

WS     = os.path.expanduser("~/.openclaw/workspace")
LEDGER = os.path.join(WS, "ledger")

GOVERNANCE_RULES = [
    (r"delivery\s*[=:]\s*announce", "VIOLATION: delivery must be none for autonomous jobs (ADR-002)"),
    (r"sessions_send",               "VIOLATION: sessions_send not allowed in cron prompts (ACL policy)"),
    (r"agentToAgent\s*:\s*true",     "VIOLATION: agentToAgent:true is invalid in openclaw.json"),
    (r"openclaw\.json.*['\"]w['\"]", "VIOLATION: direct openclaw.json write bypasses config_guard"),
    (r"run_with_budget",             None),  # positive signal — no violation
]

KNOWN_CAPABILITIES = {
    # keyword → (capability_name, status, ledger_ref)
    "market_pulse":        ("market_pulse.py",          "VERIFIED", "ledger/STATUS_MATRIX.md J10/S14"),
    "emergency_trigger":   ("emergency_trigger.py",     "VERIFIED", "ledger/STATUS_MATRIX.md J09/S11"),
    "emergency_scan":      ("emergency_scan.py",        "VERIFIED", "ledger/STATUS_MATRIX.md J09/S12"),
    "anomaly":             ("market_anomaly_detector",  "VERIFIED", "ledger/STATUS_MATRIX.md J11/S16"),
    "anomaly_detector":    ("market_anomaly_detector",  "VERIFIED", "ledger/STATUS_MATRIX.md J11"),
    "budget":              ("run_with_budget.py",       "VERIFIED", "ledger/STATUS_MATRIX.md S17"),
    "run_with_budget":     ("run_with_budget.py",       "VERIFIED", "ledger/STATUS_MATRIX.md S17"),
    "config_guard":        ("config_guard.py",          "VERIFIED", "ledger/STATUS_MATRIX.md S21"),
    "strategy_hint":       ("strategy_hint.py",         "WIRED",    "ledger/STATUS_MATRIX.md S13"),
    "risk_review":         ("risk_review_lite.py",      "WIRED",    "ledger/STATUS_MATRIX.md S14"),
    "collect_media":       ("collect_media.py",         "VERIFIED", "ledger/STATUS_MATRIX.md J02/S24"),
    "collect_market":      ("collect_market.py",        "VERIFIED", "ledger/STATUS_MATRIX.md J03/S22"),
    "token_meter":         ("token_meter.py",           "VERIFIED", "ledger/STATUS_MATRIX.md S18"),
    "token_cost":          ("token_cost_summary.py",    "VERIFIED", "ledger/STATUS_MATRIX.md S18"),
    "detect_changes":      ("detect_changes.py",        "VERIFIED", "ledger/STATUS_MATRIX.md S19"),
    "watchlist":           ("watchlist.json",           "VERIFIED", "shared/config/watchlist.json"),
    "chain_id":            ("chain_id tracing",         "VERIFIED", "ledger/ARCHITECTURE.md"),
    "dedup":               ("dedup in emergency_trigger","VERIFIED","shared/scripts/emergency_trigger.py"),
    "rate_limit":          ("rate_limit in emergency",  "VERIFIED", "shared/scripts/emergency_trigger.py"),
    "media_routing":       ("delivery:none + bot_cache","VERIFIED", "ledger/ADRs/ADR-002-delivery-none.md"),
    "proposal":            ("config_guard proposals",   "VERIFIED", "shared/config_proposals/"),
    "harvest":             ("harvest_openclaw_usage.py","VERIFIED", "ledger/STATUS_MATRIX.md S25"),
    "autonomy_orchestrator":("autonomy_orchestrator.py","WIRED",    "ledger/STATUS_MATRIX.md J06"),
    "infra_scan":          ("infra_scan.py",            "WIRED",    "ledger/STATUS_MATRIX.md J08"),
    "snapshot":            ("snapshot_capabilities.py", "EXISTS",   "shared/scripts/snapshot_capabilities.py"),
}

def preflight(text: str) -> dict:
    text_lower = text.lower()
    violations = []
    matches    = []

    # 1. Governance violations
    for pattern, msg in GOVERNANCE_RULES:
        if msg and re.search(pattern, text, re.IGNORECASE):
            violations.append(msg)

    # 2. Known capability matches
    for kw, (cap, status, ref) in KNOWN_CAPABILITIES.items():
        if kw.lower() in text_lower:
            matches.append({"keyword": kw, "capability": cap,
                            "status": status, "ref": ref})

    # Deduplicate matches by capability
    seen_caps = set()
    unique_matches = []
    for m in matches:
        if m["capability"] not in seen_caps:
            seen_caps.add(m["capability"])
            unique_matches.append(m)

    verified = [m for m in unique_matches if m["status"] == "VERIFIED"]
    wired    = [m for m in unique_matches if m["status"] == "WIRED"]
    new_caps = []

    # 3. Determine verdict
    if violations:
        verdict = "GOVERNANCE_CONFLICT"
    elif len(verified) >= 3 and not wired:
        verdict = "ALREADY_DONE"
    elif verified or wired:
        verdict = "PARTIAL"
    else:
        verdict = "NEW_WORK"

    # 4. Minimum next step
    if verdict == "ALREADY_DONE":
        next_step = "Verify runtime evidence in STATUS_MATRIX.md before rebuilding."
    elif verdict == "PARTIAL":
        done_caps = [m["capability"] for m in verified]
        todo_caps = [m["capability"] for m in wired]
        next_step = (f"Already done: {done_caps}. "
                     f"Wire/verify: {todo_caps if todo_caps else 'check wired items'}.")
    elif verdict == "GOVERNANCE_CONFLICT":
        next_step = f"Fix violations first: {violations}"
    else:
        next_step = "Write proposal in memory/proposals/ with 12-field spec before implementing."

    return {
        "verdict":     verdict,
        "verified":    verified,
        "wired":       wired,
        "violations":  violations,
        "next_step":   next_step,
        "checked_at":  datetime.now(timezone.utc).isoformat()
    }


def main():
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
    else:
        text = sys.stdin.read()

    result = preflight(text)

    # Human-readable output
    icon = {"ALREADY_DONE":"✅","PARTIAL":"🔶","NEW_WORK":"🆕","GOVERNANCE_CONFLICT":"🚫"}.get(result["verdict"],"?")
    print(f"\n{icon} {result['verdict']}\n")

    if result["verified"]:
        print("Already VERIFIED:")
        for m in result["verified"]:
            print(f"  ✅ {m['capability']:35s} → {m['ref']}")
    if result["wired"]:
        print("WIRED (exists but not fully verified):")
        for m in result["wired"]:
            print(f"  🔗 {m['capability']:35s} → {m['ref']}")
    if result["violations"]:
        print("⚠️ Governance conflicts:")
        for v in result["violations"]:
            print(f"  🚫 {v}")
    print(f"\n→ Next step: {result['next_step']}\n")

    # Also write JSON for programmatic use
    print("JSON:" + json.dumps(result))


if __name__ == "__main__":
    main()
