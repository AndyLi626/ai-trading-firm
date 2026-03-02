# AUDIT_POLICY.md — AuditBot Governance Policy
_Last updated: 2026-03-02_

---

## 1. Scheduled Audits (Every 12 Hours)

AuditBot runs a full audit at 06:00 UTC and 18:00 UTC. Each scheduled audit covers:

1. **P&L Review** — Daily/weekly realized and unrealized P&L vs. expected range
2. **Position Inventory** — Open positions, sizes, duration; flag anything held >48h unexpectedly
3. **Execution Log Review** — Scan `execution_logs` for errors, rejections, partial fills, retries
4. **Token Usage** — Review `token_usage` table; flag if daily spend exceeds $10 or any single call exceeds $2
5. **Risk Limit Compliance** — Verify all open positions are within RISK_LIMITS.md hard limits
6. **Bot State Health** — Check `bot_states` table; flag any bot offline >30 min or in error state
7. **GCP Table Freshness** — Verify tables received writes in the past 12h (data pipeline alive)
8. **INCIDENT_LOG.md Review** — Summarize open incidents; escalate stale ones (>24h unresolved)

**Output:** Write summary to `bot_states` (AuditBot row) and append to `memory/YYYY-MM-DD.md`.

---

## 2. Immediate Audit Triggers

The following events cause AuditBot to fire an out-of-schedule audit immediately:

| Trigger | Threshold |
|---|---|
| Daily loss | > $2,000 (2% of $100k account) |
| Single trade loss | > $1,000 |
| Drawdown from peak | > $5,000 (5%) |
| Consecutive failed orders | ≥ 3 in 1 hour |
| Bot offline | Any bot silent > 30 min during market hours |
| Risk limit breach | Any hard limit in RISK_LIMITS.md exceeded |
| Unexpected position | Position opened without logged trade plan |
| API error spike | ≥ 5 API errors in any 10-minute window |
| Token cost spike | Single bot burns > $5 in one session |

---

## 3. Escalation Path

```
AuditBot → ManagerBot → Human (Andy)
```

### 3.1 AuditBot Handles Autonomously
- Routine findings with no limit breaches
- Minor anomalies within expected range
- Informational summaries

### 3.2 Escalate to ManagerBot
- Any immediate audit trigger fires
- Unresolved incident > 24h
- Bot health degraded (not offline)
- Token costs trending up >50% week-over-week

### 3.3 Escalate to Human (Andy)
- Daily loss > $2,000 OR drawdown > 5%
- Any bot offline > 30 min with ManagerBot unable to resolve
- Risk limit hard breach detected
- Emergency stop triggered (see RISK_LIMITS.md)
- Two or more bots in error state simultaneously
- Unresolved escalation from ManagerBot > 2h

**How to reach Andy:** Via ManagerBot's primary channel (Telegram/webchat). Message must include: trigger, current state, recommended action.

---

## 4. INCIDENT_LOG.md — What Gets Logged vs. Discarded

**File location:** `shared/knowledge/INCIDENT_LOG.md`

### 4.1 Log to INCIDENT_LOG.md
- Any immediate audit trigger event
- Risk limit breaches (hard or soft)
- Bot failures lasting > 5 minutes
- Trade execution errors (rejected, partially filled unexpectedly)
- Escalations to Andy
- Emergency stop events
- Data pipeline outages > 15 min
- API credential failures

**Format per entry:**
```
### INCIDENT-YYYY-MM-DD-NNN
- **Time:** UTC timestamp
- **Severity:** LOW / MEDIUM / HIGH / CRITICAL
- **Bot:** Which bot detected/caused
- **Description:** What happened
- **Impact:** P&L impact if any
- **Resolution:** What was done / OPEN
- **Escalated to:** ManagerBot / Andy / None
```

### 4.2 Discard (Do Not Log)
- Routine audit summaries with no anomalies
- API rate-limit warnings that self-resolved < 1 min
- Minor data delays (< 5 min) that self-corrected
- Test/paper trading order fills during normal operation
- Duplicate audit alerts for the same already-logged event

---

## 5. Policy Ownership & Updates

- **Owner:** AuditBot (maintained by InfraBot)
- **Review cycle:** Monthly, or after any CRITICAL incident
- **Override:** Andy only; must be documented in INCIDENT_LOG.md
