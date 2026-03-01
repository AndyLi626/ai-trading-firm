# AI Trading Firm — v0.1

> An autonomous multi-agent AI trading company built on [OpenClaw](https://openclaw.ai).  
> Six specialized bots coordinate internally like a human team. The Boss talks only to ManagerBot.

---

## Architecture Overview

```
Boss (Telegram)
    │
    ▼
ManagerBot 🎯  ←── sole human-facing interface
    │
    ├──► StrategyBot 🔬  (Alpha generation, trade plans)
    ├──► MediaBot    📡  (Market intelligence, news)
    ├──► RiskBot     🛡️  (Risk review, veto power)
    ├──► AuditBot    📋  (Logging, compliance)
    └──► ExecutionService  (Deterministic, paper/live)
              │
              ▼
         Alpaca Paper API
              │
              ▼
         GCP BigQuery (all decisions logged)

InfraBot 🏗️ (platform maintenance, wires everything together)
```

---

## The 7 Agents

| Agent | Model | Role | Trigger |
|-------|-------|------|---------|
| **ManagerBot** | claude-sonnet-4-6 | Director, Boss's only interface | Telegram |
| **StrategyBot** | claude-sonnet-4-6 | Alpha generation, trade plans | Cron 30min + on-demand |
| **MediaBot** | qwen/qwen-plus | News intelligence, sentiment | Cron 15min |
| **RiskBot** | claude-sonnet-4-6 | Risk review, absolute veto | Per trade |
| **AuditBot** | gemini-2.0-flash | GCP logging, compliance | Cron 12h |
| **ExecutionService** | *(deterministic)* | Alpaca order execution | Per approved order |
| **InfraBot** | claude-sonnet-4-6 | Platform, wiring, maintenance | Telegram |

> **Key principle:** Agents are event-driven, not always-on daemons.  
> "No active session" ≠ "not deployed". They activate on cron/message trigger.

---

## Directory Structure

```
workspace/                          # InfraBot home (this repo)
├── SOUL.md                         # InfraBot identity + mission
├── AGENTS.md                       # Operating instructions
├── GLOBAL_CONSTITUTION.md          # Hard constraints (ALL bots read this)
├── IDENTITY.md                     # Agent identity card
├── TOOLS.md                        # Local infra notes (creds, endpoints)
├── HEARTBEAT.md                    # Periodic check tasks
│
├── execution/
│   ├── execution_service.py        # Deterministic trade executor (Alpaca)
│   ├── trading_engine.py           # Multi-cycle strategy runner
│   └── config.json                 # Paper/live mode, risk limits
│
├── shared/
│   ├── tools/
│   │   └── gcp_client.py           # BigQuery client (JWT auth, all tables)
│   ├── scripts/
│   │   └── fix_execution_logs.py   # Utility: repair execution log schema
│   └── knowledge/
│       ├── risk_limits.md          # Hard risk rules
│       └── README.md
│
├── strategy/
│   ├── config.json                 # Strategy parameters
│   ├── signal_feedback_schema.json # Signal quality tracking schema
│   └── weekly_calibration_plan.md  # Strategy review cadence
│
└── runtime_state/
    ├── current_handoff.md          # Latest system state snapshot
    ├── next_master_instruction.md  # Queued directives
    ├── trading_progress.json       # Live cycle progress
    └── trading_log.jsonl           # Per-cycle trade log (excluded from git)

workspace-manager/                  # ManagerBot home
├── SOUL.md / AGENTS.md / ARCHITECTURE.md
├── COORDINATION.md                 # Delegation format + token protocol
├── shared/tools/
│   ├── gcp_client.py               # (copy from main workspace)
│   ├── load_secrets.py
│   └── team_status.py              # Real team status via GCP query
└── runtime_state/

workspace-research/                 # StrategyBot home
├── SOUL.md / AGENTS.md
├── shared/tools/
│   ├── market_data.py              # AV + FMP + OddsAPI unified client
│   └── load_secrets.py
├── skills/
│   ├── alpaca-trading/             # apcacli wrapper
│   ├── hyperliquid/                # Perps market data (read-only)
│   └── yahoo-data-fetcher/         # Yahoo Finance quotes
├── repos/
│   ├── Lean/                       # QuantConnect engine (497MB, reference)
│   ├── financial-services-plugins/ # Anthropic fin-services skills
│   ├── anthropic-quickstarts/      # Reference implementations
│   └── awesome-openclaw-skills/    # Skills discovery index
└── research/                       # Strategy outputs
    ├── backtest_results.json
    ├── strategy_recommendations.md
    ├── signal_quality.md
    └── crypto_research.md

workspace-media/                    # MediaBot home
├── SOUL.md / AGENTS.md
├── skills/
│   ├── market-news-analyst/        # News analysis skill
│   └── market-pulse/               # Market pulse skill
└── repos/
    └── worldmonitor/               # Finance/tech/world monitor

workspace-risk/                     # RiskBot home
workspace-audit/                    # AuditBot home
```

---

## Infrastructure

### Secrets
All credentials stored in `~/.openclaw/secrets/` (chmod 600, never committed):

| File | Purpose |
|------|---------|
| `anthropic_api_key.txt` | Claude (Sonnet 4-6) |
| `qwen_api_key.txt` | Qwen Plus (MediaBot) |
| `gemini_api_key.txt` | Gemini Flash (AuditBot) |
| `alpaca_paper_key.txt` + `alpaca_paper_secret.txt` | Alpaca paper trading |
| `alphavantage_api_key.txt` | Market quotes + news sentiment |
| `fmp_api_key.txt` | FMP fundamentals |
| `odds_api_key.txt` | OddsAPI (85 sports markets) |
| `coinbase_api.json` | Coinbase CDP (crypto, future) |
| `gcp-service-account.json` | BigQuery JWT auth |
| `telegram_manager_token.txt` | ManagerBot Telegram token |

Loader: `~/.openclaw/secrets/load_secrets.py`

### Market Data APIs

| API | Used For | Status |
|-----|----------|--------|
| AlphaVantage | Quotes, OHLCV, news sentiment | ✅ Live |
| FMP (stable/quote) | Fundamentals | ✅ Live |
| OddsAPI | Prediction markets (85 sports) | ✅ Live |
| Hyperliquid | Perps/spot (read-only) | ✅ Skill installed |
| Yahoo Finance | Backup quotes | ✅ Skill installed |

### Execution

| Feature | Detail |
|---------|--------|
| Broker | Alpaca |
| Mode | **Paper only** (live_enabled: false in config.json) |
| Account | PA37P8G6EG6D, $100k cash / $200k buying power |
| Endpoint | `https://paper-api.alpaca.markets/v2` |
| Upgrade path | Set `live_enabled: true` + explicit Boss approval |

### Database (GCP BigQuery)

Project: `ai-org-mvp-001` | Dataset: `trading_firm`

| Table | Purpose | Rows (v0.1) |
|-------|---------|-------------|
| `decisions` | All bot decisions, reasoning | 60 |
| `token_usage` | Per-bot token + cost tracking | 32 |
| `trade_plans` | All generated trade plans | 14 |
| `risk_reviews` | RiskBot approvals/rejections | 1 |
| `execution_logs` | Alpaca order confirmations | 12 |
| `context_handoffs` | Cross-bot handoff state | 0 |
| `bot_states` | Current team status snapshot | 7 |

### Cron Schedule

| Job | Schedule | Agent | Purpose |
|-----|----------|-------|---------|
| `media-intel-scan` | Every 15min | media | News + sentiment scan (Qwen) |
| `strategy-scan` | Every 30min | research | Alpha scan across universe |
| `infra-5min-report` | Every 5min | main | Progress reports to Boss |
| `manager-5min-report` | Every 5min | manager | Team status + cost reports |
| `audit-daily` | Every 12h | audit | GCP audit + reconciliation |

---

## Trading Engine (v0.1)

### Strategy Universe
**Equities:** SPY, QQQ, AAPL, MSFT, NVDA, TSLA, AMZN, META  
**ETFs:** GLD, TLT, IWM, XLK, XLE  
**Crypto:** BTCUSD, ETHUSD, SOLUSD *(infrastructure ready, Alpaca crypto wiring TBD)*

### Strategies Implemented

| Strategy | Signal | Direction | Stop | Target | Min R/R |
|----------|--------|-----------|------|--------|---------|
| `momentum` | Intraday change > +1.5% | Long | 1.5% | 3.0% | 2.0x |
| `mean_reversion` | Intraday change -1.2% to -5% | Long | 1.2% | 2.5% | 2.0x |
| `range_play` | Flat (-0.3% to +0.8%) | Long | 1.0% | 1.8% | 1.8x |

### Risk Rules (hardcoded in RiskBot)
- R/R ratio ≥ 1.5x (hard minimum)
- Max position size: $5,000 per order
- Min confidence threshold: 0.50
- Sentiment filter: score > -0.20 (via AlphaVantage News Sentiment)

### v0.1 Run Results (50 cycles, 2026-03-01)
- **Cycles run:** 50
- **Orders executed:** 12 (Alpaca paper, all accepted)
- **Strategy breakdown:** mean_reversion ×10, momentum ×1, range_play ×1
- **Symbols traded:** AAPL×2, MSFT×2, NVDA×2, TSLA, META, TLT, IWM, XLK, XLE
- **Total AI cost:** $0.40 (full cycle Boss→Execution→Audit)

---

## OpenClaw Configuration

Key settings in `~/.openclaw/openclaw.json`:
```json
{
  "gateway": {
    "reload": { "mode": "hybrid", "debounceMs": 500 }
  },
  "agents": {
    "list": [
      { "id": "main",     "model": "anthropic/claude-sonnet-4-6" },
      { "id": "manager",  "model": "anthropic/claude-sonnet-4-6", "tools": { "allow": ["exec",...] } },
      { "id": "research", "model": "anthropic/claude-sonnet-4-6" },
      { "id": "media",    "model": "qwen/qwen-plus" },
      { "id": "risk",     "model": "anthropic/claude-sonnet-4-6" },
      { "id": "audit",    "model": "google/gemini-2.0-flash" }
    ]
  }
}
```

**Telegram accounts:**
- `infra` account → `main` agent (`@Guiquan_bot`) ← InfraBot
- `manager` account → `manager` agent (`@AndyCorpCEO_bot`) ← ManagerBot (Boss's interface)

**Config hot-reload:** `hybrid` mode — safe changes apply instantly, no restart needed.

---

## Known Issues / Roadmap

### v0.1 Known Issues
- `risk_reviews` table only has 1 row (trading engine logs via `execution_logs` instead; schema mismatch to fix)
- `context_handoffs` table empty (cross-bot state passing not yet wired)
- ManagerBot `team_status.py` relies on GCP bot_states — states must be refreshed per-cycle
- Lean repo (497MB) cloned but not yet integrated into live strategy generation
- Crypto execution (BTCUSD/ETHUSD/SOLUSD) — Alpaca crypto endpoint not wired yet
- Options trading — infrastructure not yet built

### v0.2 Roadmap
- [ ] Wire crypto execution (Alpaca crypto API)
- [ ] Options strategy layer (Alpaca options API)
- [ ] Lean integration (backtesting pipeline → live strategy)
- [ ] Kalshi + prediction markets (OddsAPI → Kalshi trading)
- [ ] StrategyBot self-learning loop (signal_feedback_schema.json)
- [ ] Live trading mode (requires explicit Boss approval gate)
- [ ] ManagerBot cost dashboard (daily spend summary)
- [ ] Fix risk_reviews logging in trading_engine.py
- [ ] Wire context_handoffs table

---

## Quick Start

```bash
# Check system health
openclaw gateway status
openclaw agents list
openclaw cron list

# Check team status (from manager workspace)
python3 ~/.openclaw/workspace-manager/shared/tools/team_status.py

# Run a trading cycle manually
cd ~/.openclaw/workspace/execution
python3 trading_engine.py

# Query GCP for latest decisions
# (use gcp_client.py or BigQuery console)

# Talk to the Boss interface
# → Message @AndyCorpCEO_bot on Telegram
```

---

## Security

- **No secrets in code or config** — all in `~/.openclaw/secrets/` (chmod 600)
- **Paper mode only** — `live_enabled: false` hardcoded in execution config
- **RiskBot veto is absolute** — only Boss can override
- **No live trading without explicit Boss approval**
- **No secret leakage** — GLOBAL_CONSTITUTION.md enforced across all agents

---

*Built with [OpenClaw](https://openclaw.ai) · Version 0.1 · 2026-03-01*
