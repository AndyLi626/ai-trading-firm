#!/usr/bin/env python3
"""
run_with_budget.py — Budget enforcer wrapper for bot cron runs.

Usage:
  python3 run_with_budget.py <bot_id> <task_type> <estimated_tokens>

Output JSON: {allowed, action, budget_mode, today_total, degrade_hints}
Exit code: 0=allowed, 1=hard_stop
"""
import os, sys, json, uuid, subprocess
from datetime import datetime, timezone

WORKSPACE = "/home/lishopping913/.openclaw/workspace"
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "tools"))

HARVEST_SCRIPT = os.path.join(WORKSPACE, "shared", "scripts", "harvest_openclaw_usage.py")


def _run_harvest_quick():
    try:
        result = subprocess.run(
            [sys.executable, HARVEST_SCRIPT, "--hours", "2"],
            capture_output=True, text=True, timeout=30
        )
        for line in reversed(result.stdout.strip().splitlines()):
            try:
                return json.loads(line)
            except Exception:
                continue
    except Exception:
        pass
    return {}


def _write_audit_event(bot: str, task_type: str, status: str, estimated_tokens: int, is_test: bool = False):
    try:
        import gcp_client as g
        run_id = str(uuid.uuid4())
        today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        g.insert_rows("token_usage_runs", [{
            "run_id":              run_id,
            "bot":                 bot,
            "task_type":           task_type,
            "llm_calls":           0,
            "total_input_tokens":  0,
            "total_output_tokens": 0,
            "total_tokens":        estimated_tokens,
            "duration_sec":        0,
            "status":              status,
            "date":                today,
            "usage_source":        "estimated",
            "record_source":       "budget_guard",
            "is_test":             is_test,
        }])
    except Exception as e:
        print(f"[run_with_budget] audit write failed: {e}", file=sys.stderr)


def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Usage: run_with_budget.py <bot_id> <task_type> <estimated_tokens>"}))
        sys.exit(1)

    bot_id           = sys.argv[1]
    task_type        = sys.argv[2]
    estimated_tokens = int(sys.argv[3])

    # Step 1: quick harvest for fresh data
    _run_harvest_quick()

    # Invalidate budget cache so we get fresh data
    cache_file = "/tmp/oc_facts/budget_state.json"
    if os.path.exists(cache_file):
        os.remove(cache_file)

    # Step 2: check budget
    try:
        import budget_guard as bg
        result = bg.check_budget(bot_id, estimated_tokens)
    except Exception as e:
        print(json.dumps({"error": str(e), "allowed": True, "action": "ok"}))
        sys.exit(0)

    # Fetch today_total for output
    today_total = 0
    try:
        import gcp_client as g
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows  = g.query(f"SELECT SUM(total_tokens) AS t FROM `ai-org-mvp-001.trading_firm.token_usage_runs` WHERE bot='{bot_id}' AND date='{today}'")
        today_total = int((rows[0].get("t") or 0) if rows else 0)
    except Exception:
        pass

    action = result.get("action", "ok")
    output = {
        "allowed":      result.get("allowed", True),
        "action":       action,
        "budget_mode":  action,
        "today_total":  today_total,
        "reason":       result.get("reason", ""),
        "degrade_hints": result.get("degrade_hints", {}),
    }

    # Step 3: write audit event for stop/degrade
    if action == "stop":
        _write_audit_event(bot_id, task_type, "budget_stop", estimated_tokens)
    elif action == "degrade":
        _write_audit_event(bot_id, task_type, "budget_degrade", estimated_tokens)

    print(json.dumps(output))
    sys.exit(0 if result.get("allowed", True) else 1)


if __name__ == "__main__":
    main()
