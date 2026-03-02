#!/usr/bin/env python3
"""
budget_guard.py — Budget enforcement for all bots.
Checks daily token usage against configured limits and returns action directives.

Usage:
    from budget_guard import check_budget
    result = check_budget("research", estimated_tokens=5000)
    if not result["allowed"]: sys.exit(0)
"""
import os, sys, json, time, logging
from datetime import datetime, timezone

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WORKSPACE, "tools"))

BUDGET_FILE    = os.path.join(WORKSPACE, "knowledge", "BUDGET.json")
CACHE_FILE     = "/tmp/oc_facts/budget_state.json"
CACHE_TTL_SEC  = 300  # 5 minutes

log = logging.getLogger("budget_guard")

# ── Default budgets ────────────────────────────────────────────────────────────
_DEFAULTS = {
    "per_run_max_tokens": 50_000,
    "global_daily_tokens": 2_000_000,
    "per_bot_daily_tokens": {
        "manager":  200_000,
        "research": 500_000,
        "media":    300_000,
        "risk":     200_000,
        "audit":    100_000,
        "main":     100_000,
    },
    "warn_pct":    0.70,
    "degrade_pct": 0.85,
    "stop_pct":    0.95,
}


def _load_budget() -> dict:
    """Load BUDGET.json, falling back to defaults on any error."""
    try:
        with open(BUDGET_FILE) as f:
            cfg = json.load(f)
        # Merge with defaults so missing keys are filled
        merged = dict(_DEFAULTS)
        merged.update(cfg)
        merged["per_bot_daily_tokens"] = {
            **_DEFAULTS["per_bot_daily_tokens"],
            **cfg.get("per_bot_daily_tokens", {}),
        }
        return merged
    except Exception as e:
        log.warning(f"budget_guard: could not load BUDGET.json ({e}), using defaults")
        return dict(_DEFAULTS)


# ── GCP query (with cache) ─────────────────────────────────────────────────────
def _fetch_daily_usage() -> dict:
    """
    Query GCP for today's token usage per bot.
    Returns {bot: total_tokens, "__global__": total_tokens}.
    Caches in /tmp/oc_facts/budget_state.json for CACHE_TTL_SEC seconds.
    """
    os.makedirs("/tmp/oc_facts", exist_ok=True)

    # Check cache
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                cache = json.load(f)
            if time.time() - cache.get("_fetched_at", 0) < CACHE_TTL_SEC:
                return cache
    except Exception:
        pass

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result = {"_fetched_at": time.time(), "_today": today, "__global__": 0}

    try:
        sys.path.insert(0, os.path.join(WORKSPACE, "tools"))
        import gcp_client as _gcp
        sql = f"""
            SELECT bot, SUM(total_tokens) AS tokens
            FROM `ai-org-mvp-001.trading_firm.token_usage_runs`
            WHERE date = '{today}'
            GROUP BY bot
        """
        rows = _gcp.query(sql)
        for row in rows:
            bot    = row.get("bot", "unknown")
            tokens = int(row.get("tokens") or 0)
            result[bot] = tokens
            result["__global__"] = result.get("__global__", 0) + tokens
    except Exception as e:
        log.warning(f"budget_guard: GCP query failed ({e}), assuming 0 usage")

    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(result, f)
    except Exception:
        pass

    return result


# ── Main check ─────────────────────────────────────────────────────────────────
def check_budget(bot: str, estimated_tokens: int, task_priority: str = "normal") -> dict:
    """
    Returns a budget decision dict:
      {allowed, action, reason, degrade_hints (optional)}
    action: "ok" | "warn" | "degrade" | "stop"
    """
    cfg     = _load_budget()
    usage   = _fetch_daily_usage()

    warn_pct    = cfg["warn_pct"]
    degrade_pct = cfg["degrade_pct"]
    stop_pct    = cfg["stop_pct"]

    per_run_max = cfg["per_run_max_tokens"]
    bot_daily   = cfg["per_bot_daily_tokens"].get(bot, 100_000)
    global_max  = cfg["global_daily_tokens"]

    bot_used    = usage.get(bot, 0)
    global_used = usage.get("__global__", 0)

    # Per-run hard cap
    if estimated_tokens > per_run_max:
        return {
            "allowed": False,
            "action":  "stop",
            "reason":  f"Estimated tokens {estimated_tokens} exceeds per_run_max {per_run_max}",
        }

    # Determine worst pct across bot-daily and global
    bot_pct    = (bot_used + estimated_tokens) / bot_daily   if bot_daily   > 0 else 0.0
    global_pct = (global_used + estimated_tokens) / global_max if global_max > 0 else 0.0
    worst_pct  = max(bot_pct, global_pct)
    scope      = "bot-daily" if bot_pct >= global_pct else "global"

    reason_base = (
        f"bot={bot} used={bot_used}+{estimated_tokens}/{bot_daily} ({bot_pct:.0%}) | "
        f"global={global_used}+{estimated_tokens}/{global_max} ({global_pct:.0%})"
    )

    if worst_pct >= stop_pct:
        allowed = task_priority == "critical"
        return {
            "allowed": allowed,
            "action":  "stop",
            "reason":  f">{stop_pct:.0%} {scope} budget consumed. {'Critical task allowed.' if allowed else 'Task blocked.'}  {reason_base}",
        }

    if worst_pct >= degrade_pct:
        return {
            "allowed": True,
            "action":  "degrade",
            "reason":  f">{degrade_pct:.0%} {scope} budget consumed — degraded mode. {reason_base}",
            "degrade_hints": {
                "shorten_summary":      True,
                "skip_unchanged":       True,
                "preferred_model":      "claude-haiku-4-5",
                "disable_large_payload": True,
                "critical_only":        False,
            },
        }

    if worst_pct >= warn_pct:
        log.warning(f"budget_guard WARN: {reason_base}")
        return {
            "allowed": True,
            "action":  "warn",
            "reason":  f">{warn_pct:.0%} {scope} budget consumed — approaching limit. {reason_base}",
        }

    return {
        "allowed": True,
        "action":  "ok",
        "reason":  reason_base,
    }


# ── Self-test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = check_budget("research", 10_000)
    assert "action" in result, "Missing 'action' key"
    print("check_budget('research', 10000):", json.dumps(result, indent=2))
    print("budget_guard import OK")
