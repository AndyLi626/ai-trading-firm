#!/usr/bin/env python3
"""
bot_cache_alert_gate.py — Hard gate for ManagerBot before dispatching alerts.

Usage: python3 bot_cache_alert_gate.py
Exit 0: gate PASS — bot_cache is fresh, alert evaluation allowed
Exit 1: gate FAIL — CACHE_STALE, alerts suppressed

ManagerBot MUST call this before any alert/report dispatch.
If FAIL: output CACHE_STALE and suppress the alert.
"""
import json, os, sys, time, subprocess
from datetime import datetime, timezone

WS       = os.path.expanduser('~/.openclaw/workspace')
BC_PATH  = os.path.join(WS, 'memory/bot_cache.json')
MAX_STALE_MIN = 30   # bot_cache older than this → try refresh

def get_cache_age_min():
    if not os.path.exists(BC_PATH):
        return float('inf')
    return (time.time() - os.path.getmtime(BC_PATH)) / 60

def try_refresh():
    """Run bot_cache_refresh.py. Returns True on success."""
    try:
        result = subprocess.run(
            ['python3', os.path.join(WS, 'shared/scripts/bot_cache_refresh.py')],
            capture_output=True, text=True, timeout=15
        )
        return result.returncode == 0
    except Exception as e:
        return False

def run():
    now  = datetime.now(timezone.utc).isoformat()[:19]
    age  = get_cache_age_min()
    gate_result = {
        'as_of':           now,
        'cache_age_min':   round(age, 1),
        'max_stale_min':   MAX_STALE_MIN,
        'refresh_attempted': False,
        'gate':            'UNKNOWN',
        'action':          None,
    }

    if age <= MAX_STALE_MIN:
        # Fresh — no refresh needed
        gate_result['gate']   = 'PASS'
        gate_result['action'] = 'proceed'
    else:
        # Stale — attempt deterministic refresh
        gate_result['refresh_attempted'] = True
        refreshed = try_refresh()

        if refreshed:
            new_age = get_cache_age_min()
            if new_age <= MAX_STALE_MIN:
                gate_result['gate']            = 'PASS'
                gate_result['action']          = 'refreshed_then_proceed'
                gate_result['cache_age_after'] = round(new_age, 1)
            else:
                gate_result['gate']   = 'FAIL'
                gate_result['action'] = 'CACHE_STALE suppressing alerts'
                gate_result['reason'] = f'refresh ran but age still {new_age:.1f}min > {MAX_STALE_MIN}min'
        else:
            gate_result['gate']   = 'FAIL'
            gate_result['action'] = 'CACHE_STALE suppressing alerts'
            gate_result['reason'] = 'refresh script failed'

    print(json.dumps(gate_result))
    sys.exit(0 if gate_result['gate'] == 'PASS' else 1)

if __name__ == '__main__':
    run()
