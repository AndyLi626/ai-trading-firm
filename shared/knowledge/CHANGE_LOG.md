# CHANGE_LOG.md — Architecture Change Audit Log
_Format: DATE | TIME | CHANGE | APPROVED BY | TESTS | RESULT_

---

## 2026-03-01

| Time | Change | Approved | Tests | Result |
|------|--------|----------|-------|--------|
| 09:00 | Initial platform: 6 agents, GCP dataset, Alpaca paper $100k | Boss | n/a | ✅ |
| 14:00 | Cron jobs: strategy-scan, media-intel-scan, manager/infra reports, audit-daily | Boss | n/a | ✅ |
| 16:00 | Crypto execution wired (BTC/ETH/SOL via Alpaca) | Boss | test_crypto 5/5 | ✅ |
| 16:30 | Options execution wired (Alpaca level-3) | Boss | test_options 3/4 | ✅ |
| 17:00 | Brave Search API + market_news.py + Twitter/XHS via Brave | Boss | test_media 11/11 | ✅ |
| 19:00 | Skills: kalshi-trading, data-analyst, agent-team-orchestration, arxiv, airadar, arc-agent-lifecycle | Boss | manual | ✅ |
| 19:05 | INCIDENT-005: secret:file ref format invalid in openclaw.json — reverted to plaintext | n/a | n/a | fixed |
| 20:00 | GCP: market_signals table, log_signal(), context_handoffs from_bot/to_bot, token_usage normalizer | Boss | gcp 15/15 | ✅ |
| 20:30 | INCIDENT-006: main session 93% → compaction timeout — timeoutSeconds 120→240s | n/a | n/a | fixed |
| 21:00 | Cron rebuild P0: collect_*.py, write_signal.py, update_cache.py, media_finalize.py | Boss | 3-cycle | ✅ |
| 22:00 | Cron prompts slimmed, absolute paths, strategy-scan timeout 180s | Boss | live verified | ✅ |

## 2026-03-02

| Time | Change | Approved | Tests | Result |
|------|--------|----------|-------|--------|
| 00:05 | INCIDENT-007: prompt-as-transport anti-pattern caused abort on Telegram heavy session | n/a | n/a | documented |
| 00:05 | InfraBot cron: 5m→12h, audit mode only, whitelist remediation only | Boss | n/a | ✅ |
| 00:10 | GOVERNANCE.md, CHANGE_LOG.md, ACL_SNAPSHOT.md, SPAWN_TEMPLATE.md created | Boss | n/a | ✅ |
| 00:10 | SOUL.md: transport rules + context-pressure guard added (INCIDENT-007 fix) | Boss | n/a | ✅ |
| 00:15 | test suite: 16 files (was 9). test_failure_chains 10/10 PASS | Boss | all pass | ✅ |
| 00:15 | ManagerBot cache contract: check_manager_cache.py, 7 required fields, cache continuation proof | Boss | check ok | ✅ |
| 00:15 | Rollback point: v0.4-pre-release @ f60d1d0 | Boss | n/a | ✅ |
| 02:48 | MediaBot routing policy: failures→InfraBot, signals→StrategyBot via GCP, summary→ManagerBot cache | Boss | pending verify | 🟡 |
| 02:48 | MediaBot agentToAgent + sessions_send tool enabled | Boss | n/a | ✅ |
| 02:48 | RELEASE_GATE.md: v0.5 push conditions, stable criteria defined | Boss | n/a | ✅ |

## 20260302T035636Z | bot=manager | result=APPLIED
- patch: {"agents.defaults.timeoutSeconds": 250}
- detail: /home/lishopping913/.openclaw/openclaw.json
