# Evidence Paths — Source of Truth

**Established:** 2026-03-02  
**Purpose:** Authoritative paths for system health evidence. Any claim about system state MUST cite these files + as_of timestamp.

---

## Core Evidence Paths

| Signal | Path | Owner | Max Staleness |
|--------|------|-------|---------------|
| **Healthcheck** | `memory/healthcheck_YYYYMMDDTHHMMSSZ.json` | InfraBot | 30 min |
| **Heartbeat** | `~/.openclaw/workspace-manager/runtime_state/infra_heartbeat.json` | infra_poll_unified.py | 2 min |
| **Heartbeat (symlink)** | `workspace-manager/runtime_state/infra_heartbeat.json` | symlink → above | 2 min |
| **Market Pulse** | `memory/market/MARKET_PULSE.json` | market_pulse.py (15min cron) | 15 min |
| **Ticket Queue** | `shared/state/ticket_queue.jsonl` | infra_ticket.py | append-only |
| **Budget State** | `shared/knowledge/BUDGET.json` | budget_refresh.py | manual reset |
| **Bot Cache** | `memory/bot_cache.json` | update_cache.py | 30 min |
| **ARCH_LOCK** | `ledger/ARCH_LOCK.json` | arch_lock.py | on-demand |
| **Run Registry** | `shared/state/run_registry.json` | run_registry.py | per-run |

---

## Staleness Rules (Evidence Gate)

All claims about the following categories require `source` + `as_of` within the window:

| Category | Window | UNCERTAIN if |
|----------|--------|--------------|
| Market prices | 30 min | No source or as_of > 30min old |
| System status | 30 min | No file path citation |
| Model availability | per run | No cron run log evidence |
| Cost/budget | manual | No budget_state.json citation |

---

## Ticket Queue — Deduplication Note

`ticket_queue.jsonl` is **append-only**. To get actual open tickets:
1. Parse all lines, group by `ticket_id`
2. Use **latest entry per ID** as current state
3. As of 2026-03-02 20:50 UTC: **1 open** ticket (`55470d8e` — upgrade-check cron approval)

---

## Heartbeat Path Fix (2026-03-02)

healthcheck.py resolves `HEARTBEAT_PATH` relative to `WORKSPACE`:  
`~/.openclaw/workspace/workspace-manager/runtime_state/infra_heartbeat.json`

Actual file lives at:  
`~/.openclaw/workspace-manager/runtime_state/infra_heartbeat.json`

**Fix:** symlink at `workspace-manager/runtime_state/infra_heartbeat.json` → real path.  
Created: 2026-03-02 ~20:26 UTC. Do not remove.

---

## Data Quality Evidence (added 2026-03-02)

| Signal | Path | Writer | Cadence |
|--------|------|--------|---------|
| **Data Quality Status** | `memory/data_quality_status.json` | market_data_validator.py | after each pulse |
| **Data Quality Report** | `memory/data_quality_report.md` | market_data_validator.py | after each pulse |
| **Paper Account Snapshot** | `memory/paper_account_snapshot.json` | paper_account_monitor.py | 30min cron |
| **Paper PnL Daily** | `memory/paper_pnl_daily.md` | paper_account_monitor.py | 30min cron |
| **Paper PnL History** | `memory/paper_pnl_history.json` | paper_account_monitor.py | daily rollup |

### MARKET_PULSE.json — Single Source of Truth (ADR-010)
- Writer: `market_pulse.py` only (OS cron, no LLM)
- Any market price not sourced from this file = `UNCERTAIN`
- Validator: `market_data_validator.py` — `is_verified` flag is authoritative
