#!/usr/bin/env python3
"""
daily_usage_report.py — Query GCP for today's token usage and produce a report.
Output: runtime_state/usage_report_YYYY-MM-DD.json + human-readable summary.
"""
import os, sys, json
from datetime import datetime, timezone

WORKSPACE = "/home/lishopping913/.openclaw/workspace"
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "tools"))
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "knowledge"))

OUTPUT_DIR = os.path.join(WORKSPACE, "runtime_state")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BUDGET_FILE = os.path.join(WORKSPACE, "shared", "knowledge", "BUDGET.json")

# ── Cost rates (per 1M tokens) ─────────────────────────────────────────────────
COST_RATES = {
    "sonnet":       {"input": 3.00,  "output": 15.00},
    "haiku":        {"input": 0.25,  "output": 1.25},
    "gemini-flash": {"input": 0.15,  "output": 0.60},
    "default":      {"input": 3.00,  "output": 15.00},
}

def _model_rate(model: str) -> dict:
    m = (model or "").lower()
    if "haiku" in m:      return COST_RATES["haiku"]
    if "gemini" in m and "flash" in m: return COST_RATES["gemini-flash"]
    return COST_RATES["sonnet"]


def _load_budget() -> dict:
    try:
        with open(BUDGET_FILE) as f:
            return json.load(f)
    except Exception:
        return {
            "per_bot_daily_tokens": {},
            "global_daily_tokens": 2_000_000,
        }


