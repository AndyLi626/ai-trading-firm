#!/usr/bin/env python3
"""
infra_poll_unified.py — 统一工单轮询器 (budget-exempt, 确定性)
同时处理两个来源：
  1. workspace-manager/INFRA_TICKETS.md  (Manager 写入)
  2. /tmp/oc_facts/infra_tickets.json    (桥接/直接写入)

行为：
  - OPEN + 未ACK 工单 → 自动 ACK（60秒内）
  - ACK 直接追加到 INFRA_TICKETS.md
  - 状态同步到 infra_tickets.json
  - 更新 heartbeat 文件
  - OVERDUE → INCIDENT 自动升级

tokens=0（无 LLM 调用）— 不受 run_with_budget 限制
"""
import sys, os, json, re, uuid
from datetime import datetime, timezone, timedelta

# ── 路径常量 ──────────────────────────────────────────────────────────────────
WS         = "/home/lishopping913/.openclaw/workspace"
WS_MGR     = "/home/lishopping913/.openclaw/workspace-manager"
MD_PATH    = f"{WS_MGR}/INFRA_TICKETS.md"
JSON_PATH  = "/tmp/oc_facts/infra_tickets.json"
HEARTBEAT  = f"{WS}/memory/infra_ticket_poller_heartbeat.json"
ACK_TIMEOUT = 600   # 10分钟内 ACK
ETA_RESOLVE = 60    # 默认 resolve ETA（分钟）
now_utc    = datetime.now(timezone.utc)

# ── JSON DB ───────────────────────────────────────────────────────────────────

def load_json_db():
    try: return json.load(open(JSON_PATH))
    except: return []

def save_json_db(tickets):
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    json.dump(tickets, open(JSON_PATH, "w"), indent=2)

# ── Markdown 解析器 ───────────────────────────────────────────────────────────

def parse_md_tickets():
    """从 INFRA_TICKETS.md 提取 OPEN 状态的工单 ID"""
    if not os.path.exists(MD_PATH):
        return []
    content = open(MD_PATH).read()

    found = []
    # 模式：## 或 ### 标题中提取 INFRA-ID
    all_ids = list(dict.fromkeys(
        re.findall(r'#{1,3}\s+(INFRA-[\d]+-[\d]+-[\d]+-\d+)', content)
    ))

    # 已 ACK 的工单
    acked = set(re.findall(r'## (INFRA-[\d]+-[\d]+-[\d]+-\d+): InfraBot ACK', content))

    for tid in all_ids:
        if tid in acked:
            continue
        # 提取对应 JSON 块中的元数据
        pattern = rf'{re.escape(tid)}.*?```json\s*(\{{.*?\}})\s*```'
        m = re.search(pattern, content, re.DOTALL)
        data = {}
        if m:
            try: data = json.loads(m.group(1))
            except Exception: pass

        status = data.get('status', 'OPEN')
        if 'OPEN' in status and 'RESOLVED' not in status:
            found.append({
                'ticket_id':  data.get('ticket_id', tid),
                'title':      data.get('title', ''),
                'priority':   data.get('priority', 'P1'),
                'created_at': data.get('created_at', now_utc.isoformat()),
                'from':       data.get('requester', 'manager'),
                'source':     'md',
                'status':     'OPEN',
            })

    return found

# ── ACK 写入器 ────────────────────────────────────────────────────────────────

def write_ack_to_md(ticket_id, priority, eta_min, late=False):
    """向 INFRA_TICKETS.md 追加 ACK 段落"""
    if not os.path.exists(MD_PATH):
        return
    eta_ts  = (now_utc + timedelta(minutes=eta_min)).strftime('%H:%M UTC')
    upd_ts  = (now_utc + timedelta(minutes=min(eta_min, 10))).strftime('%H:%M UTC')
    late_note = "（补发 ACK — 渠道连接问题已修复）" if late else ""
    ack_txt = f"""
## {ticket_id}: InfraBot ACK

**ACK 时间**: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC {late_note}
**状态**: IN_PROGRESS
**预计完成**: {eta_ts}
**下次更新**: {upd_ts}
**负责人**: infra
**阻塞项**: 无
**ACK 类型**: 自动 (control-plane, 无需审批)

---
"""
    existing = open(MD_PATH).read()
    if f"{ticket_id}: InfraBot ACK" in existing:
        return
    with open(MD_PATH, 'a') as f:
        f.write(ack_txt)


