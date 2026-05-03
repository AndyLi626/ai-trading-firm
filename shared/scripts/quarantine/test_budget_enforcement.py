#!/usr/bin/env python3
"""
test_budget_enforcement.py — Simulate all 3 budget thresholds.

Tests stop (95%), degrade (85%), warn (70%) by temporarily lowering manager daily budget.
Restores original budget after all tests.
All GCP writes use is_test=True.
"""
import os, sys, json, uuid, subprocess, time
from datetime import datetime, timezone

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
BUDGET_FILE = os.path.join(WORKSPACE, "shared", "knowledge", "BUDGET.json")
CACHE_FILE  = "/tmp/oc_facts/budget_state.json"
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "tools"))

RUN_BUDGET_SCRIPT = os.path.join(WORKSPACE, "shared", "scripts", "run_with_budget.py")


def _load_budget():
    with open(BUDGET_FILE) as f:
        return json.load(f)


def _save_budget(cfg):
    with open(BUDGET_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def _set_manager_budget(tokens: int):
    cfg = _load_budget()
    cfg["per_bot_daily_tokens"]["manager"] = tokens
    _save_budget(cfg)
    # Invalidate cache
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)


def _get_manager_today_tokens() -> int:
    try:
        import gcp_client as g
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows  = g.query(
            f"SELECT SUM(total_tokens) AS t FROM `example-gcp-project.trading_firm.token_usage_runs`"
            f" WHERE bot='manager' AND date='{today}' AND (is_test IS NULL OR is_test=FALSE)"
        )
        return int((rows[0].get("t") or 0) if rows else 0)
    except Exception:
        return 0


def _write_test_event(threshold: str, action: str, budget: int):
    try:
        import gcp_client as g
        today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        run_id = str(uuid.uuid4())
        g.insert_rows("token_usage_runs", [{
            "run_id":              run_id,
            "bot":                 "manager",
            "task_type":           f"budget_test_{threshold}",
            "llm_calls":           0,
            "total_input_tokens":  0,
            "total_output_tokens": 0,
            "total_tokens":        0,
            "duration_sec":        0,
            "status":              f"budget_{action}",
            "date":                today,
            "usage_source":        "estimated",
            "record_source":       "test",
            "is_test":             True,
        }])
        return run_id
    except Exception as e:
        print(f"  [test] GCP write failed: {e}", file=sys.stderr)
        return None


def _run_budget_check(estimated_tokens: int) -> dict:
    """Call run_with_budget.py and capture output + exit code."""
    proc = subprocess.run(
        [sys.executable, RUN_BUDGET_SCRIPT, "manager", "manager_report", str(estimated_tokens)],
        capture_output=True, text=True, timeout=60
    )
    try:
        result = json.loads(proc.stdout.strip())
    except Exception:
        result = {"raw": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    result["_exit_code"] = proc.returncode
    return result


def main():
    print("=" * 60)
    print("Budget Enforcement Threshold Tests")
    print("=" * 60)

    # Save original budget
    original_cfg = _load_budget()
    original_manager_budget = original_cfg.get("per_bot_daily_tokens", {}).get("manager", 200000)
    print(f"Original manager budget: {original_manager_budget:,} tokens\n")

    # Get actual today usage for manager
    today_used = _get_manager_today_tokens()
    print(f"Manager tokens used today (real): {today_used:,}\n")

    tests = [
        {"name": "stop",    "threshold": "95%", "budget": max(int(today_used / 0.96) + 1, 100),  "expected_action": "stop"},
        {"name": "degrade", "threshold": "85%", "budget": max(int(today_used / 0.86) + 1, 500),  "expected_action": "degrade"},
        {"name": "warn",    "threshold": "70%", "budget": max(int(today_used / 0.71) + 1, 1000), "expected_action": "warn"},
    ]

    all_passed = True
    results = []

    for t in tests:
        print(f"--- Test: {t['threshold']} ({t['name'].upper()}) ---")
        _set_manager_budget(t["budget"])
        print(f"  Temp budget set to: {t['budget']:,} tokens")
        print(f"  Usage ratio:        {today_used}/{t['budget']} = {today_used/t['budget']:.1%}")

        result = _run_budget_check(estimated_tokens=100)
        action    = result.get("action", "unknown")
        exit_code = result.get("_exit_code", -1)
        passed    = action == t["expected_action"]

        print(f"  Expected action:    {t['expected_action']}")
        print(f"  Actual action:      {action}")
        print(f"  Exit code:          {exit_code}")
        print(f"  Result:             {'✅ PASS' if passed else '❌ FAIL'}")

        # Write GCP test record
        gcp_run_id = _write_test_event(t["name"], action, t["budget"])
        if gcp_run_id:
            print(f"  GCP test record:    {gcp_run_id}")

        if not passed:
            all_passed = False
            print(f"  WARNING: expected {t['expected_action']} but got {action}")

        results.append({
            "test":            t["name"],
            "threshold":       t["threshold"],
            "temp_budget":     t["budget"],
            "today_used":      today_used,
            "expected_action": t["expected_action"],
            "actual_action":   action,
            "exit_code":       exit_code,
            "passed":          passed,
        })
        print()

    # Restore original budget
    _set_manager_budget(original_manager_budget)
    print(f"✅ Original budget restored: {original_manager_budget:,} tokens")
    print()
    print("=" * 60)
    print(f"Final: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")
    print("=" * 60)
    print(json.dumps({"tests": results, "all_passed": all_passed}, indent=2))


if __name__ == "__main__":
    main()
