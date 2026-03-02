#!/usr/bin/env python3
"""
source_health.py — 数据源健康报告
检查各源成功率 + 最近失败原因
输出: /tmp/oc_facts/source_health.json + memory/autonomy/YYYY-MM-DD/source_health.json
无 LLM，纯脚本
"""
import sys, os, json, urllib.request, urllib.error
from datetime import datetime, timezone
import os

sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace-media/shared/tools'))

FACTS   = "/tmp/oc_facts"
WS = os.path.expanduser('~/.openclaw/workspace')
now_utc = datetime.now(timezone.utc)
TODAY   = now_utc.strftime("%Y-%m-%d")


def check_source(name, check_fn):
    try:
        result = check_fn()
        return {"source": name, "status": "ok", "detail": result, "checked_at": now_utc.isoformat()}
    except Exception as e:
        err_str = str(e)
        status = "quota_limited" if any(k in err_str.lower() for k in ["403","rate limit","detected your api","quota"]) else "error"
        return {"source": name, "status": status, "error": str(e)[:120], "checked_at": now_utc.isoformat()}


def check_brave():
    from load_secrets import brave_api_key
    key = brave_api_key()
    assert key and len(key) > 10, "key missing or too short"
    import urllib.parse
    params = urllib.parse.urlencode({"q": "SPY", "count": 1, "freshness": "pd"})
    req = urllib.request.Request(
        f"https://api.search.brave.com/res/v1/news/search?{params}",
        headers={"Accept": "application/json", "X-Subscription-Token": key}
    )
    r = json.loads(urllib.request.urlopen(req, timeout=8).read())
    results = r.get("results", [])
    return {"results_count": len(results), "key_len": len(key)}


def check_alphavantage():
    from load_secrets import alphavantage
    key = alphavantage()
    assert key and len(key) > 5, "key missing"
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=SPY&apikey={key}"
    r = json.loads(urllib.request.urlopen(url, timeout=8).read())
    quote = r.get("Global Quote", {})
    assert quote, f"empty response: {str(r)[:80]}"
    return {"price": quote.get("05. price"), "symbol": "SPY"}


def check_fmp():
    try:
        fmp_key = open(os.path.expanduser('~/.openclaw/secrets/fmp_api_key.txt')).read().strip()
    except Exception:
        from load_secrets import fmp as _fmp
        fmp_key = _fmp()
    url = f"https://financialmodelingprep.com/api/v3/quote/SPY?apikey={fmp_key}"
    r = json.loads(urllib.request.urlopen(url, timeout=8).read())
    assert r and len(r) > 0, "empty response"
    return {"price": r[0].get("price"), "symbol": "SPY"}


def check_hyperliquid():
    payload = json.dumps({"type": "allMids"}).encode()
    req = urllib.request.Request(
        "https://api.hyperliquid.xyz/info",
        data=payload, headers={"Content-Type": "application/json"}
    )
    r = json.loads(urllib.request.urlopen(req, timeout=8).read())
    btc = r.get("BTC")
    assert btc, "BTC price missing"
    return {"BTC": float(btc), "ETH": float(r.get("ETH", 0))}


def check_alpaca():
    key    = open(os.path.expanduser('~/.openclaw/secrets/alpaca_paper_key.txt')).read().strip()
    secret = open(os.path.expanduser('~/.openclaw/secrets/alpaca_paper_secret.txt')).read().strip()
    req = urllib.request.Request(
        "https://data.alpaca.markets/v2/stocks/bars/latest?symbols=SPY&feed=iex",
        headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    )
    r = json.loads(urllib.request.urlopen(req, timeout=8).read())
    bar = r.get("bars", {}).get("SPY", {})
    assert bar, "SPY bar missing"
    return {"SPY_close": bar.get("c")}


def main():
    checks = [
        ("brave_news",    check_brave),
        # alphavantage: free-tier quota exhausted — disabled to stop repeated failures
        # fmp: 403 on free tier — disabled
        ("hyperliquid",   check_hyperliquid),
        ("alpaca_iex",    check_alpaca),
    ]

    results = [check_source(name, fn) for name, fn in checks]

    ok_count      = sum(1 for r in results if r["status"] == "ok")
    degraded_count= sum(1 for r in results if r["status"] == "quota_limited")
    fail_count    = sum(1 for r in results if r["status"] == "error")
    fail_sources  = [r["source"] for r in results if r["status"] in ("error","quota_limited")]

    # Price deviation check (Brave vs Alpaca for market sentiment proxy)
    # Just flag if any primary source failed
    alerts = []
    if fail_count > 0:
        alerts.append({
            "type":     "source_failure",
            "sources":  fail_sources,
            "severity": "high" if fail_count >= 2 else "medium"
        })

    output = {
        "date":        TODAY,
        "generated_at": now_utc.isoformat(),
        "sources":     results,
        "summary": {
            "total":   len(results),
            "ok":      ok_count,
            "failed":  fail_count,
            "degraded": degraded_count,
            "ok_rate": round(ok_count / len(results) * 100, 1)
        },
        "alerts":      alerts
    }

    # Write alerts to audit (not Telegram)
    if alerts:
        audit_file = os.path.join(FACTS, "ops_alerts.json")
        try:
            existing = json.load(open(audit_file)) if os.path.exists(audit_file) else []
            for a in alerts:
                a["ts"] = now_utc.isoformat()
                existing.append(a)
            json.dump(existing, open(audit_file, "w"), indent=2)
        except Exception:
            pass

    # Write output
    os.makedirs(FACTS, exist_ok=True)
    json.dump(output, open(os.path.join(FACTS, "source_health.json"), "w"), indent=2)

    auto_dir = os.path.join(WS, "memory/autonomy", TODAY)
    os.makedirs(auto_dir, exist_ok=True)
    json.dump(output, open(os.path.join(auto_dir, "source_health.json"), "w"), indent=2)

    # Summary print
    for r in results:
        icon = "✅" if r["status"] == "ok" else "❌"
        detail = r.get("detail", r.get("error",""))
        print(f"  {icon} {r['source']:15s} {str(detail)[:60]}")

    print(json.dumps(output["summary"]))


if __name__ == "__main__":
    main()