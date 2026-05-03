#!/usr/bin/env python3
"""File-backed ticket queue.

The JSONL queue is the source of truth for Infra work items. The JSON index is a
rebuildable cache of latest ticket state, and the Markdown mirror is display
only. This keeps agent-to-agent coordination deterministic and auditable.
"""
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import fcntl
except ImportError:
    # Local review on Windows should still be able to import the module. The
    # deployed OpenClaw environment is POSIX and uses real fcntl file locks.
    class _NoopFcntl:
        LOCK_EX = 0
        LOCK_UN = 0

        @staticmethod
        def flock(_file_obj, _flags):
            return None

    fcntl = _NoopFcntl()

WS = Path(os.path.expanduser("~/.openclaw/workspace"))
STATE_DIR = WS / "shared" / "state"
QUEUE_FILE = STATE_DIR / "ticket_queue.jsonl"
INDEX_FILE = STATE_DIR / "ticket_index.json"
HEARTBEAT = WS / "memory" / "infra_ticket_poller_heartbeat.json"

# Optional display-only Markdown mirror.
MD_MIRROR = Path(
    os.path.expanduser("~/.openclaw/workspace-manager/INFRA_TICKETS_MIRROR.md")
)

STATE_DIR.mkdir(parents=True, exist_ok=True)
(WS / "memory").mkdir(parents=True, exist_ok=True)

now_utc = lambda: datetime.now(timezone.utc)


# Low-level append-only event log.


def _append(event: dict):
    """Append one event to the JSONL queue."""
    event['_ts'] = now_utc().isoformat()
    line = json.dumps(event, ensure_ascii=False) + '\n'
    with open(QUEUE_FILE, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line)
        fcntl.flock(f, fcntl.LOCK_UN)


# Index management.


def _load_index() -> dict:
    try:
        return json.load(open(INDEX_FILE))
    except Exception:
        return {}

def _save_index(idx: dict):
    json.dump(idx, open(INDEX_FILE, 'w'), indent=2, ensure_ascii=False)


def _update_index(ticket: dict):
    idx = _load_index()
    idx[ticket['ticket_id']] = ticket
    _save_index(idx)
    return ticket

def rebuild_index() -> int:
    """Rebuild the latest-state index from the append-only JSONL log."""
    idx = {}
    if not QUEUE_FILE.exists():
        return 0
    for line in open(QUEUE_FILE):
        try:
            ev = json.loads(line)
            tid = ev.get('ticket_id')
            if not tid:
                continue
            action = ev.get('action', 'create')
            if action == 'create':
                idx[tid] = ev
            elif tid in idx:
                idx[tid].update({k: v for k, v in ev.items()
                                 if k not in ('action', '_ts')})
                idx[tid]['_last_event'] = ev.get('action')
        except Exception:
            pass
    _save_index(idx)
    return len(idx)


# Public API.


def enqueue(message: str, sender: str = "manager",
            priority: str = "normal", ticket_id: str = None) -> dict:
    tid = ticket_id or str(uuid.uuid4())
    eta = 10 if priority == 'high' else 30
    ticket = {
        'ticket_id':    tid,
        'action':       'create',
        'from':         sender,
        'to':           'infra',
        'message':      message,
        'priority':     priority,
        'status':       'OPEN',
        'created_at':   now_utc().isoformat(),
        'eta_min':      eta,
        'ack_deadline': (now_utc() + timedelta(minutes=10)).isoformat(),
        'history':      [{'event': 'CREATED', 'at': now_utc().isoformat(), 'by': sender}],
    }
    _append(ticket)
    _update_index(ticket)
    return ticket


def ack(ticket_id: str, eta_min: int = None) -> dict:
    idx = _load_index()
    t   = idx.get(ticket_id)
    if not t:
        return {'error': 'not_found', 'ticket_id': ticket_id}
    if t['status'] != 'OPEN':
        return t  # Already acknowledged; keep the operation idempotent.

    eta = eta_min or t.get('eta_min', 30)
    nxt = (now_utc() + timedelta(minutes=min(eta, 10))).isoformat()
    update = {
        'ticket_id':       ticket_id,
        'action':          'ack',
        'status':          'IN_PROGRESS',
        'ack_at':          now_utc().isoformat(),
        'ack_type':        'auto',
        'owner':           'infra',
        'eta_min':         eta,
        'next_update_at':  nxt,
    }
    _append(update)
    t.update(update)
    t.setdefault('history', []).append({
        'event': 'ACK', 'at': now_utc().isoformat(), 'by': 'infra',
        'detail': f'RECEIVED | ETA={eta}min | next_update={nxt[:16]}'
    })
    return _update_index(t)


