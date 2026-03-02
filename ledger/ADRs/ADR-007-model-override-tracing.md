# ADR-007 — Model Override Tracing Rules

****: Approved
**Date**: 2026-03-02  
**Background**: audit-daily (gemini-2.0-flash) (claude-haiku-4-5)

## Cause
If Gateway is not restarted, new openclaw.json settings are not applied to running crons.
Without gateway reload after model change, stale cache causes the old model to be used.

##
1. **Model change → immediate gateway reload**
2. **Document model changes in CHANGELOG.md** ( , , Reason)
3. **Verify model= field in the next cron run** (runs/ )
4. **On mismatch detection, immediately create a ticket via ticketify()**

## Verification Method
```bash
# runs/ Verify actual model used
python3 -c "
import json, os
runs = '~/.openclaw/cron/runs'
d    = json.load(open('~/.openclaw/cron/jobs.json'))
for j in d['jobs']:
    rf = f'{runs}/{j[\"id\"]}.jsonl'
    if not os.path.exists(rf): continue
    fins = [json.loads(l) for l in open(rf) if '\"finished\"' in l]
    if fins: print(j['name'], fins[-1].get('model','?'))
"
```