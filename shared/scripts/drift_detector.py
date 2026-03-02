#!/usr/bin/env python3
"""Drift detector. Compares current state to ARCH_LOCK.json. Writes /tmp/oc_facts/drift_report.json"""
import hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
import os

LOCK_PATH = os.path.expanduser('~/.openclaw/workspace/ledger/ARCH_LOCK.json')
OUT_PATH  = '/tmp/oc_facts/drift_report.json'
TICKET_Q  = os.path.expanduser('~/.openclaw/workspace/shared/state/ticket_queue.jsonl')
QUARANTINE= os.path.expanduser('~/.openclaw/workspace/shared/scripts/quarantine')
ALIASES   = os.path.expanduser('~/.openclaw/workspace/shared/config/model_aliases.json')

def fhash(p):
    h = hashlib.sha256()
    with open(p,'rb') as f: h.update(f.read())
    return h.hexdigest()[:16]

now = datetime.now(timezone.utc)
drifts = []
os.makedirs('/tmp/oc_facts', exist_ok=True)

# 1. File hash drift
lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {'files':{}}
for path, expected in lock.get('files',{}).items():
    if expected.get('error'): continue
    try:
        current = fhash(path)
        if current != expected.get('sha256_prefix'):
            drifts.append({'type':'file_changed','path':path,'expected':expected['sha256_prefix'],'current':current})
    except FileNotFoundError:
        drifts.append({'type':'file_missing','path':path})

# 2. Unauthorized cron check
enforcer = os.path.expanduser('~/.openclaw/workspace/shared/scripts/cron_drift_enforcer.py')
r = subprocess.run(['python3', enforcer], capture_output=True, text=True, timeout=15)
try:
    cron_result = json.loads(r.stdout)
    cron_violations = cron_result.get('violations', 0)
except Exception:
    cron_violations = -1

# 3. Quarantine activity (modified in last 1h)
quar_active = False
for f in os.listdir(QUARANTINE) if os.path.exists(QUARANTINE) else []:
    mtime = os.path.getmtime(os.path.join(QUARANTINE, f))
    if time.time() - mtime < 3600:
        quar_active = True
        drifts.append({'type':'quarantine_activity','file':f,'age_minutes':round((time.time()-mtime)/60)})

# 4. Pricing completeness
pricing_ok = True
try:
    caps = json.load(open(ALIASES)).get('provider_daily_caps_usd',{})
    for p,v in caps.items():
        if not isinstance(v,(int,float)) or v <= 0:
            pricing_ok = False
            drifts.append({'type':'pricing_invalid','provider':p,'value':v})
except Exception as e:
    pricing_ok = False
    drifts.append({'type':'pricing_load_error','error':str(e)})

# Write tickets for drifts
if drifts:
    os.makedirs(os.path.dirname(TICKET_Q), exist_ok=True)
    for d in drifts:
        ticket = {'ticket_id':f'DRIFT-{now.strftime("%Y%m%d%H%M%S")}-{d["type"][:8]}',
                  'status':'OPEN','priority':'high',
                  'message':f'Drift detected: {json.dumps(d)[:200]}',
                  'from':'drift_detector','created_at':now.isoformat()}
        with open(TICKET_Q,'a') as f: f.write(json.dumps(ticket)+'\n')

result = {'checked_at':now.isoformat(),'drifts':len(drifts),'cron_violations':cron_violations,
          'quarantine_activity':quar_active,'pricing_ok':pricing_ok,'details':drifts}
json.dump(result, open(OUT_PATH,'w'), indent=2)
print(json.dumps(result))
sys.exit(1 if drifts or cron_violations > 0 else 0)