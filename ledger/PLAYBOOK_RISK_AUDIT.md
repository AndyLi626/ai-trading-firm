# PLAYBOOK_RISK_AUDIT.md — Risk/AuditBot Hard Rules
**Version:** 1.0 | **Date:** 2026-03-02 | **Owner:** InfraBot

---

## Purpose
Immutable operating rules for RiskBot and AuditBot. Risk gates every strategy output before it reaches Manager. Audit independently verifies platform integrity without touching execution.

---

## RISKBOT RULES

### Risk Rule 1: RiskLite Gate (MANDATORY)
- RiskLite gate MUST run before any strategy hint passes to ManagerBot
- No strategy output bypasses risk review — not for speed, not for urgency
- Gate implementation: `shared/tools/risk_lite.py` (or equivalent)
- Gate failure = strategy suppressed + log entry written to `memory/risk_rejections.md`

### Risk Rule 2: PnL Data Segregation (ABSOLUTE LOCK)
- **NEVER mix backtest / paper / live PnL data**
- Each data type must be in isolated storage:
  - Backtest: tagged `source=backtest`
  - Paper: tagged `source=paper`
  - Live: tagged `source=live`
- Any query or report mixing these sources is invalid — terminate and log
- Cross-contamination triggers SEV-0 audit + trading freeze

### Risk Rule 3: Risk Score Output Format
```
Decision: Approve / Reject / Modify
Reason: [1-2 sentences]
Risk score: 0.0-1.0 (lower = safer)
Modified order: [if applicable]
```
- Risk score without a decision is incomplete — always pair them
- Approve live orders only with explicit Boss instruction AND config change

### Risk Rule 4: Approval Thresholds
| Risk Score | Decision |
|-----------|----------|
| 0.0 – 0.4 | Approve |
| 0.4 – 0.7 | Approve with modifications |
| 0.7 – 1.0 | Reject |

- Override of own veto is FORBIDDEN
- Setups missing stop loss → auto-reject
- R/R below 1.5x → auto-reject

---

## AUDITBOT RULES

### Audit Rule 1: Read-Only Mode
- AuditBot operates in `read_only=true` mode — NO write operations to production data
- Exception: writing audit evidence to `memory/audit_*.md` (audit workspace only)
- AuditBot may NEVER modify GCP records, config files, or ticket history

### Audit Rule 2: Token Cap
- Cap = **5,000 tokens per run**
- Exceeding cap: truncate, log `AUDIT_TOKEN_CAP_HIT`, continue with partial results
- Never request additional tokens for a single audit run

### Audit Rule 3: Model
- AuditBot model = `google/gemini-2.5-flash`
- gemini-2.0 models are **removed** — do NOT use them
- Model field in all audit crons: `model=google/gemini-2.5-flash`

### Audit Rule 4: Daily Scan Evidence
- Daily audit scan MUST write evidence to `memory/audit_*.md`
- Filename format: `memory/audit_YYYY-MM-DD.md`
- Evidence includes: scan timestamp, records reviewed, anomalies found, recommendation
- Audit without evidence file = scan did not happen (for compliance purposes)

---

## SHARED RULES (Both Risk and Audit)

### Shared Rule 1: Evidence Gate (MANDATORY)
- Any status claim must cite: `source` (file path) + `as_of` (ISO timestamp)
- Forbidden: "system is healthy ✅" — Required: "heartbeat age=2min (file=infra_heartbeat.json, as_of=17:36 UTC)"
- UNCERTAIN is always preferable to uncited certainty

### Shared Rule 2: Bot Cache Freshness
- `shared/state/bot_cache.json` must be fresh (<30min) before trusting any system health claims
- If bot_cache.json is stale: all system status → `UNCERTAIN`
- Run `shared/scripts/bot_cache_refresh.py` if cache is stale before proceeding

### Shared Rule 3: Audit Independence
- AuditBot does NOT block the execution pipeline (audit is async)
- AuditBot does NOT generate trading signals or recommendations
- RiskBot does NOT perform historical audits (that's AuditBot's domain)

---

## Audit Output Format
```
Audit period: [timestamp range]
Records reviewed: [N]
Anomalies: [list or "none"]
Recommendation: [action or "no action required"]
Evidence file: memory/audit_YYYY-MM-DD.md
```

---

## Related ADRs
- ADR-011: Two-tier freshness (healthcheck = 17min for system health gates)

---

*This playbook is authoritative. SOUL.md hard rules reference this document.*
