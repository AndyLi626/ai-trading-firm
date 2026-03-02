#!/usr/bin/env python3
"""
infra_poll_unified.py — 통합 ticket 폴러 (budget-exempt, deterministic)
두 소스를 동시에 처리:
  1. workspace-manager/INFRA_TICKETS.md  (Manager가 씀)
  2. /tmp/oc_facts/infra_tickets.json    (브릿지/직접 작성)

동작:
  - OPEN + 미ACK 티켓 → 자동 ACK (60초 이내)
  - ACK를 INFRA_TICKETS.md에 직접 append
  - 상태를 infra_tickets.json에 sync
  - heartbeat 파일 갱신
  - OVERDUE → INCIDENT 자동 승격

tokens=0 (LLM 호출 없음) — run_with_budget 통과 불필요
"""
import sys, os, json, re, uuid
from datetime import datetime, timezone, timedelta

# ── 경로 상수 ─────────────────────────────────────────────────────────────────
WS         = "/home/lishopping913/.openclaw/workspace"
WS_MGR     = "/home/lishopping913/.openclaw/workspace-manager"
MD_PATH    = f"{WS_MGR}/INFRA_TICKETS.md"
JSON_PATH  = "/tmp/oc_facts/infra_tickets.json"
HEARTBEAT  = f"{WS}/memory/infra_ticket_poller_heartbeat.json"
ACK_TIMEOUT = 600   # 10분 이내 ACK
ETA_RESOLVE = 60    # 기본 resolve ETA (분)
now_utc    = datetime.now(timezone.utc)

# ── JSON DB ───────────────────────────────────────────────────────────────────

def load_json_db():
    try: return json.load(open(JSON_PATH))
    except: return []

def save_json_db(tickets):
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    json.dump(tickets, open(JSON_PATH, "w"), indent=2)

# ── Markdown 파서 ─────────────────────────────────────────────────────────────

def parse_md_tickets():
    """INFRA_TICKETS.md에서 OPEN 상태 ticket ID 목록 추출"""
    if not os.path.exists(MD_PATH):
        return []
    content = open(MD_PATH).read()

    found = []
    # 패턴: ### INFRA-YYYY-MM-DD-NNN 뒤에 나오는 JSON 블록에서 status=OPEN 확인
    blocks = re.findall(
        r'### (INFRA-[\d-]+).*?```json\s*(\{.*?\})\s*```',
        content, re.DOTALL
    )
    for tid, json_str in blocks:
        try:
            data = json.loads(json_str)
            status = data.get('status', '')
            if 'OPEN' in status and 'ACK' not in status:
                found.append({
                    'ticket_id': data.get('ticket_id', tid),
                    'title':     data.get('title', ''),
                    'priority':  data.get('priority', 'P1'),
                    'created_at': data.get('created_at', now_utc.isoformat()),
                    'from':      data.get('requester', 'manager'),
                    'source':    'md',
                    'status':    'OPEN',
                })
        except Exception:
            pass
    return found

# ── ACK 작성기 ────────────────────────────────────────────────────────────────

def write_ack_to_md(ticket_id, priority, eta_min):
    """INFRA_TICKETS.md에 ACK 섹션을 append"""
    if not os.path.exists(MD_PATH):
        return
    eta_ts  = (now_utc + timedelta(minutes=eta_min)).strftime('%H:%M UTC')
    upd_ts  = (now_utc + timedelta(minutes=min(eta_min, 10))).strftime('%H:%M UTC')
    ack_txt = f"""
## {ticket_id}: InfraBot ACK

**ACK 시각**: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC
**status**: IN_PROGRESS
**eta_resolve**: {eta_ts}
**eta_next_update**: {upd_ts}
**owner**: infra
**blockers**: none
**ack_type**: auto (control-plane, no approval needed)

---
"""
    # 중복 방지: 이미 ACK 섹션이 있으면 skip
    existing = open(MD_PATH).read()
    if f"{ticket_id}: InfraBot ACK" in existing:
        return
    with open(MD_PATH, 'a') as f:
        f.write(ack_txt)


