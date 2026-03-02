# AI Trading Firm — OpenClaw Multi-Bot Platform

> **Stable tag**: `v0.7-stable` | Healthcheck: 7/7 PASS | ARCH_LOCK: 75 entries drift=0

## Project Summary

A production-grade autonomous trading/research firm built on [OpenClaw](https://openclaw.ai).
Six specialized bots coordinate like a human team — InfraBot is the platform operator,
ManagerBot is the sole interface to Boss, and all cross-bot communication flows through
deterministic channels (file queues, JSONL tickets, facts cache).

**Not a toy**: budget governance, Evidence Gate, config_guard, drift detection, E2E smoke tests,
and a full upgrade SOP are all operational.

---

## Architecture

```
Boss (Telegram) ──► ManagerBot ──► InfraBot (tickets)
                        │
          ┌─────────────┼──────────────┐
          ▼             ▼              ▼
    ResearchBot     MediaBot       AuditBot
    (strategy)      (intel)        (daily audit)
          │
          ▼
       RiskBot (gate)
```

| Bot | Model | Role |
|-----|-------|------|
| main / InfraBot | claude-sonnet-4-6 | Platform operator, ticket polling, infra scans |
| manager / ManagerBot | gemini-2.5-flash | Boss-facing delta reports (Telegram announce) |
| research / ResearchBot | claude-sonnet-4-6 | Strategy hints, event proposals |
| media / MediaBot | qwen-plus (restricted) | Market intel, anomaly detection |
| audit / AuditBot | gemini-2.0-flash | Daily audit, model evidence |
| risk / RiskBot | claude-sonnet-4-6 | Risk gate for proposals |

**Routing rules:**
- Telegram = control-plane only. No code blobs, no large payloads
- Only `manager-30min-report` uses `delivery=announce`; all others `delivery=none`
- Bot-to-bot: file queues only (`/tmp/oc_facts/`, `shared/state/`)

---

## Core Guardrails

### Evidence Gate
Any claim about market prices, system status, model availability, or cost **must** cite
`source` + `as_of` within 30 minutes. Otherwise output `UNCERTAIN`. No `✅` without evidence.

```python
from shared.tools.evidence_gate import check
result = check({"category": "market_price", "value": "SPY=686",
                "source": "alpaca_iex", "as_of": "2026-03-02T18:00Z"})
# result["result"] == "VERIFIED" or "UNCERTAIN"
```

### ConfigCheck Pipeline
`openclaw.json` changes must go through `shared/tools/config_check.py` validation.
Roles: ManagerBot=request only, AuditBot=review only, InfraBot=apply only.

```bash
python3 shared/tools/config_check.py  # validate a patch dict
```

### Cron Allowlist + Drift Detector
All 13 cron jobs are hashed in `ledger/ARCH_LOCK.json`. Any unauthorized change is detected:

```bash
python3 shared/scripts/arch_lock.py check   # drift=0 required
python3 shared/scripts/arch_lock.py generate  # update baseline
```

### Budget Governance
`shared/knowledge/BUDGET.json`: global 8M tokens / $5 per day.
All LLM paths go through `run_with_budget.py`: 70% warn / 85% degrade / 95% stop.

```bash
python3 shared/scripts/run_with_budget.py <bot> <tokens> -- python3 <script>
```

### Ticket System
JSONL queue at `shared/state/ticket_queue.jsonl`. Manager writes via `infra_ticket_bridge.py`,
InfraBot polls every 60s. P0 tickets auto-ACK within 60s.

```bash
python3 shared/tools/ticketify.py "description" --priority high --acceptance "criteria"
```

---

## How to Run

```bash
# 1. Start gateway
openclaw gateway start

# 2. Check health
python3 shared/scripts/healthcheck.py          # 7/7 PASS required

# 3. Run E2E smoke
python3 shared/scripts/e2e_smoke.py --dry-run  # 6/6 PASS

# 4. Check cron jobs
openclaw cron list

# 5. Check budget
python3 shared/scripts/budget_refresh.py
```

**Secrets**: all tokens in `~/.openclaw/secrets/*.txt` (never committed).
**Config**: `~/.openclaw/openclaw.json` (outside git scope).

---

## Stability

Current stable tag: **`v0.7-stable`** (commit `147b238`)

7/7 healthcheck criteria:
1. `platform` — gateway running, disk < 90%
2. `ticket_poller` — heartbeat age < 2min
3. `cron_allowlist` — no announce violations, no bad agents
4. `model_runtime` — evidenced from cron runs/ files
5. `market_pulse` — age < 15min, source=alpaca_iex
6. `archivist` — ARCH_LOCK drift=0
7. `evidence_gate` — VERIFIED for fresh+sourced data

---

## Operations

| Command | What it does |
|---------|-------------|
| `python3 shared/scripts/e2e_smoke.py` | Run E2E smoke (6 scenarios, 1 Telegram summary) |
| `python3 shared/scripts/budget_refresh.py` | Refresh budget thresholds (no spend reset) |
| `python3 shared/tools/ticketify.py "<msg>"` | Convert discussion to tracked ticket |
| `python3 shared/scripts/upgrade_check.py` | Check for new OpenClaw version |
| `python3 shared/scripts/arch_lock.py check` | Check for config drift |

**ADR-009**: Never run `openclaw gateway restart` or `systemctl restart openclaw-gateway`
during an active session — it kills the session manager.

---

## Repo Layout

```
shared/
  scripts/       # All cron-executed scripts (market_pulse, strategy_hint, etc.)
  tools/         # Shared libraries (evidence_gate, config_check, ticketify, etc.)
  knowledge/     # BUDGET.json, LEGAL_CRON_WHITELIST.md, EVIDENCE_GATE_RULES.md
  state/         # ticket_queue.jsonl, run_registry.json, ticket_index.json
ledger/
  ADRs/          # Architecture Decision Records (ADR-001 to ADR-009)
  CHANGELOG.md   # All changes with timestamps
  ARCH_LOCK.json # Hash baseline for drift detection
  TEST_GATE.json # Latest test suite results
memory/
  YYYY-MM-DD.md  # Daily session logs (gitignored)
  market/        # MARKET_PULSE.json permanent path
  proposals/     # strategy proposals + ticket proposals
tests/           # test_smoke.py, test_config_guard.py, test_archivist.py, etc.
```

---

## ADR Index

| ADR | Title | Status |
|-----|-------|--------|
| ADR-001 | Token accounting via cron runs | Approved |
| ADR-002 | Delivery routing (delivery=none default) | Approved |
| ADR-003 | Unauthorized cron forbidden | Approved |
| ADR-004 | Market data architecture (Alpaca IEX + Hyperliquid) | Approved |
| ADR-005 | Emergency trigger via file (not sessions_send) | Approved |
| ADR-006 | Evidence Gate (4-category, 30min staleness) | Approved |
| ADR-007 | Model change → immediate gateway reload required | Approved |
| ADR-008 | Upgrade SOP (Proposal→Preflight→Apply→Verify→Rollback) | Approved |
| ADR-009 | No gateway restart during active session | Approved |
