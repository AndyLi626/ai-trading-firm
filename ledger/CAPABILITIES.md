# System Capabilities — 2026-03-02
_Auto-generated_

## ACCOUNTING
- 🔗 **harvest_openclaw_usage** (infra) — manual/called

## BUDGET
- 🔗 **run_with_budget** (infra) — manual/called
- 🔗 **check_budget_status** (infra) — manual/called

## CRON
- 🔗 **manager-30min-report** (manager) — every 30m → `bot_cache.json`
- 🔗 **media-intel-scan** (media) — every 15m
- 🔗 **strategy-scan** (research) — every 30m
- 🔗 **audit-daily** (audit) — every 12h
- 🔗 **infra-5min-report** (main) — every 12h
- 🔗 **autonomy-orchestrator** (manager) — every 1h
- 🔗 **repo-skills-scan** (research) — every 24h
- 🔗 **infra-12h-scan** (infra) — every 12h
- 🔗 **emergency-scan-poll** (media) — every 1m
- ✅ **market-pulse-15m** (media) — every 15m → `MARKET_PULSE.json`
- 🔗 **anomaly-detector** (media) — every 5m

## DATA
- ✅ **collect_market** (research) — manual/called → `market_facts.json`
- ✅ **collect_media** (media) — manual/called → `media_facts.json`
- ✅ **collect_team** (infra) — manual/called → `team_facts.json`
- ✅ **market_pulse** (media) — manual/called → `MARKET_PULSE.json`

## DETECTION
- ✅ **market_anomaly_detector** (media) — manual/called → `anomaly_events.json`

## GOVERNANCE
- ❌ **config_guard** (infra) — manual/called

## PIPELINE
- 🔗 **detect_changes** (manager) — manual/called

## REPORTING
- ✅ **token_cost_summary** (infra) — manual/called → `cost_summary.json`

## RISK
- ✅ **risk_review_lite** (risk) — manual/called → `risk_verdict.json`

## SCAN
- ✅ **emergency_scan** (media) — manual/called → `emergency_scan_result.json`

## STRATEGY
- ✅ **strategy_hint** (research) — manual/called → `event_proposals.json`

## TRIGGER
- ✅ **emergency_trigger** (manager) — manual/called → `emergency_requests.json`
