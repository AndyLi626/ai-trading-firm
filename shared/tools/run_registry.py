#!/usr/bin/env python3
"""
run_registry.py — 轻量级 job 运行事实源
写: registry_set(task_key, status, summary="")
读: registry_get(task_key) → {last_run_age, last_summary_age, verdict}
CLI: python3 run_registry.py get <task_key>
     python3 run_registry.py set <task_key> <ok|failed|degraded> [summary]
     python3 run_registry.py list
"""
import sys, os, json
from datetime import datetime, timezone

REGISTRY_FILE = os.path.join(
    os.path.expanduser("~/.openclaw/workspace"),
    "shared/state/run_registry.json"
)
os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)

# Verdict thresholds (seconds)
REFRESH_NEEDED  = 900   # >15min → REFRESH_OK (stale, go fetch)
SUMMARY_STALE   = 3600  # >60min → SUMMARY_ONLY (no new fetch, but resummary ok)


def _load():
    try:    return json.load(open(REGISTRY_FILE))
    except: return {}

def _save(data):
    json.dump(data, open(REGISTRY_FILE, "w"), indent=2)


def registry_set(task_key: str, status: str, summary: str = ""):
    """Write a completed run record."""
    data = _load()
    now  = datetime.now(timezone.utc).isoformat()
    entry = data.get(task_key, {})
    entry["task_key"]     = task_key
    entry["last_run_at"]  = now
    entry["last_status"]  = status
    if summary:
        entry["last_summary_at"]   = now
        entry["last_summary_text"] = summary[:200]
    elif "last_summary_at" not in entry:
        entry["last_summary_at"]   = None
        entry["last_summary_text"] = None
    data[task_key] = entry
    _save(data)
    return entry


def registry_get(task_key: str) -> dict:
    """Read a run record and compute ages + verdict."""
    data  = _load()
    entry = data.get(task_key)
    now   = datetime.now(timezone.utc)

    if not entry:
        return {
            "task_key":        task_key,
            "found":           False,
            "last_run_age":    None,
            "last_summary_age": None,
            "verdict":         "REFRESH_OK",   # never run → go fetch
            "last_status":     None,
        }

    def age(ts_str):
        if not ts_str: return None
        try:
            dt = datetime.fromisoformat(ts_str)
            return int((now - dt).total_seconds())
        except:
            return None

    run_age     = age(entry.get("last_run_at"))
    summary_age = age(entry.get("last_summary_at"))

    # Verdict logic
    if run_age is None or run_age > REFRESH_NEEDED:
        verdict = "REFRESH_OK"
    elif summary_age is None or summary_age > SUMMARY_STALE:
        verdict = "SUMMARY_ONLY"
    else:
        verdict = "NO_OP"

    return {
        "task_key":         task_key,
        "found":            True,
        "last_run_at":      entry.get("last_run_at"),
        "last_run_age":     run_age,
        "last_summary_at":  entry.get("last_summary_at"),
        "last_summary_age": summary_age,
        "last_status":      entry.get("last_status"),
        "last_summary_text": entry.get("last_summary_text"),
        "verdict":          verdict,
    }


def registry_list() -> list:
    return list(_load().values())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "get":
        key = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(registry_get(key), indent=2))
    elif cmd == "set":
        key     = sys.argv[2]
        status  = sys.argv[3] if len(sys.argv) > 3 else "ok"
        summary = sys.argv[4] if len(sys.argv) > 4 else ""
        print(json.dumps(registry_set(key, status, summary), indent=2))
    elif cmd == "list":
        rows = registry_list()
        if not rows:
            print("(empty registry)")
        for r in rows:
            age = r.get("last_run_age")
            age_s = f"{age//60}min ago" if age else "never"
            print(f"  {r['task_key']:35s} {r['last_status']:8s} {age_s}")
    else:
        print("Usage: run_registry.py get|set|list [args]")
        sys.exit(1)
