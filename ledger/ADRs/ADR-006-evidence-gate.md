# ADR-006 — Evidence Gate（证据门禁）

**状态:** ACCEPTED  
**日期:** 2026-03-02  
**作者:** InfraBot  
**批准:** Boss（隐式，via SOUL.md Evidence Gate 条款）

---

## 背景

多个 bot 在没有可验证证据的情况下输出 ✅ 标记的断言，包括：

1. 行情数字（如"SPY=684 ✅"）— 未引用数据源或时间戳
2. 系统状态（如"heartbeat 正常 ✅"）— 未引用文件路径或时间
3. 模型可用性（如"Sonnet 在跑 ✅"）— 未引用 cron run 实测记录
4. 预算余量（如"预算充足 ✅"）— 未引用 budget_state.json

这类"置信度膨胀"会在真实故障（heartbeat 已停、数据已过期）时给操作员造成错误安全感，
导致错误决策。INCIDENT-007（Telegram 大型 payload）的根因之一就是缺乏证据约束。

---

## 规则（4类必须有 source + as_of）

### 类别 1: market_price
- **触发条件:** 任何行情数字（价格、涨跌幅、市值等）
- **必须提供:** `source`（数据来源）+ `as_of`（时间戳，30min 内）
- **违规示例:** `SPY=686 ✅`
- **合规示例:** `SPY=686.25 (source=alpaca_iex, as_of=2026-03-02T17:36Z)`

### 类别 2: system_status
- **触发条件:** 任何系统状态断言（heartbeat、gateway、cron、连接状态）
- **必须提供:** 文件路径 + 最后修改时间戳（或 RPC probe 结果）
- **违规示例:** `heartbeat 正常 ✅`
- **合规示例:** `heartbeat age=0min (file=runtime_state/infra_heartbeat.json, last_update=17:36Z)`

### 类别 3: model_availability
- **触发条件:** 任何声称模型可用或正在运行的断言
- **必须提供:** cron run 的 `model=` 字段 + 时间戳（实测，非推断）
- **违规示例:** `claude-sonnet-4-6 在跑 ✅`
- **合规示例:** `model_availability: UNCERTAIN (无 17:00 后 probe 证据)`

### 类别 4: cost_budget
- **触发条件:** 任何预算余量、花费或是否可用的断言
- **必须提供:** budget_state.json 的当前值 + 时间戳，或 GCP 账单行
- **违规示例:** `预算充足 ✅`
- **合规示例:** `anthropic 已用 $1.23/$3.50 (budget_state.json, updated=17:45Z)`

---

## 违规处理

| 情形 | 处理方式 |
|------|---------|
| 无证据 | 输出 `UNCERTAIN`，禁止 ✅ |
| 证据过期（market >30min，heartbeat >2min）| 输出 `STALE`，禁止 ✅ |
| Qwen/media 输出行情数字 | `[REDACTED]`（media agent 不得自证行情）|

---

## 实施

**文件:** `shared/tools/evidence_gate.py`

函数接口（示意）：
```python
evidence_gate.check(category="market_price", value=686.25, source="alpaca_iex", as_of="2026-03-02T17:36Z")
# 返回: {"status": "PASS", "label": "SPY=686.25 (source=alpaca_iex, as_of=17:36Z)"}

evidence_gate.check(category="market_price", value=686.25, source=None, as_of=None)
# 返回: {"status": "FAIL", "label": "UNCERTAIN (no evidence)"}
```

**规则文件:** `shared/knowledge/EVIDENCE_GATE_RULES.md`

---

## 验收测试（4个）

### 测试 1: 行情无证据 → UNCERTAIN
```python
result = gate.check("market_price", value=686.25, source=None, as_of=None)
assert result["status"] == "FAIL"
assert "UNCERTAIN" in result["label"]
```

### 测试 2: 行情有效证据 → PASS
```python
result = gate.check("market_price", value=686.25, source="alpaca_iex", as_of=now_iso)
assert result["status"] == "PASS"
assert "alpaca_iex" in result["label"]
```

### 测试 3: system_status 证据过期 → STALE
```python
old_ts = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
result = gate.check("system_status", file_path="heartbeat.json", last_modified=old_ts, max_age_s=120)
assert result["status"] == "STALE"
```

### 测试 4: Qwen/media 行情数字 → REDACTED
```python
result = gate.check("market_price", value=686.25, agent="media")
assert result["label"] == "[REDACTED]"
```

---

## 影响范围

- 所有 bot 的 SOUL.md（已包含 Evidence Gate 硬约束）
- `shared/knowledge/EVIDENCE_GATE_RULES.md`（详细规则文档）
- healthcheck.py（检查项 7: evidence_gate）
- ARCHITECTURE.md（章节 7）
- STATUS_MATRIX.md（evidence_gate 行）
