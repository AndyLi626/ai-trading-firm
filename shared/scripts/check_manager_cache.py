#!/usr/bin/env python3
"""
check_manager_cache.py — Validate ManagerBot cache contract compliance.
Usage: python3 shared/scripts/check_manager_cache.py
Output: JSON {"ok": bool, "missing_fields": [...], "stale": bool, "status": "..."}
"""
import sys, os, json
from datetime import datetime, timezone, timedelta

CACHE_PATH = os.path.join(os.path.dirname(__file__), "../../memory/bot_cache.json")
CACHE_PATH = os.path.normpath(CACHE_PATH)

REQUIRED_FIELDS = [
    "last_round_conclusions",
    "open_issues",
    "blocked_items",
    "last_real_data_timestamp",
    "pending_requests",
    "last_full_chain_status",
    "last_updated",
]
VALID_STATUSES = {"ok", "degraded", "stale", "unknown"}
MAX_STALE_SECONDS = 7200  # 2 hours

def main():
    result = {"ok": False, "missing_fields": [], "stale": False, "status": "unknown"}

    if not os.path.exists(CACHE_PATH):
        result["status"] = "CACHE_FILE_MISSING"
        print(json.dumps(result))
        return

    try:
        with open(CACHE_PATH) as f:
            cache = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        result["status"] = f"CACHE_READ_ERROR: {e}"
        print(json.dumps(result))
        return

    manager = cache.get("manager")
    if not isinstance(manager, dict):
        result["status"] = "MANAGER_SECTION_MISSING_OR_INVALID"
        result["missing_fields"] = REQUIRED_FIELDS
        print(json.dumps(result))
        return

    # Check required fields
    missing = [f for f in REQUIRED_FIELDS if f not in manager]
    result["missing_fields"] = missing

    # Check staleness
    last_updated = manager.get("last_updated")
    stale = True
    if last_updated:
        try:
            ts = datetime.fromisoformat(last_updated)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            stale = age > MAX_STALE_SECONDS
        except ValueError:
            stale = True
    result["stale"] = stale

    # Check last_full_chain_status
    chain_status = manager.get("last_full_chain_status", "")
    if chain_status not in VALID_STATUSES:
        result["status"] = f"INVALID_CHAIN_STATUS: {chain_status!r} (expected one of {sorted(VALID_STATUSES)})"
    elif missing:
        result["status"] = f"MISSING_FIELDS: {missing}"
    elif stale:
        result["status"] = "STALE"
    else:
        result["status"] = "ok"
        result["ok"] = True

    print(json.dumps(result))

if __name__ == "__main__":
    main()
