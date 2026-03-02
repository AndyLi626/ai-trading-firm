# Standard Job Spec Template
Every new autonomous job must fill all 12 fields before being added to cron/jobs.json.

```yaml
job_name:        # 唯一，kebab-case
owner_bot:       # manager | research | infra | audit | risk | media
purpose:         # 一句话说清楚做什么
trigger:
  schedule:      # cron 表达式
  quiet_hours:   # 仅在此时间窗口内运行（如 01:00–05:00 UTC）
inputs:
  - # DB 表 / 事实文件 / memory 文件 / skills index
outputs:
  - path: memory/autonomy/YYYY-MM-DD/<filename>
    format: json|md
delivery:        # 固定 none；例外仅 incident（需 InfraBot 审批）
budget_policy:
  script: run_with_budget.py
  bot: <owner_bot>
  est_tokens_per_run: <N>
  cost_cap_usd: 0.05
  on_warn: degrade
  on_stop: skip_run
governance:
  proposal: memory/proposals/prop-<job_name>.md
  review: manager_review
  validate: unit_test + config_guard check
  apply: add to cron/jobs.json
  rollback: remove job + delete output files
safety:
  - no prompt-as-transport (prompt < 50 lines)
  - no direct writes to openclaw.json
  - no sessions_spawn in cron prompt
tests:           # 至少 1 个 unit test in tests/test_autonomy_framework.py
acceptance:
  - 跑一次能产出 output 文件
  - Manager 早报能读到并汇总 delta
```

---

## 示例：autonomy-orchestrator

```yaml
job_name:        autonomy-orchestrator
owner_bot:       manager
purpose:         生成并刷新今日自主任务队列；汇总各 bot 产出
trigger:
  schedule:      0 * * * *
  quiet_hours:   00:00–06:00 UTC（夜间低优先级）
inputs:
  - cron/runs/*.jsonl（今日运行记录）
  - memory/autonomy/YYYY-MM-DD/（今日产物目录）
  - shared/knowledge/BOT_SKILLS_REGISTRY.md
outputs:
  - path: memory/autonomy/YYYY-MM-DD/AUTONOMY_QUEUE.json
    format: json
  - path: memory/autonomy/YYYY-MM-DD/AUTONOMY_OUTPUTS.md
    format: md
delivery:        none
budget_policy:
  script: run_with_budget.py
  bot: manager
  est_tokens_per_run: 5000
  cost_cap_usd: 0.01
  on_warn: degrade
  on_stop: skip_run
governance:
  proposal: memory/proposals/prop-autonomy-orchestrator.md
  review: manager_review
  validate: test_autonomy_framework.py
  apply: added to cron/jobs.json
  rollback: remove job entry; delete memory/autonomy/YYYY-MM-DD/
safety:
  - prompt < 20 lines
  - no direct config writes
tests:           tests/test_autonomy_framework.py::test_orchestrator_runs
acceptance:
  - AUTONOMY_QUEUE.json 存在且 valid JSON
  - Manager 早报 Line 7 能看到 autonomy delta
```
