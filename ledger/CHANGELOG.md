# Platform Changelog
_Append-only. Each entry: date | commit | change | files_

| Date | Commit | Change | Key Files |
|------|--------|--------|-----------|
| 2026-02-xx | f60d1d0 | v0.4-pre-release rollback point | — |
| 2026-02-xx | a11f09a | v0.5-stable | config_guard, budget |
| 2026-02-xx | 76f11ee | v0.6-stable | token accounting, manager delta |
| 2026-03-02 | 380d1e4 | post-P0: detect_changes, media routing | — |
| 2026-03-02 | a5ed7be | fix: collect_team IndentationError + ManagerBot message tool | collect_team.py |
| 2026-03-02 | ac14654 | autonomy framework: orchestrator/skills_scan/infra_scan | 4 scripts |
| 2026-03-02 | c4f3a72 | token cost summary + model_pricing.json | token_cost_summary.py |
| 2026-03-02 | c2951b6 | P0: market_pulse+anomaly_detector Tier0 | watchlist.json |
| 2026-03-02 | 4ebb10f | P1: strategy_hint+risk_review_lite+Event Loop | 2 scripts |
| 2026-03-02 | `d77631f9` | P1 Archivist: changelog hook + test_gate + bot_cache.archivist | archivist_apply_hook.py, test_gate.py, ARCH_LOCK.json |
| 2026-03-02 | `fc52f3d2` | P0: infra_ticket通道+source_health+Manager投递修复 | infra_ticket.py, source_health.py, jobs.json |
| 2026-03-02 | `c6d3dc3d` | feat: run_registry — job运行事实源 + 5脚本写入钩子 + Manager查询入口 | run_registry.py, market_pulse.py, emergency_scan.py |

## [2026-03-02 15:16 UTC] CRON: Add market-pulse-refresh cron: runs market_pulse.py every 15m to keep MARKET_PULSE.json fresh for data_gate
- **Files:** shared/scripts/market_pulse.py
- **Validated:** ✅
- **Rollback:** check .bak files or git log

## [2026-03-02 15:17 UTC] CRON: Restore infra-ticket-poll: deterministic control-plane poller, 0 LLM, tokens=0, was mistakenly deleted during unauthorized cron cleanup
- **Files:** shared/scripts/infra_poll_unified.py
- **Validated:** ✅
- **Rollback:** check .bak files or git log

## 2026-03-02 17:37 UTC — ARCH_LOCK Baseline + MARKET_PULSE fixed

### ARCH_LOCK
- `arch_lock.py generate` : 67 entries Baseline
- `arch_lock.py check`: drift=0, status=clean
- : cron jobs (13) + scripts (54)

### MARKET_PULSE freshness fixed
- ** Cause**: `run_with_budget.py` Error (`int("python3")` ValueError)
- **fixed**: 5 whitelist cron payload Method
  - market-pulse-15m, anomaly-detector, emergency-scan-poll, infra-ticket-poll, media-intel-scan
- **Result**: MARKET_PULSE age=0min (fixed 139min)

## 2026-03-02 18:01 UTC — P0 修复 + v0.7-stable

- heartbeat 统一路径，Manager 同步对齐
- run_with_budget.py 参数 bug 修复（drift 合法，ARCH_LOCK 更新 entries=69 drift=0）  
- openclaw.json soul 键清理
- BUDGET.json: global 2M→8M, main 1.5M→2M, provider caps 新增
- Healthcheck 7/7 PASS → STABLE_RUN_CERT.md 签发
- git tag v0.7-stable

## 2026-03-02 18:03 UTC — Gradual rollout + P0-2 Cause

### P0-2 Model mismatch investigation conclusion
- **Mismatched job**: audit-daily (17:56 UTC )
- **Cause**: 17:37 UTC gateway reload → (haiku)
- **Fix**: ADR-007 ( → gateway reload ) added
- **ticketify**: 62fb3acf ( gemini )

### P0-1 manager-30min-report
- payload: delta-only + run_with_budget (-- )
- Evidence Gate : market_price/system_status → source+as_of

### P0-3 ticketify
- shared/tools/ticketify.py
- →JSONL enqueue + memory/proposals/
## 2026-03-02 20:04 UTC — docs: normalize language to English + update README

