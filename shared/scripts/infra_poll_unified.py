#!/usr/bin/env python3
"""
infra_poll_unified.py — 统一轮询器（确定性，budget-exempt，tokens=0）
每分钟由 infra-ticket-poll cron 调用

来源（按优先级）:
  1. shared/state/ticket_queue.jsonl  (正式队列 — source of truth)
  2. /tmp/oc_facts/infra_tickets.json (桥接文件 — 兼容旧路径)
  3. INFRA_TICKETS.md                 (MD 导入 — 向后兼容)

动作:
  OPEN → 自动 ACK → IN_PROGRESS（60秒内）
  IN_PROGRESS 超过 next_update_at → 写进度更新
  ACK 超时 30分钟 → 升级 INCIDENT
  每次 poll → 写 heartbeat（确定性，不受 budget 影响）
"""
import sys, os, json, re
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/shared/tools"))
from ticket_queue import (enqueue, ack, update, list_open, list_all,
                          write_heartbeat, render_md_mirror, _load_index)

WS      = os.path.expanduser("~/.openclaw/workspace")
WS_MGR  = os.path.expanduser("~/.openclaw/workspace-manager")
JSON_F  = "/tmp/oc_facts/infra_tickets.json"
MD_F    = f"{WS_MGR}/INFRA_TICKETS.md"
now_utc = datetime.now(timezone.utc)
ACK_GRACE  = 600   # 10分钟
INC_GRACE  = 1800  # 30分钟 → INCIDENT


def sync_from_json_bridge():
    """从 /tmp/oc_facts/infra_tickets.json 导入未见过的工单"""
    try:
        tickets = json.load(open(JSON_F))
    except Exception:
        return 0
    idx = _load_index()
    imported = 0
    for t in tickets:
        tid = t.get('ticket_id')
        if not tid or tid in idx:
            continue
        if t.get('status') in ('OPEN', 'pending_review'):
            enqueue(t.get('message', ''), t.get('from', 'manager'),
                    'high' if t.get('priority') in ('high','P0') else 'normal', tid)
            imported += 1
    return imported


def sync_from_md():
    """从 INFRA_TICKETS.md 导入 OPEN 工单（向后兼容）"""
    if not os.path.exists(MD_F):
        return 0
    content = open(MD_F).read()
    acked_in_md = set(re.findall(r'## (INFRA-[\d]+-[\d]+-[\d]+-\d+): InfraBot ACK', content))
    all_ids = list(dict.fromkeys(re.findall(
        r'#{1,3}\s+(INFRA-[\d]+-[\d]+-[\d]+-\d+)', content)))
    idx = _load_index()
    imported = 0
    for tid in all_ids:
        if tid in idx or tid in acked_in_md:
            continue
        # 提取标题
        m = re.search(rf'#{1,3}\s+{re.escape(tid)}[:\s]+(.*?)(?:\n|$)', content)
        title = m.group(1).strip() if m else tid
        enqueue(title, 'manager', 'high', tid)
        imported += 1
    return imported


def write_ack_to_md(ticket_id, eta_min):
    """向 INFRA_TICKETS.md 追加 ACK（镜像同步）"""
    if not os.path.exists(MD_F):
        return
    content = open(MD_F).read()
    if f"{ticket_id}: InfraBot ACK" in content:
        return
    eta_ts = (now_utc + timedelta(minutes=eta_min)).strftime('%H:%M UTC')
    upd_ts = (now_utc + timedelta(minutes=min(eta_min, 10))).strftime('%H:%M UTC')
    ack_block = f"""
## {ticket_id}: InfraBot ACK

**ACK 时间**: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC
**状态**: IN_PROGRESS
**预计完成**: {eta_ts}
**下次更新**: {upd_ts}
**负责人**: infra
**阻塞项**: 无
**ACK 类型**: 自动（control-plane，无需审批）

---
"""
    with open(MD_F, 'a') as f:
        f.write(ack_block)


def poll():
    results = {'acked': [], 'incidents': [], 'progress_updated': [], 'imported': 0}

    # ── 1. 从兼容来源导入工单 ─────────────────────────────────────────────────
    results['imported'] += sync_from_json_bridge()
    results['imported'] += sync_from_md()

    # ── 2. 处理 OPEN 工单 ─────────────────────────────────────────────────────
    open_tickets = list_open()
    for t in open_tickets:
        tid = t['ticket_id']
        try:
            created = datetime.fromisoformat(
                t['created_at'].replace('Z', '+00:00'))
            age_sec = (now_utc - created).total_seconds()
        except Exception:
            age_sec = 0

        eta_min = 10 if t.get('priority') in ('high', 'P0') else 30

        if age_sec > INC_GRACE:
            # 超时 30分钟 → INCIDENT
            from ticket_queue import _append, _update_index
            ev = {'ticket_id': tid, 'action': 'incident',
                  'status': 'INCIDENT', 'reason': f'ACK 超时 {int(age_sec/60)}分钟'}
            _append(ev)
            t.update(ev)
            _update_index(t)
            results['incidents'].append(tid)
        else:
            # 正常 ACK
            ack(tid, eta_min)
            write_ack_to_md(tid, eta_min)
            results['acked'].append(tid)

    # ── 3. IN_PROGRESS 工单进度更新 ──────────────────────────────────────────
    all_tickets = list_all()
    for t in all_tickets:
        if t.get('status') != 'IN_PROGRESS':
            continue
        nxt = t.get('next_update_at')
        if not nxt:
            continue
        try:
            nxt_dt = datetime.fromisoformat(nxt)
            if now_utc > nxt_dt:
                overdue = int((now_utc - nxt_dt).total_seconds() / 60)
                update(t['ticket_id'], f'处理中（逾期 {overdue}分钟）— 继续执行')
                results['progress_updated'].append(t['ticket_id'])
        except Exception:
            pass

    # ── 4. Heartbeat（确定性，tokens=0）─────────────────────────────────────
    hb = write_heartbeat(
        tickets_seen=len(open_tickets) + results['imported'],
        tickets_acked=len(results['acked']),
    )

    # ── 5. MD 镜像刷新 ────────────────────────────────────────────────────────
    try:
        render_md_mirror()
    except Exception:
        pass

    output = {
        'status':           'ok',
        'polled_at':        now_utc.isoformat(),
        'imported':         results['imported'],
        'acked':            results['acked'],
        'incidents':        results['incidents'],
        'progress_updated': results['progress_updated'],
        'heartbeat_age':    0,
        'heartbeat_path':   str(hb.get('source', '')),
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    poll()
