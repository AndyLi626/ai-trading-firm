# ARCHITECTURE.md — AI Trading Firm Platform
**Source of truth. Last updated: 2026-03-02. Do not edit manually — update via apply_hook.py.**

## Bot Roster
| Bot | Agent ID | Model (current) | Model (default) | Role |
|-----|----------|-----------------|-----------------|------|
| InfraBot | main | qwen/qwen-plus *(temp)* | anthropic/claude-sonnet-4-6 | Platform ops, audit, governance |
| ManagerBot | manager | google/gemini-2.5-flash-lite | anthropic/claude-haiku-4-5 | Boss-only interface, delta reports |
| StrategyBot | research | anthropic/claude-sonnet-4-6 | same | Market analysis, setup signals |
| MediaBot | media | qwen/qwen-plus | same | News, sentiment, social scan |
| RiskBot | risk | anthropic/claude-haiku-4-5 | same | Veto authority, trade gate |
| AuditBot | audit | google/gemini-2.5-flash-lite | same | Compliance, cost logging |

## Message Routing
- **Boss → ManagerBot only** (Telegram bot: 8206459051, Boss ID: 1555430296)
- **InfraBot → Boss** (Telegram bot: 8762207071) for system alerts only
- **Bot↔Bot**: via `bot_cache.json` reads + GCP `market_signals` table
- **No direct channels**: Boss never reaches Research/Media/Risk/Audit directly

## Language Rule
Reply in the same language as the human's last message. No exceptions. Do not mirror source material language.

## Authorized Cron Jobs (ALLOWLIST — enforced by cron_drift_enforcer.py)
| Name | Agent | Schedule | Script |
|------|-------|----------|--------|
| media-intel-scan | media | 15m | collect_media.py → media_finalize.py |
| strategy-scan | research | 30m | collect_market.py → reasoning |
| manager-30min-report | manager | 30m | collect_team.py → 4-line brief |
| infra-5min-report | main | 12h | drift_enforcer + budget_guard + audit |
| audit-daily | audit | 12h | GCP compliance log |
| daily-model-reset | main | 24h | model_override_reset.py |

Any cron not in this list → immediate disable + CRON-DRIFT ticket.

## Data Flow
```
collect_media.py → media_finalize.py → bot_cache.media + GCP market_signals
collect_market.py               → /tmp/oc_facts/market_facts.json
collect_team.py                 → /tmp/oc_facts/team_facts.json (GCP only)
data_gate.py                    → gate check on /tmp/oc_facts/MARKET_PULSE.json
write_signal.py                 → GCP market_signals
RiskBot → trading_engine.py → ExecutionService → Alpaca paper
```

## Token/Budget Three-Tier
| Mode | Threshold | Action |
|------|-----------|--------|
| ok | < 75% cap | Normal |
| warn | 75–90% | Alert only |
| degrade | 90–100% | Switch to alias model |
| stop | ≥ 100% or probe fail | Hard stop that provider |

Provider daily caps: anthropic=$1.00 · qwen=$0.50 · google=$0.30

Model aliases: `cheap_control_plane`=gemini-2.5-flash-lite · `latest_fast`=qwen-plus · `latest_reasoning`=claude-sonnet-4-6

## Data Provenance Rule (chain_id)
Every market data output must carry: `as_of` + `source` + `run_id`/`chain_id`.
Missing → `DATA_UNVERIFIED`, stop decision chain. SEV-0 if bot outputs price/% without provenance.

## Governance Flow
```
proposal → review → validate → apply → audit log (CHANGELOG.md)
```
- InfraBot auto-remediation whitelist: rerun collect_*.py, refresh /tmp/oc_facts/, clear temp cache
- Forbidden without Boss approval: cron changes, schema changes, model routing, topology changes, prompt rewrites
- Rollback: openclaw.json.bak.* + git revert

## GCP Tables (project: ai-org-mvp-001, dataset: trading_firm)
decisions · token_usage · trade_plans · risk_reviews · execution_logs · context_handoffs · bot_states · market_signals