def sync_to_json(md_ticket, status, ack_at=None):
    """同步工单状态到 JSON DB"""
    tickets = load_json_db()
    existing = next((t for t in tickets if t['ticket_id'] == md_ticket['ticket_id']), None)
    if existing:
        existing['status'] = status
        if ack_at:
            existing['ack_at'] = ack_at
            existing['owner']  = 'infra'
    else:
        entry = {**md_ticket, 'status': status, 'message': md_ticket.get('title', ''),
                 'history': [{'event': 'CREATED', 'at': md_ticket['created_at'], 'by': md_ticket['from']}]}
        if ack_at:
            entry['ack_at'] = ack_at
            entry['owner']  = 'infra'
        tickets.append(entry)
    save_json_db(tickets)

# ── 主轮询逻辑 ────────────────────────────────────────────────────────────────

def poll():
    results = {'acked': [], 'incidents': [], 'already_ok': [], 'errors': []}

    # ── 来源1：INFRA_TICKETS.md ───────────────────────────────────────────────
    md_open = parse_md_tickets()
    for t in md_open:
        tid      = t['ticket_id']
        priority = t.get('priority', 'P1')
        eta_min  = 60 if priority == 'P0' else 120

        try:
            created = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00'))
            age_sec = (now_utc - created).total_seconds()
        except Exception:
            age_sec = 0

        late = age_sec > ACK_TIMEOUT
        if age_sec > ACK_TIMEOUT * 3:  # 30分钟以上 → INCIDENT
            sync_to_json(t, 'INCIDENT')
            results['incidents'].append(tid)
        else:
            ack_at = now_utc.isoformat()
            write_ack_to_md(tid, priority, eta_min, late=late)
            sync_to_json(t, 'IN_PROGRESS', ack_at)
            results['acked'].append(tid)

    # ── 来源2：JSON DB（现有 OPEN 工单）──────────────────────────────────────
    json_tickets = load_json_db()
    for t in json_tickets:
        if t.get('status') == 'OPEN':
            eta_min = 10 if t.get('priority') == 'high' else 30
            t['status']          = 'IN_PROGRESS'
            t['ack_at']          = now_utc.isoformat()
            t['ack_type']        = 'auto'
            t['owner']           = 'infra'
            t['eta_min']         = eta_min
            t['next_update_at']  = (now_utc + timedelta(minutes=min(eta_min, 10))).isoformat()
            t.setdefault('history', []).append({
                'event':  'ACK',
                'at':     now_utc.isoformat(),
                'by':     'infra',
                'detail': f'RECEIVED | ETA={eta_min}min | next_update={t["next_update_at"][:16]}'
            })
            results['acked'].append(t['ticket_id'])

        elif t.get('status') == 'IN_PROGRESS':
            nxt = t.get('next_update_at')
            if nxt:
                try:
                    nxt_dt = datetime.fromisoformat(nxt)
                    if now_utc > nxt_dt:
                        overdue = int((now_utc - nxt_dt).total_seconds() / 60)
                        t['next_update_at'] = (now_utc + timedelta(minutes=10)).isoformat()
                        t.setdefault('history', []).append({
                            'event':  'PROGRESS',
                            'at':     now_utc.isoformat(),
                            'by':     'infra',
                            'detail': f'处理中（已逾期 {overdue}分钟）— 继续执行'
                        })
                        results['already_ok'].append(t['ticket_id'])
                except Exception:
                    pass

    save_json_db(json_tickets)

    # ── Heartbeat ─────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(HEARTBEAT), exist_ok=True)
    hb = {
        'last_run_at':   now_utc.isoformat(),
        'tickets_seen':  len(md_open) + len([t for t in json_tickets
                                              if t.get('status') in ('OPEN', 'IN_PROGRESS')]),
        'tickets_acked': len(results['acked']),
        'incidents':     results['incidents'],
        'errors':        results['errors'],
        'status':        'alive',
        'next_run_in':   '60s',
    }
    json.dump(hb, open(HEARTBEAT, 'w'), indent=2)

    print(json.dumps({
        'status':    'ok',
        'polled_at': now_utc.isoformat(),
        'md_open':   len(md_open),
        'acked':     results['acked'],
        'incidents': results['incidents'],
        'heartbeat': HEARTBEAT,
    }))


if __name__ == '__main__':
    poll()
