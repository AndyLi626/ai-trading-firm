#!/usr/bin/env python3
"""
no_spam_guard.py — Telegram 去重守卫
同一内容/同一 ticket 30分钟内只允许发一次
其余写入 memory/incident，不发 Telegram
"""
import json, hashlib, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

WS       = Path(os.path.expanduser("~/.openclaw/workspace"))
DEDUP_F  = WS / "shared" / "state" / "telegram_dedup.json"
INC_DIR  = WS / "memory" / "incidents"
COOLDOWN = 30  # 分钟

INC_DIR.mkdir(parents=True, exist_ok=True)

def _load():
    try:    return json.load(open(DEDUP_F))
    except: return {}

def _save(d):
    DEDUP_F.parent.mkdir(parents=True, exist_ok=True)
    json.dump(d, open(DEDUP_F,'w'), indent=2)

def can_send(content: str, ticket_id: str = None) -> dict:
    """
    返回 {'allowed': True/False, 'reason': str}
    """
    key = ticket_id or hashlib.md5(content[:200].encode()).hexdigest()[:12]
    db  = _load()
    now = datetime.now(timezone.utc)

    if key in db:
        last = datetime.fromisoformat(db[key]['last_sent'])
        age  = (now - last).total_seconds() / 60
        if age < COOLDOWN:
            # 抑制：写 incident
            _write_suppressed(key, content, int(age))
            return {'allowed': False, 'reason': f'cooldown {int(age)}/{COOLDOWN}min', 'key': key}

    # 允许发送，记录
    db[key] = {'last_sent': now.isoformat(), 'content_preview': content[:80]}
    _save(db)
    return {'allowed': True, 'reason': 'ok', 'key': key}

def _write_suppressed(key, content, age_min):
    now = datetime.now(timezone.utc)
    inc = {
        'ts':      now.isoformat(),
        'key':     key,
        'age_min': age_min,
        'suppressed_content': content[:200],
        'reason':  f'NO_SPAM: cooldown {age_min}/{COOLDOWN}min'
    }
    f = INC_DIR / f"suppressed_{now.strftime('%Y%m%d_%H%M%S')}.json"
    json.dump(inc, open(f,'w'), indent=2)

def mark_sev0_exception(content: str, ticket_id: str = None) -> bool:
    """SEV-0 直接允许（绕过冷却），但仍记录"""
    key = ticket_id or hashlib.md5(content[:200].encode()).hexdigest()[:12]
    db  = _load()
    db[key] = {
        'last_sent': datetime.now(timezone.utc).isoformat(),
        'content_preview': content[:80],
        'exception': 'SEV0'
    }
    _save(db)
    return True

if __name__ == '__main__':
    import sys
    content = sys.argv[1] if len(sys.argv) > 1 else 'test'
    tid     = sys.argv[2] if len(sys.argv) > 2 else None
    result  = can_send(content, tid)
    print(json.dumps(result))
