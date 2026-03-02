#!/usr/bin/env python3
"""Apply hook. echo '{"change_type":"cron","description":"...","files":[],"validated":true}' | python3 apply_hook.py"""
import sys, json, os
from datetime import datetime, timezone

_WS       = os.path.expanduser('~/.openclaw/workspace')
CHANGELOG = os.path.join(_WS, 'ledger/CHANGELOG.md')
TICKET_Q  = os.path.join(_WS, 'shared/state/ticket_queue.jsonl')
ARCH_TYPES = {'cron','model','budget','schema','topology','routing','prompt'}

data = json.loads(sys.stdin.read())
change_type = data.get('change_type','')
description = data.get('description','')
files       = data.get('files', [])
validated   = data.get('validated', False)

# Gate: architecture changes require validation
if change_type in ARCH_TYPES and not validated:
    print(json.dumps({'ok': False, 'error': f'REJECTED: {change_type} change requires validated=true before apply (ADR-005)'}))
    sys.exit(1)

# Write CHANGELOG entry
now = datetime.now(timezone.utc)
entry = f"\n## [{now.strftime('%Y-%m-%d %H:%M UTC')}] {change_type.upper()}: {description}\n"
entry += f"- **Files:** {', '.join(files) or 'none'}\n"
entry += f"- **Validated:** {'✅' if validated else '⚠️ no'}\n"
entry += f"- **Rollback:** check .bak files or git log\n"

os.makedirs(os.path.dirname(CHANGELOG), exist_ok=True)
with open(CHANGELOG, 'a') as f: f.write(entry)

# Write ADR reminder ticket for rule-level changes
if change_type in {'cron','routing','budget'}:
    ticket = {'ticket_id': f'ADR-CHECK-{now.strftime("%Y%m%d%H%M%S")}',
              'status':'OPEN','priority':'normal',
              'message': f'Verify ADR compliance for {change_type} change: {description}',
              'from':'apply_hook','created_at': now.isoformat()}
    os.makedirs(os.path.dirname(TICKET_Q), exist_ok=True)
    with open(TICKET_Q,'a') as f: f.write(json.dumps(ticket)+'\n')

print(json.dumps({'ok': True, 'changelog_entry': entry.strip()[:100], 'change_type': change_type}))
