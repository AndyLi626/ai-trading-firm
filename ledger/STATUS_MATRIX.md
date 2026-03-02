# STATUS_MATRIX.md — System Component Status
**更新时间: 2026-03-02T17:49Z（InfraBot 稳定化收口）**

| 功能 | EXISTS | WIRED | VERIFIED | 证据/备注 |
|------|--------|-------|----------|-----------|
| **gateway** | ✅ | ✅ | ✅ | running pid=502801, rpc probe ok |
| **token_accounting** | ✅ | ✅ | ⚠️ | gcp_client.log_token_usage() 存在; GCP 92行; status 列缺失 |
| **budget_enforcer** | ✅ | ✅ | ✅ | provider_budget_guard.py ok; hard_stop 逻辑已测 |
| **ticket_system** | ✅ | ✅ | ✅ | ticket_queue.jsonl 存在; infra-ticket-poll cron active (infra agent) |
| **data_provenance_gate** | ✅ | ✅ | ✅ | data_gate.py 存在; SOUL.md 规则已加 |
| **evidence_gate** | ✅ | ✅ | ✅ | evidence_gate.py 存在且可 import; ADR-006 归档; healthcheck 检查项 7 PASS |
| **market_pulse** | ✅ | ✅ | ✅ | market-pulse-15m cron active; MARKET_PULSE.json age=11min (17:36Z) |
| **emergency_trigger** | ✅ | ✅ | ⚠️ | emergency-scan-poll cron active (media); emergency_scan.py 路径待确认 |
| **anomaly_detector** | ✅ | ✅ | ⚠️ | anomaly-detector cron active (media); market_anomaly_detector.py 位置待确认 |
| **manager_reporting** | ✅ | ✅ | ✅ | manager-30min-report cron; delivery=announce (ADR-001 豁免) |
| **model_registry** | ✅ | ✅ | ✅ | model_aliases.json; daily-model-reset cron active |
| **budget_refresh_cmd** | ✅ | ✅ | ✅ | budget_refresh.py; /budget refresh 已实测 |
| **archivist_lock** | ✅ | ✅ | ⚠️ | ARCH_LOCK.json 67 entries; drift_count=1 (run_with_budget.py 漂移) |
| **cron_governance** | ✅ | ✅ | ✅ | 13 crons; 所有 agentId 合法; quarantine 不在 Python path |
| **cron_whitelist** | ✅ | ✅ | ✅ | LEGAL_CRON_WHITELIST.md 存在; 包含所有白名单项 |
| **language_routing** | ✅ | ✅ | ⚠️ | SOUL.md 规则 6-bot 覆盖; 最近测试 2026-03-02 |
| **GCP_market_signals** | ✅ | ✅ | ⚠️ | 表存在; 最近信号时间待确认 |
| **bot_cache_memory** | ✅ | ✅ | ⚠️ | bot_cache.json 存在; 更新时间待确认 |
| **execution_service** | ✅ | ✅ | ✅ | Alpaca paper; $100k 余额 |
| **heartbeat_poller** | ❌ | ❌ | ❌ | infra_heartbeat.json 文件不存在（workspace-manager/runtime_state/） |
| **autonomy_orchestrator** | ✅ | ✅ | ⚠️ | autonomy-orchestrator cron active; 上次 run 状态待确认 |
| **repo_skills_scan** | ✅ | ✅ | ⚠️ | repo-skills-scan cron active (24h); 上次 run 状态待确认 |
| **audit_pipeline** | ⚠️ | ⚠️ | ❌ | audit-daily cron active 但 lastRunStatus=error (gemini-2.0-flash-lite 已停用) |
| **config_validity** | ⚠️ | ✅ | ⚠️ | openclaw.json invalid (agents.list[3].soul 未识别键); gateway 仍在跑 |
| **arch_lock_drift** | ✅ | ✅ | ❌ | drift_count=1 (run_with_budget.py 哈希不匹配); 需调查 |

## 图例
✅ 已确认 · ⚠️ 部分/不确定 · ❌ 不存在/不可用

## 当前 FAIL 项（需行动）
1. **heartbeat_poller** — infra_heartbeat.json 不存在 → ticket_poller healthcheck FAIL
2. **arch_lock_drift** — run_with_budget.py 哈希漂移 → 调查后运行 arch_lock.py update 或回滚
3. **audit_pipeline** — gemini-2.0-flash-lite 已停用 → 更新 AuditBot 模型配置
4. **config_validity** — openclaw.json invalid → `openclaw doctor --fix`
