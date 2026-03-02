#!/usr/bin/env python3
"""
cron_drift_enforcer.py — Hard allowlist gate for cron jobs.
Run at startup and every 12h by InfraBot.
Any cron not in ALLOWLIST is immediately disabled and logged as a ticket.
Exit 0: all clean. Exit 1: violations found (but handled).
"""
import subprocess, json, sys, os
from datetime import datetime, timezone

ALLOWLIST = {
    'media-intel-scan',
    'strategy-scan',
    'manager-30min-report',
    'infra-5min-report',
    'audit-daily',
    'daily-model-reset',
    'market-pulse-refresh',
    'infra-ticket-poll',
}

TICKET_QUEUE = os.path.expanduser('~/.openclaw/workspace/shared/state/ticket_queue.jsonl')

def get_jobs():
    r = subprocess.run(["openclaw","cron","list","--json"], capture_output=True, text=True, timeout=10)
    out = r.stdout.strip(); return json.loads(out).get('jobs', []) if out else []

def disable_job(jid, name):
    r = subprocess.run(['openclaw','cron','disable', jid], capture_output=True, text=True, timeout=10)
    return json.loads(r.stdout) if r.stdout else {}

def log_ticket(name, jid):
    os.makedirs(os.path.dirname(TICKET_QUEUE), exist_ok=True)
    entry = {
        'ticket_id': f'CRON-DRIFT-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}-{name[:12]}',
        'status': 'OPEN',
        'priority': 'high',
        'message': f'Unauthorized cron detected and disabled: {name} (id={jid})',
        'from': 'cron_drift_enforcer',
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    with open(TICKET_QUEUE, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    return entry

def main():
    jobs = get_jobs()
    violations = []
    for j in jobs:
        name = j.get('name')
        jid  = j.get('id', '')
        if name not in ALLOWLIST:
            print(f'VIOLATION: {name} (id={jid}) — not in allowlist', file=sys.stderr)
            if jid:
                disable_job(jid, name)
            ticket = log_ticket(name, jid)
            violations.append({'name': name, 'id': jid, 'ticket': ticket['ticket_id']})

    result = {
        'ok': True,
        'checked_at': datetime.now(timezone.utc).isoformat(),
        'total_jobs': len(jobs),
        'violations': len(violations),
        'allowlist_size': len(ALLOWLIST),
        'details': violations,
    }
    print(json.dumps(result))
    sys.exit(1 if violations else 0)

if __name__ == '__main__':
    main()