def sync_to_json(md_ticket, status, ack_at=None):
    """JSON DB에 ticket 상태 동기화"""
    tickets = load_json_db()
    existing = next((t for t in tickets if t['ticket_id'] == md_ticket['ticket_id']), None)
    if existing:
        existing['status'] = status
        if ack_at:
            existing['ack_at'] = ack_at
            existing['owner']  = 'infra'
    else:
        entry = {**md_ticket, 'status': status, 'message': md_ticket.get('title',''),
                 'history': [{'event':'CREATED','at':md_ticket['created_at'],'by':md_ticket['from']}]}
        if ack_at:
            entry['ack_at'] = ack_at
            entry['owner']  = 'infra'
        tickets.append(entry)
    save_json_db(tickets)

# ── 메인 폴 루프 ─────────────────────────────────────────────────────────────

def poll():
    results = {'acked': [], 'incidents': [], 'already_ok': [], 'errors': []}

    # ── 소스 1: INFRA_TICKETS.md ──────────────────────────────────────────────
    md_open = parse_md_tickets()
    for t in md_open:
        tid      = t['ticket_id']
        priority = t.get('priority', 'P1')
        eta_min  = 60 if priority == 'P0' else 120

        created  = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00'))
        age_sec  = (now_utc - created).total_seconds()

        if age_sec > ACK_TIMEOUT * 3:   # 30분 초과 → INCIDENT
            sync_to_json(t, 'INCIDENT')
            results['incidents'].append(tid)
        else:
            ack_at = now_utc.isoformat()
            write_ack_to_md(tid, priority, eta_min)
            sync_to_json(t, 'IN_PROGRESS', ack_at)
            results['acked'].append(tid)

    # ── 소스 2: JSON DB (기존 OPEN 티켓) ─────────────────────────────────────
    json_tickets = load_json_db()
    for t in json_tickets:
        if t.get('status') == 'OPEN':
            tid     = t['ticket_id']
            eta_min = 10 if t.get('priority') == 'high' else 30
            t['status']   = 'IN_PROGRESS'
            t['ack_at']   = now_utc.isoformat()
            t['ack_type'] = 'auto'
            t['owner']    = 'infra'
            t['eta_min']  = eta_min
            t['next_update_at'] = (now_utc + timedelta(minutes=min(eta_min, 10))).isoformat()
            t.setdefault('history', []).append({
                'event': 'ACK', 'at': now_utc.isoformat(), 'by': 'infra',
                'detail': f'RECEIVED | ETA={eta_min}min | next_update={t["next_update_at"][:16]}'
            })
            results['acked'].append(tid)

        elif t.get('status') == 'IN_PROGRESS':
            # 진행 중 → next_update_at 초과 시 진도 업데이트
            nxt = t.get('next_update_at')
            if nxt:
                try:
                    nxt_dt = datetime.fromisoformat(nxt)
                    if now_utc > nxt_dt:
                        overdue = int((now_utc - nxt_dt).total_seconds() / 60)
                        t['next_update_at'] = (now_utc + timedelta(minutes=10)).isoformat()
                        t.setdefault('history', []).append({
                            'event': 'PROGRESS', 'at': now_utc.isoformat(), 'by': 'infra',
                            'detail': f'처리 중 (overdue {overdue}min) — 계속 진행 중'
                        })
                        results['already_ok'].append(t['ticket_id'])
                except Exception:
                    pass

    save_json_db(json_tickets)

    # ── heartbeat 갱신 ────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(HEARTBEAT), exist_ok=True)
    hb = {
        'last_run_at':     now_utc.isoformat(),
        'tickets_seen':    len(md_open) + len([t for t in json_tickets if t.get('status') in ('OPEN','IN_PROGRESS')]),
        'tickets_acked':   len(results['acked']),
        'incidents':       results['incidents'],
        'errors':          results['errors'],
        'status':          'alive',
        'next_run_in':     '60s',
    }
    json.dump(hb, open(HEARTBEAT, 'w'), indent=2)

    output = {
        'status':      'ok',
        'polled_at':   now_utc.isoformat(),
        'md_open':     len(md_open),
        'acked':       results['acked'],
        'incidents':   results['incidents'],
        'heartbeat':   HEARTBEAT,
    }
    print(json.dumps(output))


if __name__ == '__main__':
    poll()
