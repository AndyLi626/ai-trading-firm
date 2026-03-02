#!/usr/bin/env python3
"""
loop_guard.py —  chain_id/payload duplicate process prevent
 chain_id  payload hash 10  1 process
"""
import json, hashlib, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

WS      = Path(os.path.expanduser("~/.openclaw/workspace"))
GUARD_F = WS / "shared" / "state" / "loop_guard.json"
COOLDOWN_MIN = 10

def _load():
    try:    return json.load(open(GUARD_F))
    except: return {}

def _save(d):
    GUARD_F.parent.mkdir(parents=True, exist_ok=True)
    json.dump(d, open(GUARD_F,'w'), indent=2)

def check_and_mark(chain_id: str = None, payload: str = None) -> dict:
    """
    Returns {'allowed': bool, 'reason': str}
    """
    key = chain_id or hashlib.md5((payload or '')[:200].encode()).hexdigest()[:12]
    db  = _load()
    now = datetime.now(timezone.utc)

 #
    db = {k: v for k, v in db.items()
          if (now - datetime.fromisoformat(v['ts'])).total_seconds() < COOLDOWN_MIN * 60}

    if key in db:
        age = int((now - datetime.fromisoformat(db[key]['ts'])).total_seconds() / 60)
        return {
            'allowed': False,
            'reason':  f'LOOP_GUARD: chain_id={key} already processed {age}min ago',
            'key':     key
        }

    db[key] = {'ts': now.isoformat(), 'chain_id': chain_id, 'payload_preview': (payload or '')[:80]}
    _save(db)
    return {'allowed': True, 'reason': 'ok', 'key': key}

def mark_consumed(chain_id: str, reason: str = 'consumed'):
    db = _load()
    now = datetime.now(timezone.utc)
    db[chain_id] = {'ts': now.isoformat(), 'chain_id': chain_id, 'reason': reason}
    _save(db)

if __name__ == '__main__':
    import sys
    cid = sys.argv[1] if len(sys.argv) > 1 else 'test-chain'
    r = check_and_mark(chain_id=cid)
    print(json.dumps(r))