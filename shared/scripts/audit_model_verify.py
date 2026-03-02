#!/usr/bin/env python3
"""
audit_model_verify.py — Generate model evidence file after audit-daily runs
Called via exec() at end of cron payload
"""
import json, os
from datetime import datetime, timezone
from pathlib import Path

WS       = Path(os.path.expanduser("~/.openclaw/workspace"))
RUNS_DIR = Path(os.path.expanduser("~/.openclaw/cron/runs"))
OUT      = WS / "memory" / "audit_model_evidence.md"
now      = datetime.now(timezone.utc)

# Find audit-daily run file
jobs = json.load(open(Path(os.path.expanduser("~/.openclaw/cron/jobs.json"))))
j    = next((x for x in jobs['jobs'] if x['name']=='audit-daily'), None)
if not j:
    OUT.write_text("# Audit Model Evidence\nERROR: audit-daily job not found\n")
    raise SystemExit(1)

rf = RUNS_DIR / f"{j['id']}.jsonl"
if not rf.exists():
    OUT.write_text("# Audit Model Evidence\nERROR: run file missing\n")
    raise SystemExit(1)

fins = [json.loads(l) for l in open(rf) if '"finished"' in l]
if not fins:
    OUT.write_text("# Audit Model Evidence\nERROR: no finished records\n")
    raise SystemExit(1)

last   = fins[-1]
model  = last.get('model', 'UNKNOWN')
run_id = last.get('runId', last.get('id', 'N/A'))
ts     = datetime.fromtimestamp(last['ts']/1000, tz=timezone.utc)
age    = int((now - ts).total_seconds() // 60)

# Configured model
cfg      = json.load(open(Path(os.path.expanduser("~/.openclaw/openclaw.json"))))
agent    = next((a for a in cfg['agents']['list'] if a.get('id')=='audit'), {})
conf_mdl = agent.get('model',{}).get('primary','?') if isinstance(agent.get('model'),dict) else '?'

# Match check
match = model in conf_mdl
if not match:
    fb   = agent.get('model',{}).get('fallbacks',[])
    used = 'FALLBACK' if any(model in f for f in fb) else 'OVERRIDE/UNKNOWN'
else:
    used = 'PRIMARY'

evidence = f"""# Audit Model Evidence

**create**: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC
**run_at**: {ts.strftime('%H:%M:%S')} UTC ({age}min ago)
**run_id**: {run_id}

## Model selection
|  | value |
|------|-----|
| chosen_model | `{model}` |
| configured_primary | `{conf_mdl}` |
| resolution | **{used}** |
| match | {'✅ PRIMARY ' if match else '⚠️  ' + used} |

## Verdict
{'✅ PASS — Configured model ' if match else '⚠️  ' + used + ' — check root cause: degrade/fallback/provider_stop'}
"""

OUT.write_text(evidence)
print(json.dumps({
    "status": "ok", "model": model, "resolution": used,
    "match": match, "evidence": str(OUT)
}))