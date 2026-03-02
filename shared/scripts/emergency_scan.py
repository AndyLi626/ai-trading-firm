#!/usr/bin/env python3
"""
emergency_scan.py — Execute-side: process ONE pending emergency request.
Called by emergency_poll.sh (media bot cron, 1-min interval).
"""
import sys, os, json, uuid, subprocess
from datetime import datetime, timezone

WORKSPACE = "/home/lishopping913/.openclaw/workspace"
SCRIPTS = os.path.join(WORKSPACE, "shared", "scripts")
FACTS_DIR = "/tmp/oc_facts"
REQUESTS_FILE = os.path.join(FACTS_DIR, "emergency_requests.json")
RESULT_FILE = os.path.join(FACTS_DIR, "emergency_scan_result.json")
OPS_ALERTS_FILE = os.path.join(FACTS_DIR, "ops_alerts.json")

sys.path.insert(0, os.path.join(WORKSPACE, "shared", "tools"))

def load_requests():
    if not os.path.exists(REQUESTS_FILE):
        return []
    try:
        with open(REQUESTS_FILE) as f:
            return json.load(f)
    except Exception:
        return []

def save_requests(requests):
    os.makedirs(FACTS_DIR, exist_ok=True)
    with open(REQUESTS_FILE, "w") as f:
        json.dump(requests, f, indent=2)

def append_ops_alert(event: dict):
    alerts = []
    if os.path.exists(OPS_ALERTS_FILE):
        try:
            with open(OPS_ALERTS_FILE) as f:
                alerts = json.load(f)
        except Exception:
            alerts = []
    alerts.append(event)
    with open(OPS_ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)

def check_budget() -> str:
    """Run check_budget_status.py. Returns action string."""
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS, "check_budget_status.py")],
            capture_output=True, text=True, timeout=30
        )
        for line in reversed(r.stdout.strip().splitlines()):
            try:
                d = json.loads(line)
                return d.get("action", "ok")
            except Exception:
                continue
    except Exception:
        pass
    return "ok"

def run_market_pulse(symbols: list) -> dict:
    syms_str = ",".join(symbols)
    subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "market_pulse.py"), syms_str],
        capture_output=True, text=True, timeout=40
    )
    # market_pulse.py writes to FACTS_DIR/MARKET_PULSE.json — read from file
    mp = os.path.join(FACTS_DIR, "MARKET_PULSE.json")
    if os.path.exists(mp):
        try:
            with open(mp) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def run_brave_news(symbols: list) -> list:
    """Fetch Brave news for symbols. Returns list of articles."""
    try:
        import urllib.request, urllib.parse, gzip
        SECRETS = "/home/lishopping913/.openclaw/secrets"
        key_file = os.path.join(SECRETS, "brave_api_key.txt")
        if not os.path.exists(key_file):
            return []
        key = open(key_file).read().strip()
        query = " OR ".join(symbols)
        params = urllib.parse.urlencode({"q": query, "count": 5, "freshness": "pd"})
        req = urllib.request.Request(
            f"https://api.search.brave.com/res/v1/news/search?{params}",
            headers={"Accept": "application/json", "Accept-Encoding": "gzip",
                     "X-Subscription-Token": key}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
        results = json.loads(raw).get("results", [])
        return [{"title": x.get("title", ""), "url": x.get("url", "")} for x in results]
    except Exception as e:
        sys.stderr.write(f"[emergency_scan] brave_news error: {e}\n")
        return []

def write_gcp_signal(symbol: str, pct_change: float, chain_id: str, symbols: list):
    try:
        from gcp_client import log_signal
        value_label = f"{pct_change:+.2f}%" if pct_change is not None else "n/a"
        headline = f"Emergency scan: {','.join(symbols)}"
        log_signal(
            source_bot="media",
            symbol=symbol,
            signal_type="emergency_scan",
            value_numeric=float(pct_change or 0),
            value_label=value_label,
            headline=headline,
            session_id=chain_id
        )
        return True
    except Exception as e:
        sys.stderr.write(f"[emergency_scan] GCP write error for {symbol}: {e}\n")
        return False

def main():
    now_iso = datetime.now(timezone.utc).isoformat()
    os.makedirs(FACTS_DIR, exist_ok=True)

    # Budget check first
    action = check_budget()
    if action == "stop":
        print(json.dumps({"status": "budget_stop"}))
        requests = load_requests()
        for r in requests:
            if r.get("status") == "pending":
                r["status"] = "budget_stop"
                break
        save_requests(requests)
        append_ops_alert({"type": "emergency_scan_budget_stop", "ts": now_iso})
        return

    requests = load_requests()

    # Find first pending
    pending_idx = None
    for i, r in enumerate(requests):
        if r.get("status") == "pending":
            pending_idx = i
            break

    if pending_idx is None:
        print(json.dumps({"status": "no_pending"}))
        return

    req = requests[pending_idx]
    symbols = req.get("symbols", [])
    request_id = req.get("request_id", str(uuid.uuid4()))

    # Mark processing
    requests[pending_idx]["status"] = "processing"
    save_requests(requests)

    chain_id = str(uuid.uuid4())

    # Run market pulse
    market_data = run_market_pulse(symbols)

    # Run brave news
    news = run_brave_news(symbols)

    # Write GCP signals
    quotes = market_data.get("quotes", {})
    signals_written = 0
    for sym in symbols:
        pct = quotes.get(sym, {}).get("pct_change_day")
        if write_gcp_signal(sym, pct, chain_id, symbols):
            signals_written += 1

    completed_at = datetime.now(timezone.utc).isoformat()
    result = {
        "request_id": request_id,
        "symbols": symbols,
        "chain_id": chain_id,
        "trigger": "emergency",
        "market_data": market_data,
        "news_headlines": news[:5],
        "signals_written": signals_written,
        "completed_at": completed_at,
        "status": "done"
    }
    with open(RESULT_FILE, "w") as f:
        json.dump(result, f, indent=2)

    # Mark done
    requests[pending_idx]["status"] = "done"
    save_requests(requests)

    append_ops_alert({
        "type": "emergency_scan_complete",
        "request_id": request_id,
        "symbols": symbols,
        "signals_written": signals_written,
        "ts": completed_at
    })

    # ── P1 downstream: strategy_hint → risk_review_lite ──────────────────────
    WS = "/home/lishopping913/.openclaw/workspace"
    try:
        # Budget check before downstream LLM work
        import subprocess as _sp
        _bud = _sp.run(
            [sys.executable,
             os.path.join(WS, "shared/scripts/run_with_budget.py"),
             "research", "strategy_hint", "2000"],
            capture_output=True, text=True, timeout=15
        )
        _bres = json.loads(_bud.stdout.strip()) if _bud.stdout.strip() else {}
        if _bres.get("allowed", True):
            for script in ["strategy_hint.py", "risk_review_lite.py"]:
                _sp.run(
                    [sys.executable, os.path.join(WS, f"shared/scripts/{script}")],
                    capture_output=True, text=True, timeout=30
                )
    except Exception:
        pass  # degrade silently, main scan already done

try:
    import sys as _sys; _sys.path.insert(0, "/home/lishopping913/.openclaw/workspace/shared/tools")
    from run_registry import registry_set as _rs
    _rs("emergency_scan", result.get("status","ok"), f"signals={result.get('signals_count',0)} chain={result.get('chain_id','')[:8]}")
except Exception:
    pass
    print(json.dumps({"status": "done", "request_id": request_id,
                      "signals_written": signals_written, "chain_id": chain_id}))

if __name__ == "__main__":
    main()
