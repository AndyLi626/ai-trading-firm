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

## 2026-03-02 17:37 UTC — ARCH_LOCK 기준선 수립 + MARKET_PULSE 수정

### ARCH_LOCK
- `arch_lock.py generate` 실행: 67개 항목 기준선 수립
- `arch_lock.py check`: drift=0, status=clean
- 대상: cron jobs (13개) + scripts (54개)

### MARKET_PULSE freshness 수정
- **근본 원인**: `run_with_budget.py` 호출 인수 오류 (`int("python3")` ValueError)
- **수정**: 5개 whitelist cron의 payload를 직접 실행 방식으로 변경
  - market-pulse-15m, anomaly-detector, emergency-scan-poll, infra-ticket-poll, media-intel-scan
- **결과**: MARKET_PULSE age=0min (수정 전 139min)

## 2026-03-02 18:01 UTC — P0 修复 + v0.7-stable

- heartbeat 统一路径，Manager 同步对齐
- run_with_budget.py 参数 bug 修复（drift 合法，ARCH_LOCK 更新 entries=69 drift=0）  
- openclaw.json soul 键清理
- BUDGET.json: global 2M→8M, main 1.5M→2M, provider caps 新增
- Healthcheck 7/7 PASS → STABLE_RUN_CERT.md 签发
- git tag v0.7-stable

## 2026-03-02 18:03 UTC — 점진적 재개 + P0-2 근본 원인

### P0-2 모델 불일치 조사 결론
- **불일치 job**: audit-daily (17:56 UTC 실행)
- **원인**: 17:37 UTC 모델 변경 후 gateway reload 미실행 → 구 캐시(haiku) 사용
- **해결**: ADR-007 (모델 변경 → gateway reload 필수 규칙) 추가
- **ticketify**: 62fb3acf 티켓 생성 (다음 실행 gemini 확인)

### P0-1 manager-30min-report 재개
- payload: delta-only + run_with_budget 올바른 호출 (-- 구분자)
- Evidence Gate 강제: market_price/system_status → source+as_of 필수

### P0-3 ticketify 워크플로
- shared/tools/ticketify.py 배포
- 대화→JSONL 큐 enqueue + memory/proposals/ 마크다운 기록
