# SPAWN_TEMPLATE.md — Compact Task Template for sessions_spawn
_Created: 2026-03-02 | Enforced after INCIDENT-007_

## Rule Summary

sessions_spawn tasks must be **reference-based**, not **blob-based**.
Never inline full file contents in the task string.
Telegram → control-plane only. Large builds → Webchat or exec.

---

## Template

```
## GOAL
[One sentence: what should exist or work after this task completes]

## CONTEXT
- Workspace: /home/lishopping913/.openclaw/workspace/
- Relevant files: [list paths only — do not inline contents]
- Current state: [brief description of what exists now]

## TASKS
1. [File or component to create/modify]
   - What: [what changes]
   - Why: [reason]
   - How: [implementation approach — no code, just approach]

2. [Next file or component]
   - ...

## ACCEPTANCE CRITERIA
- [ ] [verifiable outcome 1]
- [ ] [verifiable outcome 2]
- [ ] [test command or check that confirms success]

## CONSTRAINTS
- Do not modify: [files that must not change]
- Do not call live APIs unless: [condition]
- Max files to write in one task: [number — suggest ≤5]

## OUTPUT FORMAT
STATE: done/blocked
FILES CHANGED: [list]
VALIDATION: [what was tested]
NEXT: [if anything remains]
```

---

## Context-Pressure Guard

Before spawning any subagent from Telegram, InfraBot must check:

```python
# Pseudo-check (read from /status or session metadata)
if session_tokens > 150_000:  # 75% of 200k
    # STOP — do not spawn large tasks from this session
    # Instead:
    # 1. Summarize the intent
    # 2. Tell Boss: "Switching to Webchat for this build"
    # 3. Move task to Webchat or exec path
```

**Threshold:** 150k tokens → warn. 170k tokens → hard block on large spawns.

---

## Channel Rules

| Channel | Allowed | Not Allowed |
|---------|---------|-------------|
| Telegram | Start task, status query, short directives, receive summaries | Full file content, code blobs, large markdown docs, heavy spawn payloads |
| Webchat | Everything | — |
| exec | Script runs, file writes, test execution | — |
| sessions_spawn (any channel) | Goal + references + acceptance criteria | Inlined file contents > ~200 lines |

---

## Bad vs Good Examples

### ❌ BAD (what caused INCIDENT-007)
```
task = """
## FILE 1: GOVERNANCE.md
Write /home/.../GOVERNANCE.md:
```markdown
# GOVERNANCE.md
[500 lines of full file content]
```

## FILE 2: smoke_test.py
```python
[300 lines of code]
```
...
"""
sessions_spawn(task=task)
```

### ✅ GOOD (reference-based)
```
task = """
## GOAL
Create governance + test framework for the trading firm platform.

## CONTEXT
- Workspace: /home/lishopping913/.openclaw/workspace/
- Existing tests: tests/test_*.py (9 files), tests/run_all.py
- Agents: manager, research, media, risk, audit, infra (see agents/)
- Shared tools: shared/tools/gcp_client.py, shared/scripts/collect_*.py

## TASKS
1. Create shared/knowledge/GOVERNANCE.md
   - What: Architecture change policy + audit mode rules + testing policy
   - Include: whitelist of auto-remediable actions, approval gate protocol, change categories table
   
2. Create shared/knowledge/CHANGE_LOG.md  
   - What: Audit trail of all arch changes from 2026-03-01 onward
   - Seed with known changes from memory/2026-03-01.md

3. Create tests/smoke_test.py
   - What: Post-deploy smoke test (<30s, no mocks needed)
   - Check: gateway, config, scripts, cache freshness, secrets, GCP write, Alpaca, cron jobs

## ACCEPTANCE CRITERIA
- [ ] python3 tests/smoke_test.py exits 0
- [ ] GOVERNANCE.md contains whitelist table and approval protocol
- [ ] CHANGE_LOG.md has 2026-03-01 entries

## CONSTRAINTS  
- Do not modify existing test_*.py files
- Do not call live trading APIs (Alpaca order endpoints)
"""
sessions_spawn(task=task)
```
