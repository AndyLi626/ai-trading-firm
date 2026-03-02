# 合法 Cron 白名单

> 此文件定义"不可隔离"的 cron job。
> 任何 quarantine/清理/审批规则执行前，必须检查此白名单。

## 规则
- 白名单内的 cron **不受**"未授权 cron 清理"影响
- 白名单内的 cron **不需要** proposal→review→apply 流程（已在此文件批准）
- 修改白名单本身需要 InfraBot + Boss 双重确认

---

## 白名单（合法且不可隔离）

| Cron 名 | 类别 | Budget 豁免 | 原因 |
|---------|------|------------|------|
| `infra-ticket-poll` | CONTROL_PLANE | ✅ 是 | 工单消费系统，确定性，tokens=0 |
| `market-pulse-15m` | FACT_ANCHOR | ❌ 否 | 行情事实锚，所有市场数据的真实来源 |
| `emergency-scan-poll` | EVENT_CHANNEL | ❌ 否 | 事件触发通道，emergency 主链路 |
| `anomaly-detector` | CONTROL_PLANE | ❌ 否 | Tier0 异动检测，纯确定性规则 |
| `manager-30min-report` | REPORTING | ❌ 否 | Boss 控制面，唯一人类报告入口 |
| `media-intel-scan` | INTEL | ❌ 否 | 媒体情报，媒体数据主链路 |

---

## CONTROL_PLANE 定义
> 确定性脚本（无 LLM），不受 `run_with_budget stop` 限制，
> 必须在任何预算状态下持续运行。

## 批准记录
- 2026-03-02 Boss 明确授权（工单 GOVERNANCE-CRON-SPRAWL 审查后）