def update(ticket_id: str, progress: str) -> dict:
    idx = _load_index()
    t   = idx.get(ticket_id)
    if not t:
        return {'error': 'not_found'}
    nxt = (now_utc() + timedelta(minutes=10)).isoformat()
    ev  = {'ticket_id': ticket_id, 'action': 'progress',
           'progress': progress, 'next_update_at': nxt}
    _append(ev)
    t.update({'next_update_at': nxt})
    t.setdefault('history', []).append(
        {'event': 'PROGRESS', 'at': now_utc().isoformat(), 'by': 'infra', 'detail': progress})
    return _update_index(t)


def resolve(ticket_id: str, summary: str) -> dict:
    idx = _load_index()
    t   = idx.get(ticket_id)
    if not t:
        return {'error': 'not_found'}
    ev  = {'ticket_id': ticket_id, 'action': 'resolve',
           'status': 'RESOLVED', 'resolved_at': now_utc().isoformat(), 'resolution': summary}
    _append(ev)
    t.update(ev)
    t.setdefault('history', []).append(
        {'event': 'RESOLVED', 'at': now_utc().isoformat(), 'by': 'infra', 'detail': summary})
    return _update_index(t)


def get(ticket_id: str) -> dict | None:
    return _load_index().get(ticket_id)


def list_open() -> list:
    return [t for t in _load_index().values() if t.get('status') == 'OPEN']


def list_all() -> list:
    return list(_load_index().values())


# Deterministic heartbeat; no LLM dependency.


def write_heartbeat(tickets_seen=0, tickets_acked=0, errors=None):
    hb = {
        'last_run_at':   now_utc().isoformat(),
        'tickets_seen':  tickets_seen,
        'tickets_acked': tickets_acked,
        'open_count':    len(list_open()),
        'errors':        errors or [],
        'status':        'alive',
        'source':        'ticket_queue.py',
        'next_run_in':   '60s',
    }
    json.dump(hb, open(HEARTBEAT, 'w'), indent=2)
    return hb


# Display-only Markdown mirror. Not a source of truth.


def render_md_mirror():
    tickets = sorted(list_all(), key=lambda t: t.get('created_at',''), reverse=True)
    lines = [
        "# InfraBot Ticket Queue Mirror",
        f"_Generated from `shared/state/ticket_index.json`._",
        f"_Updated: {now_utc().strftime('%Y-%m-%d %H:%M:%S')} UTC_\n",
        "| ID | Priority | Status | Created | Owner |",
        "|---|---|---|---|---|",
    ]
    for t in tickets:
        lines.append(
            f"| {t['ticket_id']} | {t.get('priority','?')} | {t.get('status','?')} "
            f"| {t.get('created_at','')[:16]} | {t.get('owner','—')} |"
        )
    lines.append("")
    for t in tickets:
        lines += [
            f"\n## {t['ticket_id']}",
            f"**Status**: {t.get('status')}  **Priority**: {t.get('priority')}",
            f"**Message**: {t.get('message','')}",
        ]
        if t.get('ack_at'):
            lines.append(f"**ACK time**: {t['ack_at'][:19]} UTC")
        if t.get('resolution'):
            lines.append(f"**Resolution**: {t['resolution']}")

    MD_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    MD_MIRROR.write_text('\n'.join(lines), encoding='utf-8')


# CLI.

if __name__ == '__main__':
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'

    if cmd == 'enqueue':
        msg  = sys.argv[2] if len(sys.argv) > 2 else 'ping'
        prio = next((sys.argv[i+1] for i,a in enumerate(sys.argv)
                     if a == '--priority' and i+1 < len(sys.argv)), 'normal')
        tid  = next((sys.argv[i+1] for i,a in enumerate(sys.argv)
                     if a == '--id' and i+1 < len(sys.argv)), None)
        print(json.dumps(enqueue(msg, 'manager', prio, tid), ensure_ascii=False))

    elif cmd == 'ack':
        tid = sys.argv[2]
        eta = int(sys.argv[3]) if len(sys.argv) > 3 else None
        print(json.dumps(ack(tid, eta), ensure_ascii=False))

    elif cmd == 'resolve':
        tid, summary = sys.argv[2], sys.argv[3]
        print(json.dumps(resolve(tid, summary), ensure_ascii=False))

    elif cmd == 'list':
        all_t = list_all()
        for t in all_t:
            print(f"  {t['ticket_id']:30s} {t.get('status'):12s} {t.get('priority','?'):4s} "
                  f"{t.get('message','')[:40]}")

    elif cmd == 'rebuild':
        n = rebuild_index()
        print(f"Rebuilt index: {n} tickets")

    elif cmd == 'mirror':
        render_md_mirror()
        print(f"Markdown mirror generated: {MD_MIRROR}")

    elif cmd == 'heartbeat':
        hb = write_heartbeat()
        print(json.dumps(hb, ensure_ascii=False))
