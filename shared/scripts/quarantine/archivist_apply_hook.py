#!/usr/bin/env python3
"""
archivist_apply_hook.py — apply 后自动执行的钩子
调用方式: python3 archivist_apply_hook.py "<change_summary>" [--files f1,f2]
功能:
  1. CHANGELOG 追加一条记录
  2. arch_lock generate (刷新快照)
  3. snapshot_capabilities (刷新 STATUS_MATRIX)
  4. 写 bot_cache.archivist 供 ManagerBot 读取
  5. 生成 rollbacks/YYYYMMDD-<id>.json (回滚清单)
"""
import sys, os, json, uuid, subprocess
from datetime import datetime, timezone

WS      = os.path.expanduser("~/.openclaw/workspace")
LEDGER  = os.path.join(WS, "ledger")
CACHE   = os.path.join(WS, "memory/bot_cache.json")
now_utc = datetime.now(timezone.utc)
TODAY   = now_utc.strftime("%Y-%m-%d")

os.makedirs(os.path.join(LEDGER, "rollbacks"), exist_ok=True)

def run(script, *args):
    return subprocess.run(
        [sys.executable, os.path.join(WS, "shared/scripts", script)] + list(args),
        capture_output=True, text=True, timeout=30
    )

def append_changelog(summary, files, change_id):
    cl = os.path.join(LEDGER, "CHANGELOG.md")
    entry = (f"| {TODAY} | `{change_id[:8]}` | {summary[:80]} "
             f"| {', '.join(files[:3]) if files else '—'} |\n")
    # Ensure table exists
    if not os.path.exists(cl):
        header = ("# Platform Changelog\n_Append-only._\n\n"
                  "| Date | ID | Change | Files |\n"
                  "|------|----|--------|-------|\n")
        open(cl, "w").write(header)
    open(cl, "a").write(entry)

def write_rollback_manifest(summary, files, change_id):
    rb_file = os.path.join(LEDGER, "rollbacks",
                           f"{TODAY.replace('-','')}-{change_id[:8]}.json")
    manifest = {
        "change_id":    change_id,
        "applied_at":   now_utc.isoformat(),
        "summary":      summary,
        "files":        files,
        "rollback_steps": [
            f"git revert --no-commit HEAD (if committed)",
            f"Restore files: {files}",
            "python3 shared/scripts/arch_lock.py generate",
            "python3 shared/scripts/snapshot_capabilities.py",
        ]
    }
    json.dump(manifest, open(rb_file, "w"), indent=2)
    return rb_file

def update_bot_cache(snapshot_result, changelog_entry, drift_count):
    try:
        cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
        cache["archivist"] = {
            "last_snapshot_at":   now_utc.isoformat(),
            "last_change":        changelog_entry,
            "status_matrix_path": os.path.join(LEDGER, "STATUS_MATRIX.md"),
            "drift_count":        drift_count,
            "verified_count":     snapshot_result.get("counts", {}).get("VERIFIED", 0),
            "wired_count":        snapshot_result.get("counts", {}).get("WIRED", 0),
            "total_items":        snapshot_result.get("items", 0),
            "updated_at":         now_utc.isoformat()
        }
        json.dump(cache, open(CACHE, "w"), indent=2)
    except Exception as e:
        pass  # non-blocking

def main():
    summary = sys.argv[1] if len(sys.argv) > 1 else "manual apply"
    files_arg = ""
    for i, a in enumerate(sys.argv):
        if a == "--files" and i + 1 < len(sys.argv):
            files_arg = sys.argv[i + 1]
    files = [f.strip() for f in files_arg.split(",") if f.strip()] if files_arg else []
    change_id = str(uuid.uuid4())

    results = {}

    # 1. CHANGELOG
    append_changelog(summary, files, change_id)
    results["changelog"] = "ok"

    # 2. arch_lock generate
    r = run("arch_lock.py", "generate")
    try:
        lock_r = json.loads(r.stdout)
        results["arch_lock"] = {"entries": lock_r.get("entries"), "status": "ok"}
    except Exception:
        results["arch_lock"] = {"status": "error", "stderr": r.stderr[:100]}

    # 3. snapshot_capabilities
    r = run("snapshot_capabilities.py")
    snap_r = {}
    try:
        snap_r = json.loads(r.stdout)
        results["snapshot"] = {"items": snap_r.get("items"), "status": "ok"}
    except Exception:
        results["snapshot"] = {"status": "error"}

    # 4. arch_lock check (get drift count after generate — should be 0)
    r = run("arch_lock.py", "check")
    drift_count = 0
    try:
        drift_r = json.loads(r.stdout)
        drift_count = drift_r.get("drift_count", 0)
        results["drift_after_apply"] = drift_count
    except Exception:
        pass

    # 5. rollback manifest
    rb_file = write_rollback_manifest(summary, files, change_id)
    results["rollback_manifest"] = rb_file

    # 6. bot_cache.archivist
    update_bot_cache(snap_r, summary, drift_count)
    results["bot_cache"] = "ok"

    print(json.dumps({
        "status":    "ok",
        "change_id": change_id,
        "summary":   summary,
        "results":   results,
        "applied_at": now_utc.isoformat()
    }, indent=2))

if __name__ == "__main__":
    main()
