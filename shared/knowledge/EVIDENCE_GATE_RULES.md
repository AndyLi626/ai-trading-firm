# Evidence Gate 规则

**版本:** 1.0  
**生效日期:** 2026-03-02  
**ADR:** ledger/ADRs/ADR-006-evidence-gate.md  
**实施文件:** shared/tools/evidence_gate.py

---

## 触发类别

| 类别 | 触发条件 | 必须提供 | 最大有效期 |
|------|---------|---------|-----------|
| `market_price` | 任何价格/涨跌幅/市值数字 | source + as_of | 30 分钟 |
| `system_status` | heartbeat/gateway/cron/连接状态 | 文件路径 + 最后修改时间 | 2 分钟 |
| `model_availability` | 声称某模型可用或在运行 | cron run model= 实测字段 + 时间戳 | 1 小时 |
| `cost_budget` | 预算余量/花费/是否可用 | budget_state.json 当前值 或 GCP 账单行 | 15 分钟 |

---

## 违规处理

| 情形 | 输出标记 | 禁止使用 |
|------|---------|---------|
| 无证据 | `UNCERTAIN` | ✅ |
| 证据过期 | `STALE` | ✅ |
| Qwen/media agent 行情数字 | `[REDACTED]` | 任何数值 |

**关键原则:** 宁可输出 `UNCERTAIN` 也不输出无凭据的 ✅

---

## 合规示例

### 示例 1: 行情引用
```
✅ 合规:
SPY=686.25 (source=alpaca_iex, as_of=2026-03-02T17:36Z)

❌ 违规:
SPY=686 ✅
SPY 上涨 0.02% ✅
```

### 示例 2: 系统状态引用
```
✅ 合规:
heartbeat age=45s (file=workspace-manager/runtime_state/infra_heartbeat.json, last_update=2026-03-02T17:48Z)

❌ 违规:
heartbeat 正常 ✅
ticket poller 在运行 ✅
```

### 示例 3: 模型可用性引用
```
✅ 合规:
model_availability: UNCERTAIN（无 17:00 后 cron run 实测证据）

✅ 合规（有证据时）:
claude-sonnet-4-6 最近成功运行 (cron=strategy-scan, lastRunAt=2026-03-02T17:32Z, status=ok)

❌ 违规:
claude-sonnet-4-6 正常运行 ✅
```

### 示例 4: 预算引用
```
✅ 合规:
anthropic 已用 $1.23/$3.50 (budget_state.json, updated=2026-03-02T17:45Z)

❌ 违规:
预算充足 ✅
Anthropic 还有余量 ✅
```

---

## Qwen/media 限制

- MediaBot（qwen agent）**禁止**在输出中包含行情数字
- MediaBot 只允许输出：可引用来源的文本信号、情绪标签
- 任何 Qwen 模型对行情数字的引用 → 自动 `[REDACTED]`

---

## 实施状态

- [x] evidence_gate.py 已部署（shared/tools/evidence_gate.py）
- [x] ADR-006 已归档（ledger/ADRs/ADR-006-evidence-gate.md）
- [x] SOUL.md 已包含 Evidence Gate 硬约束
- [x] healthcheck.py 检查项 7: evidence_gate EXISTS + importable
- [x] ARCHITECTURE.md 章节 7 已更新
