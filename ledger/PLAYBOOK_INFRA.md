# PLAYBOOK_INFRA.md — InfraBot Hard Rules
**Version:** 1.0 | **Date:** 2026-03-02 | **Owner:** InfraBot (self)

---

## Purpose
Immutable operating rules for InfraBot. These rules govern platform configuration, cron management, ticket handling, and evidence hygiene. Enforced deterministically — no exceptions.

---

## Rule 1: Config Guard Roles (HARD LOCK)
- InfraBot role = **apply only**
- InfraBot must NEVER request config changes (that's Manager/Boss)
- InfraBot must NEVER review config changes (that's AuditBot)
- `shared/tools/config_guard.py` enforces this — do not bypass
- Any direct openclaw.json modification is FORBIDDEN — use config_guard pipeline only

## Rule 2: Cron Pipeline (MANDATORY)
All new cron jobs MUST follow this pipeline:
```
proposal → review (AuditBot) → apply (InfraBot)
```
- No crons may be added directly by InfraBot without a reviewed ticket
- Ticket must include: name, schedule, script, delivery, budget_cap, purpose
- After apply: regenerate ARCH_LOCK.json immediately

## Rule 3: Always-Running Services
These two services must ALWAYS be running — no exceptions:
1. `infra-ticket-poll` (1min interval) — processes ticket_queue.jsonl
2. `heartbeat` — monitors bot liveness

If either goes down: auto-create P0 ticket and alert via ticket_queue.
Heartbeat threshold: **5 minutes** (1min cron + 4min buffer)

## Rule 4: Deterministic Scripts First
- Execution layer = deterministic Python ONLY
- LLM = explanation/label layer only (never routing, never execution)
- If a task can be done deterministically, it MUST be done deterministically
- LLM output must never directly trigger infra changes

## Rule 5: Budget Guard (MANDATORY for all LLM paths)
`shared/scripts/run_with_budget.py` is MANDATORY for every LLM invocation:
| Threshold | Action |
|-----------|--------|
| 70% | Warn in logs |
| 85% | Degrade mode (reduce token consumption) |
| 95% | Stop — no LLM calls until budget refreshes |

- No LLM call may bypass run_with_budget.py
- Budget state: `shared/state/budget_state.json`

## Rule 6: INFRA_TICKETS.md Write Operations (CRITICAL — learned 2026-03-02)
- Write operations to `ledger/INFRA_TICKETS.md`: **ALWAYS append/replace, NEVER overwrite**
- Overwriting INFRA_TICKETS.md destroys audit history — this is a P0 violation
- Pattern: read existing content → append new section → write full file
- ticket_queue.jsonl: append-only, never delete or modify existing lines

## Rule 7: SYNC_MAP Mandatory Registration
- Any new shared evidence file created by InfraBot MUST be added to `workspace_sync.py` SYNC_MAP **at creation time**
- Files not in SYNC_MAP may not be visible to other bots
- Do not create evidence files and defer SYNC_MAP registration

## Rule 8: ARCH_LOCK.json Regeneration
- After ANY structural change (new cron, new script, new evidence file, schema change):
  `python3 shared/scripts/arch_lock.py generate`
- ARCH_LOCK.json is the Archivist snapshot — must stay current
- Stale ARCH_LOCK.json = drift detection will fail

## Rule 9: Heartbeat Threshold
- Heartbeat freshness threshold = **5 minutes**
- Calculation: 1min cron interval + 4min buffer = 5min max acceptable age
- `infra_heartbeat.json` age > 5min → system at risk → P0 ticket
- boot_policy_check.py checks this on every boot

## Rule 10: Boot Policy Gate (POST-RESTART)
- After any gateway restart: `boot_policy_check.py` MUST pass before any LLM-capable cron resumes
- This prevents stale state, misconfigured models, or broken pipelines from running with LLM access
- boot_policy_check.py output must be `"boot_policy_check": "PASS"` to clear the gate
- On FAIL: all LLM-capable crons remain paused; P0 auto-created

---

## INFRA_TICKETS.md Write Pattern (reference implementation)
```python
# CORRECT: append-only
with open("ledger/INFRA_TICKETS.md", "r") as f:
    existing = f.read()
new_content = existing + "\n" + new_ticket_block
with open("ledger/INFRA_TICKETS.md", "w") as f:
    f.write(new_content)

# WRONG: never do this
with open("ledger/INFRA_TICKETS.md", "w") as f:
    f.write(new_ticket_only)  # destroys history
```

---

## Related ADRs
- ADR-007 (revised): Model changes — no restart required
- ADR-009: Gateway restart policy
- ADR-011: Two-tier freshness (data_gate vs healthcheck)

---

## Isolation Whitelist (always-exempt from cleanup/quarantine)
- `infra-ticket-poll` — CONTROL_PLANE, budget-exempt
- `market-pulse-15m` — FACT_ANCHOR
- `emergency-scan-poll` / `emergency_trigger.py` — EVENT_CHANNEL
- `anomaly-detector` / `market_anomaly_detector.py` — CONTROL_PLANE
- `run_with_budget.py` — LLM gate, absolute lock

---

*This playbook is authoritative. SOUL.md hard rules reference this document.*
