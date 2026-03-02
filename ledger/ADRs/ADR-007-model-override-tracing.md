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
## Addendum (2026-03-02 21:02 UTC) — Restart Policy Clarification

**Do NOT restart gateway for routine model changes.**

- `openclaw.json` model changes take effect on the next cron execution / agent turn automatically
- Gateway restart = kills active session = user disconnect
- Restart is ONLY required when:
  1. Gateway is in a broken/crash-loop state
  2. Boss explicitly requests a restart
  3. Provider config (baseUrl, apiKey) changes require a new HTTP client

**Correct procedure for model changes:**
1. Edit `openclaw.json` (via config_guard pipeline)
2. Commit + push
3. Confirm on next cron run that `model=` field shows new value
4. DO NOT restart

ADR-009 (no restart during active session) takes precedence.
