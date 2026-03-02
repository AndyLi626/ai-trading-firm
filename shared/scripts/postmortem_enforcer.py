#!/usr/bin/env python3
"""
postmortem_enforcer.py — Check SEV-0/1 incidents have postmortems.
Exit 0: all covered. Exit 1: missing found (tickets created).
"""
import json, os, sys, re
from datetime import datetime, timezone

TICKET_Q  = '/home/lishopping913/.openclaw/workspace/shared/state/ticket_queue.jsonl'
INCIDENT  = '/home/lishopping913/.openclaw/workspace/shared/knowledge/INCIDENT_LOG.md'
PM_DIR    = '/home/lishopping913/.openclaw/workspace/shared/knowledge/postmortems'
OUT_PATH  = '/tmp/oc_facts/postmortem_status.json'
now = datetime.now(timezone.utc)
os.makedirs(PM_DIR, exist_ok=True)
os.makedirs('/tmp/oc_facts', exist_ok=True)

# Find SEV-0/1 incidents from INCIDENT_LOG.md
sev01 = []
if os.path.exists(INCIDENT):
    content = open(INCIDENT).read()
    for m in re.finditer(r'##\s+(INCIDENT-\d+)[^\n]*\n', content):
        inc_id = m.group(1)
        context = content[m.start():m.start()+300]
        if re.search(r'SEV-[01]|sev-[01]|P0|critical', context, re.I):
            sev01.append(inc_id)
    # Also catch all incidents if no severity tags
    if not sev01:
        sev01 = re.findall(r'##\s+(INCIDENT-\d+)', content)

# Check which have postmortems
missing = []
for inc_id in sev01:
    pm_file = os.path.join(PM_DIR, f'POSTMORTEM-{inc_id}.md')
    if not os.path.exists(pm_file):
        missing.append(inc_id)
        ticket = {
            'ticket_id': f'POSTMORTEM-REQUIRED-{inc_id}',
            'status': 'OPEN', 'priority': 'high',
            'message': f'Postmortem required for {inc_id}. Run: python3 postmortem_generator.py --incident-id {inc_id}',
            'from': 'postmortem_enforcer', 'created_at': now.isoformat()
        }
        os.makedirs(os.path.dirname(TICKET_Q), exist_ok=True)
        with open(TICKET_Q, 'a') as f: f.write(json.dumps(ticket) + '\n')

result = {
    'checked_at': now.isoformat(),
    'sev01_incidents': len(sev01),
    'postmortems_written': len(sev01) - len(missing),
    'missing': missing,
    'ok': len(missing) == 0
}
json.dump(result, open(OUT_PATH,'w'), indent=2)
print(json.dumps(result))
sys.exit(1 if missing else 0)
