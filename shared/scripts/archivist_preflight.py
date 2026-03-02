#!/usr/bin/env python3
"""Preflight dedup. Usage: echo '{"request":"..."}' | python3 archivist_preflight.py"""
import sys, json, os

_WS    = os.path.expanduser('~/.openclaw/workspace')
CAPS   = os.path.join(_WS, 'ledger/CAPABILITIES.md')
STATUS = os.path.join(_WS, 'ledger/STATUS_MATRIX.md')
ADRS   = os.path.join(_WS, 'ledger/ADRs')

data = json.loads(sys.stdin.read())
request = data.get('request','').lower()

# Load ledger content
caps_text   = open(CAPS).read().lower()   if os.path.exists(CAPS)   else ''
status_text = open(STATUS).read().lower() if os.path.exists(STATUS) else ''

# Keyword match
keywords = [w for w in request.split() if len(w) > 3]
caps_hits   = sum(1 for k in keywords if k in caps_text)
status_hits = sum(1 for k in keywords if k in status_text)

# Check verified status
def is_verified(kw):
    for line in (open(STATUS) if os.path.exists(STATUS) else []):
        if kw in line.lower() and '✅' in line and 'VERIFIED' in line:
            return True
    return False

# Governance trigger
cron_trigger = any(w in request for w in ['cron','job','schedule','periodic'])

# Verdict
if caps_hits >= 2 and is_verified(keywords[0] if keywords else ''):
    verdict = 'ALREADY_DONE'
    reason  = f'Capability found in CAPABILITIES.md and marked VERIFIED in STATUS_MATRIX'
    ref     = 'ledger/CAPABILITIES.md + ledger/STATUS_MATRIX.md'
elif caps_hits >= 1 or status_hits >= 1:
    verdict = 'PARTIAL'
    reason  = f'Capability exists ({caps_hits} cap hits, {status_hits} status hits) but not fully verified'
    ref     = 'ledger/STATUS_MATRIX.md — check WIRED/VERIFIED columns'
else:
    verdict = 'NEW_WORK'
    reason  = 'Not found in ledger. Requires proposal→review→validate→apply'
    ref     = 'ledger/ADRs/ADR-005-governance-flow.md'

result = {'verdict': verdict, 'reason': reason, 'ledger_ref': ref}
if cron_trigger:
    result['governance_note'] = 'CRON CHANGE DETECTED — triggers allowlist check (ADR-003) + apply_hook.py required'
print(json.dumps(result, indent=2))
