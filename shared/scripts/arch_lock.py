#!/usr/bin/env python3
"""
arch_lock.py — 生成/校验 ledger/ARCH_LOCK.json
用途：
  python3 arch_lock.py generate   → 生成/刷新 lockfile
  python3 arch_lock.py check      → 与上次 lock 对比，输出 drift items
"""
import sys, os, json, hashlib, glob
from datetime import datetime, timezone

WS      = os.path.expanduser("~/.openclaw/workspace")
CRON_F  = os.path.expanduser("~/.openclaw/cron/jobs.json")
LOCK_F  = os.path.join(WS, "ledger", "ARCH_LOCK.json")
SCRIPTS = os.path.join(WS, "shared/scripts")
CONFIG  = os.path.join(WS, "shared/config")
os.makedirs(os.path.join(WS, "ledger"), exist_ok=True)


def sha256(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except Exception:
        return None


def file_entry(path):
    rel = os.path.relpath(path, WS)
    return {"path": rel, "hash": sha256(path),
            "size": os.path.getsize(path) if os.path.exists(path) else 0}


def snapshot():
    entries = {}

    # 1. cron jobs — hash each job payload individually
    try:
        jobs = json.load(open(CRON_F)).get("jobs", [])
        for j in jobs:
            key = f"cron::{j['name']}"
            payload_str = json.dumps(j.get("payload", {}), sort_keys=True)
            sched_str   = json.dumps(j.get("schedule", {}), sort_keys=True)
            entries[key] = {
                "name":     j["name"],
                "agent":    j.get("agentId",""),
                "delivery": j.get("delivery", {}).get("mode",""),
                "schedule_hash": hashlib.sha256(sched_str.encode()).hexdigest()[:16],
                "payload_hash":  hashlib.sha256(payload_str.encode()).hexdigest()[:16],
            }
    except Exception as e:
        entries["cron::_error"] = {"error": str(e)}

    # 2. shared scripts
    for path in sorted(glob.glob(os.path.join(SCRIPTS, "*.py"))):
        key = f"script::{os.path.basename(path)}"
        entries[key] = file_entry(path)

    # 3. shared config files
    for path in sorted(glob.glob(os.path.join(CONFIG, "*.json"))):
        key = f"config::{os.path.basename(path)}"
        entries[key] = file_entry(path)

    # 4. ledger ADRs
    for path in sorted(glob.glob(os.path.join(WS, "ledger/ADRs/*.md"))):
        key = f"adr::{os.path.basename(path)}"
        entries[key] = file_entry(path)

    # 5. skills index (names only, not content)
    skill_names = []
    for p in glob.glob(os.path.expanduser("~/.openclaw/workspace*/skills/*/SKILL.md")):
        parts = p.split(os.sep)
        skill_names.append(parts[-2])
    entries["skills::index"] = {
        "count": len(skill_names),
        "hash": hashlib.sha256(json.dumps(sorted(skill_names)).encode()).hexdigest()[:16],
        "names": sorted(set(skill_names))
    }

    return entries


def generate():
    snap = snapshot()
    lock = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
        "entries": snap
    }
    json.dump(lock, open(LOCK_F, "w"), indent=2)
    print(json.dumps({"status": "generated", "entries": len(snap),
                      "lock_file": LOCK_F}))


def check():
    if not os.path.exists(LOCK_F):
        print(json.dumps({"status": "no_lockfile", "drift": []}))
        return

    prev = json.load(open(LOCK_F))
    prev_entries = prev.get("entries", {})
    curr_entries = snapshot()

    drift = []
    all_keys = set(prev_entries) | set(curr_entries)

    for key in sorted(all_keys):
        p = prev_entries.get(key)
        c = curr_entries.get(key)
        if p is None:
            drift.append({"key": key, "change": "added"})
        elif c is None:
            drift.append({"key": key, "change": "deleted"})
        else:
            # Compare hashes
            p_hash = p.get("hash") or p.get("payload_hash")
            c_hash = c.get("hash") or c.get("payload_hash")
            if p_hash and c_hash and p_hash != c_hash:
                drift.append({"key": key, "change": "modified",
                               "prev_hash": p_hash, "curr_hash": c_hash})

    result = {
        "status":       "drift_detected" if drift else "clean",
        "drift_count":  len(drift),
        "drift":        drift,
        "prev_lock_at": prev.get("generated_at"),
        "checked_at":   datetime.now(timezone.utc).isoformat()
    }

    # Write drift summary to DRIFT_REPORT.md
    if drift:
        _append_drift_to_report(drift, prev.get("generated_at",""))

    print(json.dumps(result, indent=2))


def _append_drift_to_report(drift, prev_ts):
    drift_md = os.path.join(WS, "ledger/DRIFT_REPORT.md")
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    lines = [f"\n## Arch Drift @ {now} (since {prev_ts[:16] if prev_ts else '?'})"]
    added   = [d for d in drift if d["change"] == "added"]
    deleted = [d for d in drift if d["change"] == "deleted"]
    modified= [d for d in drift if d["change"] == "modified"]
    if added:   lines += [f"- ➕ {d['key']}" for d in added]
    if deleted: lines += [f"- ➖ {d['key']}" for d in deleted]
    if modified:lines += [f"- ✏️  {d['key']} ({d['prev_hash']}→{d['curr_hash']})" for d in modified]
    with open(drift_md, "a") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if cmd == "generate":
        generate()
    elif cmd == "check":
        check()
    else:
        print(f"Usage: arch_lock.py generate|check")
        sys.exit(1)
