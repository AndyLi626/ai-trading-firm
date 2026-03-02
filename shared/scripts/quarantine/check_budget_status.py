#!/usr/bin/env python3
"""
check_budget_status.py — Budget status wrapper for cron prompts.

1. Harvests recent usage (last 2h) from cron/runs/ into GCP
2. Calls budget_guard.check_budget("manager", estimated_tokens=5000)
3. Outputs JSON with all 4 budget levels

Output:
{
  "message_level": {...},
  "run_level": {...},
  "bot_daily": {"manager": {...}, ...},
  "global": {...},
  "action": "ok|warn|degrade|stop",
  "degrade_hints": {...}
}
"""
import os, sys, json, subprocess
from datetime import datetime, timezone

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "tools"))

HARVEST_SCRIPT = os.path.join(WORKSPACE, "shared", "scripts", "harvest_openclaw_usage.py")

BUDGET_FILE = os.path.join(WORKSPACE, "shared", "knowledge", "BUDGET.json")


def _load_budget() -> dict:
    try:
        with open(BUDGET_FILE) as f:
            return json.load(f)
    except Exception:
        return {
            "per_bot_daily_tokens": {"manager": 200000, "research": 500000,
                                     "media": 300000, "risk": 200000,
                                     "audit": 100000, "main": 100000},
            "global_daily_tokens": 2_000_000,
        }


def _run_harvest_quick():
    """Run harvester for last 2h only (quick mode)."""
    try:
        result = subprocess.run(
            [sys.executable, HARVEST_SCRIPT, "--hours", "2"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            # parse last JSON line from stdout
            for line in reversed(result.stdout.strip().splitlines()):
                try:
                    return json.loads(line)
                except Exception:
                    continue
    except Exception as e:
        pass
    return {"harvested": 0, "errors": 1}


def _query_today_per_bot() -> dict:
    """Query token_usage_runs for today's totals per bot."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = {}
    try:
        import gcp_client as _gcp
        # Try new table first
        sql = f"""
            SELECT bot, SUM(total_tokens) AS tokens
            FROM `ai-org-mvp-001.trading_firm.token_usage_runs`
            WHERE date = '{today}' AND (is_test IS NULL OR is_test = FALSE)
                  AND (record_source IS NULL OR record_source != 'test')
            GROUP BY bot
        """
        rows = _gcp.query(sql)
        for row in rows:
            result[row.get("bot", "unknown")] = int(row.get("tokens") or 0)

        # If new table empty, fall back to legacy token_usage
        if not result:
            sql_legacy = f"""
                SELECT bot, SUM(total_tokens) AS tokens
                FROM `ai-org-mvp-001.trading_firm.token_usage`
                WHERE DATE(SAFE.PARSE_TIMESTAMP('%s', SAFE_CAST(timestamp AS STRING))) = '{today}'
                   OR DATE(timestamp) = '{today}'
                GROUP BY bot
            """
            try:
                rows2 = _gcp.query(sql_legacy)
                for row in rows2:
                    result[row.get("bot", "unknown")] = int(row.get("tokens") or 0)
            except Exception:
                pass
    except Exception as e:
        pass
    return result


def _classify(used: int, budget: int, pcts: dict) -> str:
    if budget <= 0:
        return "ok"
    pct = used / budget
    if pct >= pcts["stop"]:    return "stop"
    if pct >= pcts["degrade"]: return "degrade"
    if pct >= pcts["warn"]:    return "warn"
    return "ok"


def main():
    # Step 1: quick harvest
    harvest_result = _run_harvest_quick()

    # Step 2: load budget config
    budget_cfg = _load_budget()
    bot_budgets = budget_cfg.get("per_bot_daily_tokens", {})
    global_budget = budget_cfg.get("global_daily_tokens", 2_000_000)
    pcts = {
        "warn":    budget_cfg.get("warn_pct",    0.70),
        "degrade": budget_cfg.get("degrade_pct", 0.85),
        "stop":    budget_cfg.get("stop_pct",    0.95),
    }

    # Step 3: query today's usage
    usage_per_bot = _query_today_per_bot()
    global_total  = sum(usage_per_bot.values())

    # Step 4: build bot_daily breakdown
    all_bots = set(list(bot_budgets.keys()) + list(usage_per_bot.keys()))
    bot_daily = {}
    for bot in sorted(all_bots):
        today_total = usage_per_bot.get(bot, 0)
        budget      = bot_budgets.get(bot, 100_000)
        pct         = round(today_total / budget * 100, 1) if budget > 0 else 0.0
        mode        = _classify(today_total, budget, pcts)
        bot_daily[bot] = {
            "today_total":  today_total,
            "budget":       budget,
            "pct":          pct,
            "budget_mode":  mode,
        }

    # Step 5: global budget
    global_pct  = round(global_total / global_budget * 100, 1) if global_budget > 0 else 0.0
    global_mode = _classify(global_total, global_budget, pcts)

    # Step 6: call budget_guard for authoritative action
    try:
        import budget_guard as bg
        guard_result = bg.check_budget("manager", estimated_tokens=5000)
        action        = guard_result.get("action", "ok")
        degrade_hints = guard_result.get("degrade_hints", {})
    except Exception as e:
        # Fallback: compute action from worst bot/global mode
        all_modes   = [v["budget_mode"] for v in bot_daily.values()] + [global_mode]
        mode_rank   = ["ok", "warn", "degrade", "stop"]
        action      = max(all_modes, key=lambda m: mode_rank.index(m) if m in mode_rank else 0)
        degrade_hints = {}

    output = {
        "message_level": {
            "context_used":  None,
            "context_limit": 200_000,
            "note":          "not_available_from_script",
        },
        "run_level": {
            "estimated_input": 5000,
            "usage_source":    "estimated",
        },
        "bot_daily":    bot_daily,
        "global": {
            "system_today_total": global_total,
            "global_budget":      global_budget,
            "pct":                global_pct,
            "budget_mode":        global_mode,
        },
        "action":        action,
        "degrade_hints": degrade_hints,
        "harvest_result": harvest_result,
    }

    print(json.dumps(output, indent=2))
    return output


if __name__ == "__main__":
    main()
