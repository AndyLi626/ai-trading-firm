#!/usr/bin/env python3
"""
audit_data_violation.py
Usage: echo '{"bot":"manager","output":"BTC +2.3%","context":"cron"}' | python3 audit_data_violation.py
Logs SEV-0 DATA_FABRICATION_RISK to GCP decisions table and prints ticket JSON.
"""
import sys, os, json
from datetime import datetime, timezone
import os

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
BOT_CACHE_PATH = os.path.join(WORKSPACE, "memory", "bot_cache.json")
GCP_CLIENT_DIR = os.path.join(WORKSPACE, "shared", "tools")


def main():
    raw = sys.stdin.read().strip()
    try:
        payload = json.loads(raw)
    except Exception as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    bot = payload.get("bot", "unknown")
    output = payload.get("output", "")
    context = payload.get("context", "")

    reasoning = f"Output contained market data without provenance: {output[:200]}"

    # Log to GCP decisions table
    try:
        sys.path.insert(0, GCP_CLIENT_DIR)
        from gcp_client import log_decision
        log_decision(
            bot=bot,
            decision_type="SEV0_DATA_FABRICATION",
            summary=reasoning,
            risk_status="SEV0",
            token_cost=0,
            session_id=context,
            payload={"bot": bot, "output": output[:500], "context": context}
        )
        gcp_ok = True
    except Exception as e:
        sys.stderr.write(f"[audit_data_violation] GCP log failed: {e}\n")
        gcp_ok = False

    # Update bot_cache.json
    now_ts = datetime.now(timezone.utc).isoformat()
    try:
        if os.path.exists(BOT_CACHE_PATH):
            with open(BOT_CACHE_PATH) as f:
                cache = json.load(f)
        else:
            cache = {}

        if bot not in cache:
            cache[bot] = {}
        cache[bot]["data_violation_active"] = True
        cache[bot]["data_violation_ts"] = now_ts

        with open(BOT_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
        cache_ok = True
    except Exception as e:
        sys.stderr.write(f"[audit_data_violation] bot_cache update failed: {e}\n")
        cache_ok = False

    ticket = {
        "ticket": "SEV-0",
        "severity": "DATA_FABRICATION_RISK",
        "bot": bot,
        "frozen": True,
        "reasoning": reasoning,
        "context": context,
        "gcp_logged": gcp_ok,
        "cache_updated": cache_ok,
        "ts": now_ts
    }
    print(json.dumps(ticket, indent=2))


if __name__ == "__main__":
    main()