def run_report(gcp_query_fn=None):
    """
    Main report function. Accepts optional gcp_query_fn for testing (mocking).
    Returns (report_dict, summary_str).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    budget = _load_budget()
    bot_budgets = budget.get("per_bot_daily_tokens", {})
    global_max  = budget.get("global_daily_tokens", 2_000_000)

    # ── Query GCP ──────────────────────────────────────────────────────────────
    if gcp_query_fn is None:
        try:
            import gcp_client as _gcp
            _raw_query = _gcp.query
            def gcp_query_fn(sql):
                try:
                    return _raw_query(sql)
                except Exception as e:
                    print(f"[daily_usage_report] GCP query error: {e}")
                    return []
        except Exception as e:
            gcp_query_fn = lambda sql: []
            print(f"[daily_usage_report] GCP unavailable: {e}")

    # Per-bot totals — use query_usage_today helper (handles legacy table fallback)
    try:
        import gcp_client as _gcp_helper
        _usage_today_rows = _gcp_helper.query_usage_today()
        # Reformat to match expected schema
        _usage_map = {r.get("bot"): r for r in _usage_today_rows}
    except Exception:
        _usage_map = {}

    sql_bots = f"""
        SELECT bot,
               SUM(total_input_tokens)  AS input_tokens,
               SUM(total_output_tokens) AS output_tokens,
               SUM(total_tokens)        AS total_tokens,
               COUNT(*)                 AS run_count
        FROM `ai-org-mvp-001.trading_firm.token_usage_runs`
        WHERE date = '{today}'
          AND (is_test IS NULL OR is_test = FALSE)
          AND (record_source IS NULL OR record_source = 'runtime')
        GROUP BY bot
        ORDER BY total_tokens DESC
    """
    bot_rows = gcp_query_fn(sql_bots)

    # Top task_types
    sql_tasks = f"""
        SELECT task_type, SUM(total_tokens) AS tokens, COUNT(*) AS runs
        FROM `ai-org-mvp-001.trading_firm.token_usage_runs`
        WHERE date = '{today}'
          AND (is_test IS NULL OR is_test = FALSE)
          AND (record_source IS NULL OR record_source = 'runtime')
        GROUP BY task_type
        ORDER BY tokens DESC
        LIMIT 5
    """
    task_rows = gcp_query_fn(sql_tasks)

    # Waste candidates: high-token no-op runs
    sql_waste = f"""
        SELECT run_id, bot, task_type, total_tokens, status, duration_sec
        FROM `ai-org-mvp-001.trading_firm.token_usage_runs`
        WHERE date = '{today}'
          AND total_tokens > 5000
          AND (is_test IS NULL OR is_test = FALSE)
          AND (status = 'no_op' OR status = 'minimal')
        ORDER BY total_tokens DESC
        LIMIT 3
    """
    waste_rows = gcp_query_fn(sql_waste)

    # ── Compute per-bot cost ───────────────────────────────────────────────────
    # Cost approximation from call-level data (has model info)
    sql_cost = f"""
        SELECT model,
               SUM(input_tokens)  AS inp,
               SUM(output_tokens) AS out
        FROM `ai-org-mvp-001.trading_firm.token_usage_calls`
        WHERE DATE(started_at) = '{today}'
        GROUP BY model
    """
    cost_rows = gcp_query_fn(sql_cost)
    estimated_cost_usd = 0.0
    for cr in cost_rows:
        rate = _model_rate(cr.get("model", ""))
        inp  = int(cr.get("inp") or 0)
        out  = int(cr.get("out") or 0)
        estimated_cost_usd += (inp * rate["input"] + out * rate["output"]) / 1_000_000

    # ── Build report dict ──────────────────────────────────────────────────────
    global_total = sum(int(r.get("total_tokens") or 0) for r in bot_rows)
    global_pct   = round(global_total / global_max * 100, 1) if global_max > 0 else 0

    bots_report = []
    for r in bot_rows:
        bot   = r.get("bot", "unknown")
        total = int(r.get("total_tokens") or 0)
        limit = bot_budgets.get(bot, 100_000)
        pct   = round(total / limit * 100, 1) if limit > 0 else 0
        bots_report.append({
            "bot":           bot,
            "total_tokens":  total,
            "input_tokens":  int(r.get("input_tokens") or 0),
            "output_tokens": int(r.get("output_tokens") or 0),
            "run_count":     int(r.get("run_count") or 0),
            "daily_budget":  limit,
            "pct_used":      pct,
        })

    report = {
        "date":            today,
        "generated_at":    datetime.now(timezone.utc).isoformat(),
        "global": {
            "total_tokens": global_total,
            "daily_budget": global_max,
            "pct_used":     global_pct,
        },
        "estimated_cost_usd": round(estimated_cost_usd, 4),
        "bots":             bots_report,
        "top_task_types":   [
            {"task_type": r.get("task_type",""), "tokens": int(r.get("tokens") or 0), "runs": int(r.get("runs") or 0)}
            for r in task_rows
        ],
        "waste_candidates": [
            {"run_id": r.get("run_id",""), "bot": r.get("bot",""), "task_type": r.get("task_type",""),
             "total_tokens": int(r.get("total_tokens") or 0), "status": r.get("status","")}
            for r in waste_rows
        ],
    }

    # ── Human-readable summary ─────────────────────────────────────────────────
    lines = [
        f"=== Daily Token Usage Report — {today} ===",
        f"Global: {global_total:,} / {global_max:,} ({global_pct}%)",
        f"Estimated cost: ${estimated_cost_usd:.4f}",
        "",
        "Bot usage:",
    ]
    for b in bots_report:
        lines.append(f"  {b['bot']:10s}  {b['total_tokens']:>8,} / {b['daily_budget']:>8,}  ({b['pct_used']}%)")

    lines += ["", "Top task types:"]
    for t in report["top_task_types"]:
        lines.append(f"  {t['task_type']:20s}  {t['tokens']:>8,} tokens  ({t['runs']} runs)")

    if report["waste_candidates"]:
        lines += ["", "Waste candidates (high-token no-op runs):"]
        for w in report["waste_candidates"]:
            lines.append(f"  {w['run_id'][:16]}  {w['bot']:10s}  {w['total_tokens']:>6,} tokens  status={w['status']}")
    else:
        lines.append("\nNo waste candidates today.")

    summary = "\n".join(lines)
    report["summary"] = summary

    # ── Save ───────────────────────────────────────────────────────────────────
    out_path = os.path.join(OUTPUT_DIR, f"usage_report_{today}.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    return report, summary


if __name__ == "__main__":
    report, summary = run_report()
    print(summary)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"\nReport saved to runtime_state/usage_report_{today}.json")
