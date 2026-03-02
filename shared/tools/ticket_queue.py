#!/usr/bin/env python3
"""
ticket_queue.py — 轻量级工单队列（JSONL + 索引）
职责: 唯一 source of truth（替代 INFRA_TICKETS.md 作为数据源）
MD 文件只作镜像展示，不参与状态机

存储:
  QUEUE_FILE  = shared/state/ticket_queue.jsonl   (追加写，不可变日志)
  INDEX_FILE  = shared/state/ticket_index.json    (最新状态索引，可重建)
  HEARTBEAT   = memory/infra_ticket_poller_heartbeat.json

API:
  enqueue(ticket_id, message, sender, priority) → ticket
  ack(ticket_id, eta_min)                        → ticket
  update(ticket_id, progress)                    → ticket
  resolve(ticket_id, summary)                    → ticket
  get(ticket_id)                                 → ticket | None
  list_open()                                    → [ticket]
  list_all()                                     → [ticket]
  rebuild_index()                                → int (entries rebuilt)
"""
import os, json, uuid, fcntl
from datetime import datetime, timezone, timedelta
from pathlib import Path

WS          = Path(os.path.expanduser("~/.openclaw/workspace"))
STATE_DIR   = WS / "shared" / "state"
QUEUE_FILE  = STATE_DIR / "ticket_queue.jsonl"
INDEX_FILE  = STATE_DIR / "ticket_index.json"
HEARTBEAT   = WS / "memory" / "infra_ticket_poller_heartbeat.json"

# MD 镜像（可选，仅展示）
MD_MIRROR   = Path(os.path.expanduser(
    "~/.openclaw/workspace-manager/INFRA_TICKETS_MIRROR.md"))

STATE_DIR.mkdir(parents=True, exist_ok=True)
(WS / "memory").mkdir(parents=True, exist_ok=True)

now_utc = lambda: datetime.now(timezone.utc)


# ── 底层写入（追加 JSONL）────────────────────────────────────────────────────

def _append(event: dict):
    """原子性追加一条事件到 JSONL 队列"""
    event['_ts'] = now_utc().isoformat()
    line = json.dumps(event, ensure_ascii=False) + '\n'
    with open(QUEUE_FILE, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(line)
        fcntl.flock(f, fcntl.LOCK_UN)


# ── 索引管理 ─────────────────────────────────────────────────────────────────

def _load_index() -> dict:
    try:    return json.load(open(INDEX_FILE))
    except: return {}

def _save_index(idx: dict):
    json.dump(idx, open(INDEX_FILE, 'w'), indent=2, ensure_ascii=False)

def _update_index(ticket: dict):
    idx = _load_index()
    idx[ticket['ticket_id']] = ticket
    _save_index(idx)
    return ticket

def rebuild_index() -> int:
    """从 JSONL 日志重建索引"""
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


# ── 公开 API ──────────────────────────────────────────────────────────────────

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
        return t  # 已 ACK，幂等

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


# ── Heartbeat（确定性，不依赖 LLM）──────────────────────────────────────────

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


# ── MD 镜像（只展示，不是 source of truth）──────────────────────────────────

def render_md_mirror():
    tickets = sorted(list_all(), key=lambda t: t.get('created_at',''), reverse=True)
    lines = [
        "# InfraBot 工单队列镜像",
        f"_自动生成 — source of truth 在 `shared/state/ticket_index.json`_",
        f"_更新时间: {now_utc().strftime('%Y-%m-%d %H:%M:%S')} UTC_\n",
        "| ID | 优先级 | 状态 | 创建时间 | 负责人 |",
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
            f"**状态**: {t.get('status')}  **优先级**: {t.get('priority')}",
            f"**内容**: {t.get('message','')}",
        ]
        if t.get('ack_at'):
            lines.append(f"**ACK时间**: {t['ack_at'][:19]} UTC")
        if t.get('resolution'):
            lines.append(f"**解决方案**: {t['resolution']}")

    MD_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    MD_MIRROR.write_text('\n'.join(lines), encoding='utf-8')


# ── CLI ───────────────────────────────────────────────────────────────────────

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
        print(f"重建索引完成: {n} 条工单")

    elif cmd == 'mirror':
        render_md_mirror()
        print(f"MD 镜像已生成: {MD_MIRROR}")

    elif cmd == 'heartbeat':
        hb = write_heartbeat()
        print(json.dumps(hb, ensure_ascii=False))
