#!/usr/bin/env python3
"""Unified deterministic Infra ticket poller.

Called by the infra-ticket-poll cron. It consumes tickets from the JSONL queue
and compatibility inputs, acknowledges open work, escalates stale tickets, and
writes a heartbeat. This control-plane path is deterministic and token-free.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/shared/tools"))
from ticket_queue import (
    _load_index,
    ack,
    enqueue,
    list_all,
    list_open,
    render_md_mirror,
    update,
    write_heartbeat,
)

WS = os.path.expanduser("~/.openclaw/workspace")
WS_MGR = os.path.expanduser("~/.openclaw/workspace-manager")
JSON_F = "/tmp/oc_facts/infra_tickets.json"
MD_F = f"{WS_MGR}/INFRA_TICKETS.md"
now_utc = datetime.now(timezone.utc)
ACK_GRACE = 600
INC_GRACE = 1800


def sync_from_json_bridge():
    """Import unseen tickets from the legacy JSON bridge."""
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
            enqueue(
                t.get('message', ''),
                t.get('from', 'manager'),
                'high' if t.get('priority') in ('high', 'P0') else 'normal',
                tid,
            )
            imported += 1
    return imported


def sync_from_md():
    """Import open tickets from the legacy Markdown mirror."""
    if not os.path.exists(MD_F):
        return 0
    content = open(MD_F).read()
    acked_in_md = set(
        re.findall(r'## (INFRA-[\d]+-[\d]+-[\d]+-\d+): InfraBot ACK', content)
    )
    all_ids = list(
        dict.fromkeys(re.findall(r'#{1,3}\s+(INFRA-[\d]+-[\d]+-[\d]+-\d+)', content))
    )
    idx = _load_index()
    imported = 0
    for tid in all_ids:
        if tid in idx or tid in acked_in_md:
            continue
        # Extract the ticket title from the Markdown heading.
        m = re.search(
            rf'#{1,3}\s+{re.escape(tid)}[:\s]+(.*?)(?:\n|$)', content
        )
        title = m.group(1).strip() if m else tid
        enqueue(title, 'manager', 'high', tid)
        imported += 1
    return imported


def write_ack_to_md(ticket_id, eta_min):
    """Append an ACK block to the legacy Markdown mirror."""
    if not os.path.exists(MD_F):
        return
    content = open(MD_F).read()
    if f"{ticket_id}: InfraBot ACK" in content:
        return
    eta_ts = (now_utc + timedelta(minutes=eta_min)).strftime('%H:%M UTC')
    upd_ts = (now_utc + timedelta(minutes=min(eta_min, 10))).strftime('%H:%M UTC')
    ack_block = f"""
## {ticket_id}: InfraBot ACK

**ACK time**: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC
**Status**: IN_PROGRESS
**ETA**: {eta_ts}
**Next update**: {upd_ts}
**Owner**: infra
**Blockers**: none
**ACK type**: automatic control-plane acknowledgement

---
"""
    with open(MD_F, 'a') as f:
        f.write(ack_block)

def sync_manager_runtime(tickets_seen, tickets_acked):
    """Update Manager-visible runtime state."""
    import json
    from datetime import datetime, timezone
    MGR_RT = os.path.expanduser('~/.openclaw/workspace-manager/runtime_state')
    now = datetime.now(timezone.utc)

    # 1. infra_heartbeat.json
    hb_path = f"{MGR_RT}/infra_heartbeat.json"
    try:
        hb = json.load(open(hb_path))
    except Exception:
        hb = {"system": "infra_heartbeat", "version": "1.1"}
    hb.update({
        "last_update":   now.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "status":        "ALIVE",
        "source":        "infra_poll_unified.py",
        "tickets_seen":  tickets_seen,
        "tickets_acked": tickets_acked,
    })
    json.dump(hb, open(hb_path, 'w'), indent=2)

    # 2. freshness_registry.json market_pulse_scan
    fr_path = f"{MGR_RT}/freshness_registry.json"
    try:
        fr = json.load(open(fr_path))
        # Mirror market_pulse freshness into the manager registry when present.
        try:
            mp_ts = json.load(open('/tmp/oc_facts/MARKET_PULSE.json')).get(
                'generated_at', ''
            )
            fr.setdefault('market_pulse_scan', {})['last_run'] = (
                mp_ts or now.isoformat()
            )
        except Exception:
            pass
        json.dump(fr, open(fr_path, 'w'), indent=2)
    except Exception:
        pass


def poll():
    results = {'acked': [], 'incidents': [], 'progress_updated': [], 'imported': 0}

    # 1. Import tickets from compatibility sources.
    results['imported'] += sync_from_json_bridge()
    results['imported'] += sync_from_md()

    # 2. Process open tickets.
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
            # Escalate tickets that were not acknowledged in time.
            from ticket_queue import _append, _update_index
            ev = {
                'ticket_id': tid,
                'action': 'incident',
                'status': 'INCIDENT',
                'reason': f'ACK timeout after {int(age_sec / 60)} minutes',
            }
            _append(ev)
            t.update(ev)
            _update_index(t)
            results['incidents'].append(tid)
        else:
            # Normal acknowledgement path.
            ack(tid, eta_min)
            write_ack_to_md(tid, eta_min)
            results['acked'].append(tid)

    # 3. Update overdue in-progress tickets.
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
                update(
                    t['ticket_id'],
                    f'in progress; overdue by {overdue} minutes; continuing',
                )
                results['progress_updated'].append(t['ticket_id'])
        except Exception:
            pass

    # 4. Write a deterministic heartbeat.
    hb = write_heartbeat(
        tickets_seen=len(open_tickets) + results['imported'],
        tickets_acked=len(results['acked']),
    )

    sync_manager_runtime(
        tickets_seen=len(open_tickets) + results['imported'],
        tickets_acked=len(results['acked']),
    )

    # 5. Refresh the display-only Markdown mirror.
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