- Translated all Korean comments/docs to English (34 files scanned, scripts+ADRs+memory docs)
- Skip list: memory/2026-03-02.md (personal log), memory/proposals/ticket_*.md (auto-generated)
- New README: architecture diagram, 6-bot roles, Evidence Gate, ConfigCheck, Budget,
  Ticket system, How-to-Run, Stability (v0.7-stable), Operations, Repo Layout, ADR Index
- memory/i18n_korean_inventory.md: full file list
- memory/token_security_report.md: tokens safe (outside git), Boss action required for env vars
- memory/readme_update_summary.md: section-by-section changelog

## 2026-03-02 20:35 UTC — fix: security hardening + path portability

### Issues Resolved
1. MARKET_PULSE stale (119min) → refreshed directly; cron confirmed running ✅
2. heartbeat file missing → workspace-manager/runtime_state/ symlink created; 7/7 healthcheck restored ✅
3. runtime_state/ files removed from git tracking (5 files: RELEASE_GATE, handoff, instruction, rollback, progress) ✅
4. Telegram Boss ID 1555430296 redacted → ${BOSS_TELEGRAM_ID} in SOUL.md, ADR-008, ARCHITECTURE.md, e2e_smoke.py ✅
5. /home/lishopping913/ hardcoded paths → os.path.expanduser('~/.openclaw/...') in 51 files (0 syntax errors) ✅
6. cron jobs.json 13 payloads: absolute paths → ~/.openclaw/workspace ✅
7. {datetime} template not substituted in memoryFlush.prompt → removed unsupported placeholder ✅

### Security Status
- git tracked files: 0 API keys, 0 hardcoded paths, 0 personal identifiers
- runtime_state/ now gitignored
- openclaw.json: outside git scope (safe)
- secrets/: gitignored (safe)

## 2026-03-02 20:42 UTC — config: raise memoryFlush.softThresholdTokens 4000→80000

- ConfigCheck: APPLY_ALLOWED
- softThresholdTokens: 4000 → 80000 (reduces flush frequency ~20x)
- prompt: shortened to single line
- Reason: flush triggered too frequently at 4000 tokens, flooding webchat UI
- Gateway restart required to pick up new config

## 2026-03-02 21:00 UTC — model: StrategyBot (research) → openai/gpt-5.2

ConfigCheck: APPLY_ALLOWED
- Registered OpenAI provider (models.providers.openai)
  - models: gpt-5.2, gpt-4o, o3
- research agent model: claude-sonnet-4-6 → openai/gpt-5.2
  - fallbacks: claude-sonnet-4-6, gemini-2.5-flash
- ADR-007: gateway restart required after model change

## 2026-03-02 21:01 UTC — model: manager → openai/gpt-5.2

ConfigCheck: APPLY_ALLOWED
- manager agent: gemini-2.5-flash → openai/gpt-5.2
  fallbacks: gemini-2.5-flash, claude-sonnet-4-6
- research agent: confirmed openai/gpt-5.2 (set in previous cycle)
- ADR-007: gateway restart required

## 2026-03-02 21:12 UTC — cron: add paper-account-monitor + market-data-validator

ConfigCheck: APPLY_ALLOWED (Boss approved)
- paper-account-monitor: every 30min, agent=main, delivery=none, 0 LLM
  output: memory/paper_account_snapshot.json + memory/paper_pnl_daily.md
- market-data-validator: every 15min (+2min after market-pulse-15m), agent=main, delivery=none, 0 LLM
  output: memory/data_quality_status.json + memory/data_quality_report.md
Total cron jobs: 15

## 2026-03-02 21:20 UTC — ops: credit restored + config fixes + cron + telegram

1. Anthropic credit recharged — apiKey restored to auth.profiles.anthropic:default ✅
2. gemini-2.0-flash-lite removed by Boss — Google models now: gemini-2.5-flash, gemini-2.5-pro ✅
3. env_var issue: OpenClaw does not expand ${VAR} in config — keys must be plaintext.
   Restored all provider apiKeys from secrets/. openclaw.json is outside git (safe).
4. upgrade-check cron applied (ticket 55470d8e approved): weekly, delivery=none ✅
5. Telegram groupAllowFrom=[1555430296] added to infra + manager accounts ✅
6. Token counter: NOT reset. Boss decision pending (current spend: Anthropic 8.6%, Qwen 4.8%, Google 3.2%)
