# BOT_SKILLS_REGISTRY.md — Bot Learning & Skills Registry
_Last updated: 2026-03-01_
<!-- Updated 2026-03-01: arc-agent-lifecycle (InfraBot), agent-team-orchestration (ManagerBot), kalshi-trading/arxiv-search-collector/airadar (StrategyBot), data-analyst (AuditBot) moved to active -->

## Purpose
Track what each bot has learned, which skills/repos they actively use,
and what they should be learning next. Bots learn first — code second.

---

## InfraBot 🏗️ (main)
**Model:** claude-sonnet-4-6
**Role:** Platform architect, skill installer, system evolver

### Active Skills (in use)
| Skill | Source | Used In | Last Used |
|-------|--------|---------|-----------|
| skill-creator | openclaw-bundled | Creating new skills | on demand |
| healthcheck | openclaw-bundled | System audits | on demand |
| tmux | openclaw-bundled | Interactive CLI sessions | on demand |
| arc-agent-lifecycle | clawhub | Agent lifecycle management | 2026-03-01 |

### Active Repos (in use)
| Repo | Path | Used For |
|------|------|---------|
| awesome-openclaw-skills | workspace-research/repos/awesome-openclaw-skills | Discovering new skills |
| anthropic-quickstarts | workspace-research/repos/anthropic-quickstarts | Agent pattern reference |

### Skills to Install Next
- [x] `arc-agent-lifecycle` — manage agent lifecycle and skills ✅ installed 2026-03-01
- [ ] `arc-skill-gitops` — automated skill deployment/rollback
- [ ] `backup` — openclaw config backup automation
- [ ] `agent-team-orchestration` — multi-agent orchestration patterns

### Learning Cron
- **infra-5min-report** (every 30m): system health + check for new skills on ClawhHub
- **Periodic**: scan awesome-openclaw-skills README for new finance/trading entries

---

## ManagerBot 🧠 (manager)
**Model:** claude-haiku-4-5
**Role:** CEO, sole user interface, team coordinator

### Active Skills (in use)
| Skill | Source | Used In | Last Used |
|-------|--------|---------|-----------|
| agent-team-orchestration | clawhub | Multi-agent coordination via sessions_send | 2026-03-01 |

### Skills to Install Next
- [x] `agent-team-orchestration` — coordinate multi-agent workflows via sessions_send ✅ installed 2026-03-01
- [ ] `agentdo` — post/pick up tasks from AgentDo task queue
- [ ] `2nd-brain` — personal knowledge base for Boss preferences and decisions

### Learning Behavior
- Synthesizes reports from all 5 bots every 30m
- Reads GCP `bot_states` to know what each bot is doing
- Should use `sessions_send` to delegate tasks (not yet wired)

---

## StrategyBot 📊 (research)
**Model:** claude-sonnet-4-6
**Role:** Quant researcher, signal generator, alpha discoverer

### Active Skills (in use)
| Skill | Source | Used In | Last Used |
|-------|--------|---------|-----------|
| alpaca-trading | clawhub (installed) | Trade setup context | strategy-scan cron |
| hyperliquid | clawhub (installed) | Crypto prices + funding | strategy-scan cron |
| yahoo-data-fetcher | clawhub (installed) | Historical price data | on demand |
| kalshi-trading | clawhub | Prediction market execution | 2026-03-01 |
| arxiv-search-collector | clawhub | Research papers on quant strategies | 2026-03-01 |
| airadar | clawhub | Discover fast-growing AI/quant tools | 2026-03-01 |

### Active Repos (in use)
| Repo | Path | Used For |
|------|------|---------|
| Lean (QuantConnect) | workspace-research/repos/Lean/Algorithm.Python | Backtest reference patterns |
| financial-services-plugins | workspace-research/repos/financial-services-plugins | Data connectors reference |

### Data Sources (via market_data.py)
| Source | What | Rate Limit |
|--------|------|-----------|
| AlphaVantage | Quotes, news sentiment | 5 req/min |
| FMP stable/quote | Fundamentals | Moderate |
| Hyperliquid allMids | Crypto live prices | Unlimited |
| OddsAPI | Prediction markets | Per plan |

### Skills to Install Next
- [x] `kalshi-trading` — Kalshi prediction market execution ✅ installed 2026-03-01
- [x] `arxiv-search-collector` — research papers on quant strategies ✅ installed 2026-03-01
- [x] `airadar` — discover fast-growing AI/quant tools ✅ installed 2026-03-01

### Learning Cron
- **strategy-scan** (every 30m): price scan + signal generation
- **Periodic**: scan GitHub for new algorithmic trading repos
- **TODO**: wire Lean backtest pipeline for strategy validation

