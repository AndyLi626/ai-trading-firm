#!/usr/bin/env python3
"""
emergency_trigger.py — Write-side of emergency scan system.
Usage: python3 emergency_trigger.py PLTR XOM GLD [--reason "why"]
"""
import sys, os, json, uuid, argparse
from datetime import datetime, timezone, timedelta

FACTS_DIR = "/tmp/oc_facts"
REQUESTS_FILE = os.path.join(FACTS_DIR, "emergency_requests.json")
OPS_ALERTS_FILE = os.path.join(FACTS_DIR, "ops_alerts.json")

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
    os.makedirs(FACTS_DIR, exist_ok=True)
    with open(OPS_ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("symbols", nargs="+")
    p.add_argument("--reason", default="")
    return p.parse_args()

def main():
    args = parse_args()
    symbols = sorted(set(s.upper() for s in args.symbols))
    reason = args.reason
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    requests = load_requests()

    # DEDUP: same symbol set within last 10 minutes
    sym_set = set(symbols)
    cutoff_dedup = now - timedelta(minutes=10)
    for r in requests:
        if set(r.get("symbols", [])) == sym_set:
            try:
                req_at = datetime.fromisoformat(r["requested_at"])
            except Exception:
                continue
            if req_at > cutoff_dedup:
                result = {"accepted": False, "reason": f"dedup: last_request_at={r['requested_at']}"}
                print(json.dumps(result))
                append_ops_alert({
                    "type": "emergency_trigger", "symbols": symbols,
                    "accepted": False, "reason": result["reason"], "ts": now_iso
                })
                return

    # RATE LIMIT: >= 3 requests in last 60 minutes
    cutoff_rate = now - timedelta(minutes=60)
    recent_count = 0
    for r in requests:
        try:
            req_at = datetime.fromisoformat(r["requested_at"])
        except Exception:
            continue
        if req_at > cutoff_rate:
            recent_count += 1
    if recent_count >= 3:
        result = {"accepted": False, "reason": "rate_limit: 3/hour max"}
        print(json.dumps(result))
        append_ops_alert({
            "type": "emergency_trigger", "symbols": symbols,
            "accepted": False, "reason": result["reason"], "ts": now_iso
        })
        return

    # Accept
    req_id = str(uuid.uuid4())
    new_req = {
        "request_id": req_id,
        "symbols": symbols,
        "reason": reason,
        "requested_at": now_iso,
        "status": "pending",
        "trigger": "emergency"
    }
    requests.append(new_req)
    save_requests(requests)

    result = {"accepted": True, "request_id": req_id, "symbols": symbols}
    print(json.dumps(result))
    append_ops_alert({
        "type": "emergency_trigger", "symbols": symbols,
        "accepted": True, "reason": reason, "request_id": req_id, "ts": now_iso
    })

if __name__ == "__main__":
    main()
