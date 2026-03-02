#!/usr/bin/env python3
"""
token_cost_summary.py — 今日 token 消耗与成本汇总。
优先查 token_usage_calls，fallback 到 token_usage_runs，再 fallback 到 legacy token_usage。
输出：JSON + 人类可读文本。
安全：任何步骤失败只写日志，不中断调用方。
"""
import sys, os, json
from datetime import datetime, timezone

sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/shared/tools"))

PRICING_FILE = os.path.expanduser("~/.openclaw/workspace/shared/config/model_pricing.json")
FALLBACK_LOG = "/tmp/oc_facts/cost_summary_error.log"

def load_pricing():
    try:
        return json.load(open(PRICING_FILE)).get("models", {})
    except Exception as e:
        _log(f"pricing load error: {e}")
        return {}

def _log(msg):
    try:
        with open(FALLBACK_LOG, "a") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")
    except Exception:
        pass

def calc_cost(model, input_tokens, output_tokens, pricing):
    p = pricing.get(model)
    if not p:
        return None, True  # cost=None, pricing_missing=True
    cost = (input_tokens * p["input_per_1m_usd"] / 1_000_000
          + output_tokens * p["output_per_1m_usd"] / 1_000_000)
    return round(cost, 6), False

def query_today():
    """Query today's usage. Priority: calls → runs → legacy."""
    from gcp_client import query

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. token_usage_calls (most detailed)
    try:
        rows = query(f"""
            SELECT bot, model,
                   SUM(input_tokens) as tin, SUM(output_tokens) as tout,
                   SUM(total_tokens) as total, COUNT(*) as calls
            FROM trading_firm.token_usage_calls
            WHERE DATE(started_at) = '{today}'
              AND (is_test IS NULL OR is_test = FALSE)
            GROUP BY bot, model
        """)
        if rows:
            return rows, "token_usage_calls"
    except Exception as e:
        _log(f"calls query error: {e}")

    # 2. token_usage_runs
    try:
        rows = query(f"""
            SELECT bot, '' as model,
                   SUM(total_input_tokens) as tin, SUM(total_output_tokens) as tout,
                   SUM(total_tokens) as total, SUM(llm_calls) as calls
            FROM trading_firm.token_usage_runs
            WHERE date = '{today}'
              AND (is_test IS NULL OR is_test = FALSE)
              AND total_tokens > 0
            GROUP BY bot
        """)
        if rows:
            return rows, "token_usage_runs"
    except Exception as e:
        _log(f"runs query error: {e}")

    # 3. legacy token_usage
    try:
        rows = query(f"""
            SELECT bot, model,
                   SUM(CAST(input_tokens AS INT64)) as tin,
                   SUM(CAST(output_tokens AS INT64)) as tout,
                   SUM(CAST(input_tokens AS INT64)+CAST(output_tokens AS INT64)) as total,
                   COUNT(*) as calls
            FROM trading_firm.token_usage
            WHERE DATE(TIMESTAMP_SECONDS(CAST(CAST(timestamp AS FLOAT64) AS INT64))) = '{today}'
            GROUP BY bot, model
        """)
        if rows:
            return rows, "token_usage_legacy"
    except Exception as e:
        _log(f"legacy query error: {e}")

    return [], "no_data"

def build_summary():
    pricing = load_pricing()
    rows, source = query_today()

    by_bot = {}
    by_model = {}
    missing_models = set()
    global_in = global_out = global_total = 0
    global_cost = 0.0

    for r in rows:
        bot   = r.get("bot") or "unknown"
        model = r.get("model") or ""
        tin   = int(r.get("tin") or 0)
        tout  = int(r.get("tout") or 0)
        total = int(r.get("total") or 0) or (tin + tout)
        calls = int(r.get("calls") or 0)

        cost, missing = calc_cost(model, tin, tout, pricing)
        if missing and model:
            missing_models.add(model)

        # by bot
        if bot not in by_bot:
            by_bot[bot] = {"tokens_in":0,"tokens_out":0,"total_tokens":0,"est_cost_usd":0.0,"pricing_missing":False,"calls":0}
        by_bot[bot]["tokens_in"]    += tin
        by_bot[bot]["tokens_out"]   += tout
        by_bot[bot]["total_tokens"] += total
        by_bot[bot]["calls"]        += calls
        if cost is not None:
            by_bot[bot]["est_cost_usd"] = round(by_bot[bot]["est_cost_usd"] + cost, 6)
        else:
            by_bot[bot]["pricing_missing"] = True

        # by model
        if model:
            if model not in by_model:
                by_model[model] = {"tokens_in":0,"tokens_out":0,"total_tokens":0,"est_cost_usd":0.0,"pricing_missing":False}
            by_model[model]["tokens_in"]    += tin
            by_model[model]["tokens_out"]   += tout
            by_model[model]["total_tokens"] += total
            if cost is not None:
                by_model[model]["est_cost_usd"] = round(by_model[model]["est_cost_usd"] + cost, 6)
            else:
                by_model[model]["pricing_missing"] = True

        global_in    += tin
        global_out   += tout
        global_total += total
        if cost is not None:
            global_cost = round(global_cost + cost, 6)

    result = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source": source,
        "by_bot": by_bot,
        "by_model": by_model,
        "global": {
            "total_tokens_in":  global_in,
            "total_tokens_out": global_out,
            "total_tokens":     global_total,
            "est_cost_usd":     global_cost,
            "missing_pricing":  list(missing_models)[:3]
        },
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    return result

def human_readable(s):
    lines = [f"📊 Token 消耗汇总 — {s['date']} (来源: {s['source']})"]
    lines.append("")
    lines.append("各 Bot 消耗：")
    for bot, d in sorted(s["by_bot"].items(), key=lambda x: -x[1]["total_tokens"]):
        cost_str = f"${d['est_cost_usd']:.4f}" if not d["pricing_missing"] else "N/A(pricing missing)"
        lines.append(f"  {bot:12s} in={d['tokens_in']:>7,} out={d['tokens_out']:>7,} total={d['total_tokens']:>8,} cost={cost_str}")
    g = s["global"]
    lines.append("")
    lines.append(f"全局今日合计：{g['total_tokens']:,} tokens | 预估成本 ${g['est_cost_usd']:.4f} USD")
    if g["missing_pricing"]:
        lines.append(f"⚠️ 缺少单价的模型: {', '.join(g['missing_pricing'])}")
    return "\n".join(lines)

if __name__ == "__main__":
    try:
        s = build_summary()
        print(json.dumps(s, ensure_ascii=False, indent=2))
        print()
        print(human_readable(s))
        # Save for ManagerBot to read
        out = "/tmp/oc_facts/cost_summary.json"
        json.dump(s, open(out,"w"), ensure_ascii=False, indent=2)
    except Exception as e:
        _log(f"FATAL: {e}")
        # 失败时输出空结构，不中断调用方
        print(json.dumps({"error": str(e), "by_bot": {}, "global": {"total_tokens":0,"est_cost_usd":0}}))
        sys.exit(0)
