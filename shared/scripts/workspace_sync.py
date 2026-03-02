#!/usr/bin/env python3
"""
workspace_sync.py — Push shared evidence files from main workspace to all bot workspaces.
Deterministic, 0 LLM. Run after market_pulse, data_quality, bot_cache updates.

Sync map: main workspace → [manager, research, risk, audit, media] workspaces
Only syncs files that are NEWER in source than destination.
"""
import os, shutil, time, json
from datetime import datetime, timezone

WS       = os.path.expanduser('~/.openclaw/workspace')
TARGETS  = {
    'manager':  os.path.expanduser('~/.openclaw/workspace-manager'),
    'research': os.path.expanduser('~/.openclaw/workspace-research'),
    'media':    os.path.expanduser('~/.openclaw/workspace-media'),
    'risk':     os.path.expanduser('~/.openclaw/workspace-risk'),
    'audit':    os.path.expanduser('~/.openclaw/workspace-audit'),
}

# Which bots need which files
SYNC_MAP = {
    # (source_rel_path, [target_bots])
    'memory/market/MARKET_PULSE.json':     ['manager','research','media','risk','audit'],
    'memory/data_quality_status.json':     ['manager','research','risk','audit'],
    'memory/bot_cache.json':               ['manager'],
    'memory/READY_FOR_RESEARCH_CERT.md':   ['manager','research'],
    'memory/paper_account_snapshot.json':  ['manager','risk'],
    'memory/paper_pnl_daily.md':           ['manager','risk'],
}

def sync():
    now    = datetime.now(timezone.utc).isoformat()[:19]
    synced = []
    skipped = []
    errors  = []

    for rel_path, bots in SYNC_MAP.items():
        src = os.path.join(WS, rel_path)
        if not os.path.exists(src):
            skipped.append(f"src missing: {rel_path}")
            continue

        src_mtime = os.path.getmtime(src)

        for bot in bots:
            dst = os.path.join(TARGETS[bot], rel_path)
            dst_dir = os.path.dirname(dst)

            # Skip if dst is newer or same age
            if os.path.exists(dst) and os.path.getmtime(dst) >= src_mtime:
                skipped.append(f"{bot}/{rel_path} (up-to-date)")
                continue

            try:
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(src, dst)
                synced.append(f"{bot}/{rel_path}")
            except Exception as e:
                errors.append(f"{bot}/{rel_path}: {e}")

    result = {
        'as_of':   now,
        'synced':  synced,
        'skipped': skipped,
        'errors':  errors,
    }

    # Write sync log
    log_path = os.path.join(WS, 'memory/workspace_sync_last.json')
    with open(log_path, 'w') as f:
        json.dump(result, f, indent=2)

    return result

if __name__ == '__main__':
    r = sync()
    print(f"workspace_sync: synced={len(r['synced'])} skipped={len(r['skipped'])} errors={len(r['errors'])}")
    for s in r['synced']:   print(f"  ✅ {s}")
    for e in r['errors']:   print(f"  ❌ {e}")