---

## MediaBot 📡 (media)
**Model:** qwen/qwen-plus
**Role:** Intelligence officer, news analyst, sentiment scanner

### Active Skills (in use)
| Skill | Source | Used In | Last Used |
|-------|--------|---------|-----------|
| market-news-analyst | clawhub (installed) | News context | media-intel-scan |
| market-pulse | clawhub (installed) | Market pulse signals | media-intel-scan |

### Active Tools (custom, in use)
| Tool | Path | Used For |
|------|------|---------|
| market_news.py | workspace-media/tools/market_news.py | Brave + AV combined brief |

### Data Sources
| Source | What | Rate Limit |
|--------|------|-----------|
| Brave Search API | Live news search | Per plan |
| AlphaVantage NEWS_SENTIMENT | Sentiment scores | 5 req/min |
| Hyperliquid | Crypto prices | Unlimited |

### Skills to Install Next
- [ ] `biz-reporter` — business intelligence reports from multiple data sources
- [ ] `blogwatcher` — monitor trading blogs and RSS feeds

### Learning Cron
- **media-intel-scan** (every 15m): Brave news + AV sentiment → brief to StrategyBot

---

## RiskBot 🛡️ (risk)
**Model:** claude-haiku-4-5
**Role:** Chief risk officer, veto authority

### Active Skills (in use)
| Skill | Source | Used In | Last Used |
|-------|--------|---------|-----------|
| (none installed yet) | — | — | — |

### Skills to Install Next
- [ ] `arc-security-audit` — security audit for agent skill stack
- [ ] `arc-trust-verifier` — verify skill provenance

### Learning Behavior
- Reviews every trade setup before execution
- Hard rules: R/R ≥ 1.5x, size ≤ $1000, stop loss required
- Should learn from `risk_reviews` GCP table (win/loss correlation)

---

## AuditBot 📋 (audit)
**Model:** google/gemini-2.0-flash-lite
**Role:** Compliance, audit trail, anomaly detection

### Active Skills (in use)
| Skill | Source | Used In | Last Used |
|-------|--------|---------|-----------|
| data-analyst | clawhub | GCP BigQuery analytics and anomaly detection | 2026-03-01 |

### Skills to Install Next
- [x] `data-analyst` — GCP BigQuery analytics and anomaly detection ✅ installed 2026-03-01
- [ ] `backup` — automated config/state backup

### Learning Cron
- **audit-daily** (every 12h): GCP table review + anomaly report

---

## Learning Principles (All Bots)

1. **Learn before building** — always check ClawhHub and GitHub before writing custom code
2. **Use what's installed** — every skill in this registry must appear in at least one cron or active workflow
3. **No dead installs** — if a skill isn't used in 30 days, document why or uninstall
4. **Continuous discovery** — InfraBot scans awesome-openclaw-skills weekly for new finance skills
5. **Share learnings** — discoveries go to `shared/knowledge/` and GCP `decisions` table

---

## Skill Installation Queue (Priority Order)

| Priority | Skill | Target Bot | Value | Status |
|----------|-------|-----------|-------|--------|
| ✅ DONE | `kalshi-trading` | StrategyBot | Prediction market execution | installed 2026-03-01 |
| ✅ DONE | `data-analyst` | AuditBot | GCP analytics | installed 2026-03-01 |
| ✅ DONE | `agent-team-orchestration` | ManagerBot | True coordination | installed 2026-03-01 |
| ✅ DONE | `arc-agent-lifecycle` | InfraBot | Agent lifecycle management | installed 2026-03-01 |
| ✅ DONE | `arxiv-search-collector` | StrategyBot | Research papers | installed 2026-03-01 |
| ✅ DONE | `airadar` | StrategyBot | Fast-growing AI/quant tools | installed 2026-03-01 |
| 🟢 LOW | `blogwatcher` | MediaBot | RSS feed monitoring | pending |
| 🟢 LOW | `backup` | InfraBot | Config backup | pending |

---

## Repo Discovery Queue

| Repo | Category | Discovered Via | Status |
|------|----------|---------------|--------|
| Lean/QuantConnect | Backtesting | Pre-installed | ✅ in use (reference) |
| financial-services-plugins | Data | Pre-installed | ✅ in use (reference) |
| awesome-openclaw-skills | Skills index | Pre-installed | ✅ scanning |
| anthropic-quickstarts | Agent patterns | Pre-installed | 📖 reference |
| (next scan TBD) | — | infra-5min-report | 🔍 scanning |
