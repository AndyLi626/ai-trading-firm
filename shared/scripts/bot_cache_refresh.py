#!/usr/bin/env python3
"""
bot_cache_refresh.py — Deterministic bot_cache freshness updater.
Runs every 30min. Updates metadata fields only (last_check, system_status).
Does NOT overwrite LLM-written summary fields.
Output: memory/bot_cache.json
"""
import json, os, time
from datetime import datetime, timezone

WS       = os.path.expanduser('~/.openclaw/workspace')
BC_PATH  = os.path.join(WS, 'memory/bot_cache.json')
HB_PATH  = os.path.join(WS, 'workspace-manager/runtime_state/infra_heartbeat.json')
MP_PATH  = os.path.join(WS, 'memory/market/MARKET_PULSE.json')
DQ_PATH  = os.path.join(WS, 'memory/data_quality_status.json')
TQ_PATH  = os.path.join(WS, 'shared/state/ticket_queue.jsonl')

def count_open_tickets():
    states = {}
    try:
        with open(TQ_PATH) as f:
            for line in f:
                line = line.strip()
                if not line: continue
                t = json.loads(line)
                tid = t.get('ticket_id') or t.get('id')
                if tid: states[tid] = t
        return sum(
            1 for t in states.values()
            if t.get('action') not in ('resolve',) and
               t.get('status') not in ('RESOLVED','CLOSED','CANCELLED')
        )
    except: return -1

def get_heartbeat_age():
    try:
        hb  = json.load(open(HB_PATH))
        ts  = hb.get('last_update', hb.get('timestamp',''))
        dt  = datetime.fromisoformat(ts.replace('Z','+00:00'))
        return round((datetime.now(timezone.utc) - dt).total_seconds() / 60, 1)
    except: return -1

def get_market_age():
    try:
        age = (time.time() - os.path.getmtime(MP_PATH)) / 60
        return round(age, 1)
    except: return -1

def get_data_quality():
    try:
        return json.load(open(DQ_PATH)).get('status', 'UNKNOWN')
    except: return 'UNKNOWN'

def run():
    now = datetime.now(timezone.utc).isoformat()

    # Load existing cache (preserve LLM-written summaries)
    cache = {}
    if os.path.exists(BC_PATH):
        try:
            cache = json.load(open(BC_PATH))
        except: pass

    hb_age     = get_heartbeat_age()
    mkt_age    = get_market_age()
    open_tix   = count_open_tickets()
    dq_status  = get_data_quality()

    # Only update deterministic metadata fields
    cache['_updated']        = now
    cache['_refresh_source'] = 'bot_cache_refresh.py (deterministic)'
    cache['system_health'] = {
        'heartbeat_age_min':    hb_age,
        'market_pulse_age_min': mkt_age,
        'data_quality':         dq_status,
        'open_tickets':         open_tix,
        'as_of':                now,
        'status': (
            'ok'      if hb_age >= 0 and hb_age < 5 and mkt_age < 17 else
            'warning' if hb_age < 10 and mkt_age < 20 else
            'stale'
        )
    }

    # Clear stale alarm if system is healthy
    if cache['system_health']['status'] == 'ok' and open_tix == 0:
        cache.pop('active_alarms', None)

    with open(BC_PATH, 'w') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    print(f"bot_cache refreshed: hb={hb_age}min mkt={mkt_age}min dq={dq_status} tickets={open_tix}")
    return cache['system_health']

if __name__ == '__main__':
    run()
