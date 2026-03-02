# Incident Log — 2026-03-01

## 事故汇总 + 防范规则

---

### INC-001: SecretRef 格式错误导致双 bot 断连
**时间:** 19:05 UTC  
**严重度:** P0 — 两个 Telegram bot 全断，主 session 超时卡死  

**根因:**  
InfraBot 尝试将 botToken 改为 `secret:file:/path/to/file` 字符串格式，OpenClaw 不支持此格式，将其当普通字符串传给 Telegram API → 404/401 → manager channel 反复 crash → 409 冲突循环。

**规则:**  
❌ 永远不要将 `botToken` 或 `apiKey` 改为任何非字符串格式  
❌ `secret:file:...` 不是有效的 OpenClaw SecretRef（只在 openclaw secrets apply 流程里使用对象格式）  
✅ `botToken` 和 `model.apiKey` 必须是明文字符串

---

### INC-002: 双 Gateway 进程 409 冲突
**时间:** 19:10-19:35 UTC  
**严重度:** P1 — ManagerBot 持续断连

**根因:**  
`liguiquan` 用户和 `<user-B>` 用户各自运行了一个 openclaw-gateway，同时使用同一个 ManagerBot token 轮询 Telegram → 409 Conflict。

**排查命令:**  
```bash
ps aux | grep openclaw | grep -v grep
```
**规则:**  
- 同一台机器上同一个 bot token 只能有一个 gateway 进程
- 发现 409 立刻检查是否有多进程

---

### INC-003: strategy-scan / 主 session 超时卡死
**时间:** 19:16 UTC  
**严重度:** P2 — 请求超时，无响应

**根因:**  
1. `agents.defaults.timeoutSeconds` 未设置（默认过低）
2. INC-002 的 channel crash 占用并发资源
3. strategy-scan cron 无独立 timeout，长时间 API 调用阻塞

**修复:**  
- `timeoutSeconds = 60`（agent 级）
- 各 cron job 单独设置 `--timeout-seconds 60/90`
- `maxRetries = 2`（防止无限重试烧 token）

---

### INC-004: Gateway 重启丢失 tool result
**时间:** 17:55 UTC  
**严重度:** P3 — 回复延迟，session 修复

**根因:**  
手动 `openclaw gateway restart` 时，正在执行的 tool call 结果丢失，OpenClaw 插入 synthetic error 修复 transcript。

**修复:**  
`gateway.reload.mode = "hybrid"` — 安全变更热加载，无需手动重启  
**规则:**  
❌ 不要手动 `openclaw gateway restart`（除非 gateway 完全挂死）  
✅ 修改 openclaw.json 后等待热加载自动生效（~500ms debounce）

---

### INC-005: ManagerBot 误判团队状态
**时间:** 整天  
**严重度:** P2 — ManagerBot 持续报告"其他 bot 未部署"

**根因:**  
ManagerBot 用 `sessions_list` 判断 bot 是否在线，但 OpenClaw agents 是事件驱动的，空闲时没有活跃 session。

**修复:**  
- 新建 `team_status.py` 查询 GCP bot_states 表
- 重写 AGENTS.md，明确禁止用 sessions_list 判断状态
- `tools.sessions.visibility = all`

---

## 防范配置（已生效）

```json
{
  "agents": {
    "defaults": {
      "timeoutSeconds": 60,
      "maxRetries": 2,
      "maxConcurrent": 3,
      "subagents": { "maxConcurrent": 4 },
      "compaction": {
        "mode": "safeguard",
        "targetTokens": 80000,
        "minFreeTokens": 20000
      }
    }
  },
  "gateway": {
    "reload": { "mode": "hybrid", "debounceMs": 500 }
  },
  "cron": {
    "defaultBestEffortDeliver": true
  }
}
```

## 黄金规则

1. **botToken / apiKey 只用明文字符串**，不用任何引用格式
2. **不手动 restart gateway**，改 config 等热加载
3. **不用 sessions_list 判断 bot 状态**，用 team_status.py + GCP
4. **发现 409 立查双进程**: `ps aux | grep openclaw`
5. **cron 失败不阻塞**: `bestEffortDeliver: true`，`maxRetries: 2`

---

## INCIDENT-006 — 2026-03-01 20:32 UTC
**Type:** Repeated session timeout during compaction
**Symptom:** `Request was aborted` / `embedded run timeout: timeoutMs=120000`
**Root Cause (confirmed via logs):**
- Main session hit 185k/200k tokens (93% full)
- `compaction start` at 20:30:24, `agent start` at 20:32:16 — **112 seconds** on compaction alone
- `timeoutSeconds` was still 120s at that run (180s update hadn't taken effect yet)
- Agent got <8s to respond after compaction, timed out immediately
**Fix Applied:**
- `agents.defaults.timeoutSeconds` → 180s (already done)
- Long-term: reduce session token accumulation (see below)
**Session Token Analysis (from user-provided /status output):**
```
main (InfraBot):   185k/200k  93%  — CRITICAL, triggers long compaction
research (cron):    26k/200k  13%  — fine
manager (telegram): 11k/200k   5%  — fine
manager (cron):     10k/200k   5%  — fine
main (cron):        16k/200k   8%  — fine
media (cron):       12k/200k   6%  — fine
```
**Why main session is so full:**
1. Large summary injected at conversation start (compaction summary ~30k tokens)
2. All test file writes in single run = large tool outputs accumulated in context
3. SOUL.md + AGENTS.md + TOOLS.md + IDENTITY.md + USER.md + HEARTBEAT.md loaded every session
4. cron status entries duplicated in session list (each cron shows 2x)
**Optimization Recommendations:**
1. Keep `timeoutSeconds = 240` for main session (compaction can take 2+ min at high token count)
2. Set `compaction.mode = aggressive` to compact earlier (before 93%)
3. Break large multi-file tasks into separate messages to avoid accumulating huge context
4. Consider moving SOUL.md + AGENTS.md injections to a shorter summary format
**Status:** Resolved for now; 180s timeout active. Monitor session token level.

---

## INCIDENT-007 — 2026-03-02 ~20:07 UTC

**Type:** Prompt-as-transport anti-pattern caused aborted request under heavy session load
**Symptom:** `Request was aborted` — InfraBot Telegram session, sessions_spawn call
**Root Cause (confirmed via session log):**
- InfraBot tried to embed 6 full file contents (GOVERNANCE.md, CHANGE_LOG.md, smoke_test.py, test_infra_audit.py + more) directly inside a single `sessions_spawn` task string
- Payload was enormous (multi-thousand token JSON blob) — serialization/transport layer aborted mid-send
- Compound factor: Telegram session was at `totalTokens: 180,933` (90% of 200k limit) — session already slow and heavy
- Telegram polling connection not suited for large payload delivery

**Anti-pattern name:** Prompt-as-transport — using the LLM prompt/task field as a file delivery vehicle instead of a goal + references description

**Fix Applied:**
- Retried from Webchat session (stable transport) using reference-based task description
- Subagent `infra-governance-tests` running correctly

**New Hard Rules (Boss directive 2026-03-02):**
1. Telegram = control-plane only. Start tasks, query status, short directives, receive summaries. NO large payloads.
2. sessions_spawn tasks must be reference-based: goal + target files + required changes + acceptance criteria. Never inline full file contents.
3. Context-pressure guard: if session context near limit → refuse heavy spawn, summarize, switch channel or split work.
4. Large rebuild / governance / test-gen tasks → Webchat or exec path only.

**Status:** Rules enforced. Subagent running from Webchat. Compact task template created (see shared/knowledge/SPAWN_TEMPLATE.md).
