#!/usr/bin/env python3
"""
autonomy_init_day.py — 每日自主任务目录初始化
由 autonomy-orchestrator cron 在首次运行时调用（也可手动）

产物（写入 memory/autonomy/YYYY-MM-DD/）：
  AUTONOMY_QUEUE.json    — 今日队列（任务列表 + 预算估算）
  AUTONOMY_OUTPUTS.md   — 今日产出汇总（追加式，不重复历史）
  AUTONOMY_PROPOSALS.md — 待人工/Manager 审核的 proposal
"""
import os, json
from datetime import datetime, timezone
from pathlib import Path

WS   = Path(os.path.expanduser("~/.openclaw/workspace"))
DATE = datetime.now(timezone.utc).strftime('%Y-%m-%d')
DIR  = WS / "memory" / "autonomy" / DATE

DIR.mkdir(parents=True, exist_ok=True)

# ── AUTONOMY_QUEUE.json ──────────────────────────────────────────────────────
queue_path = DIR / "AUTONOMY_QUEUE.json"
if not queue_path.exists():
    queue = {
        "date":        DATE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "queue": [
            {
                "job_name":    "repo-skills-scan",
                "owner_bot":   "research",
                "purpose":     "扫描可用 repo/skills，输出候选与能力缺口",
                "status":      "PENDING",
                "est_tokens":  3000,
                "est_cost_usd": 0.01,
                "trigger":     "nightly (quiet_hours)",
                "output_file": f"memory/autonomy/{DATE}/repo_skills_scan.json",
            },
            {
                "job_name":    "infra-12h-scan",
                "owner_bot":   "infra",
                "purpose":     "检查缺失/升级/故障/治理漏洞，输出 proposal（不 apply）",
                "status":      "PENDING",
                "est_tokens":  2000,
                "est_cost_usd": 0.006,
                "trigger":     "every 12h",
                "output_file": f"memory/autonomy/{DATE}/infra_proposals.json",
            },
            {
                "job_name":    "audit-daily",
                "owner_bot":   "audit",
                "purpose":     "日度治理审计，检查 config/cron/script 合规性",
                "status":      "PENDING",
                "est_tokens":  1500,
                "est_cost_usd": 0.005,
                "trigger":     "every 12h",
                "output_file": f"memory/autonomy/{DATE}/audit_report.json",
            },
        ],
        "budget_total_est_tokens": 6500,
        "budget_total_est_usd":    0.021,
    }
    queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False))
    print(f"✅ AUTONOMY_QUEUE.json 创建: {len(queue['queue'])}个任务")
else:
    print(f"ℹ️  AUTONOMY_QUEUE.json 已存在，跳过")

# ── AUTONOMY_OUTPUTS.md ──────────────────────────────────────────────────────
outputs_path = DIR / "AUTONOMY_OUTPUTS.md"
if not outputs_path.exists():
    outputs_path.write_text(
        f"# 自主任务产出汇总 — {DATE}\n\n"
        "_由各 bot 自动追加，每条只写新增内容_\n\n"
        "| 时间 | Bot | 任务 | 产出摘要 |\n"
        "|------|-----|------|----------|\n",
        encoding='utf-8'
    )
    print(f"✅ AUTONOMY_OUTPUTS.md 创建")
else:
    print(f"ℹ️  AUTONOMY_OUTPUTS.md 已存在，跳过")

# ── AUTONOMY_PROPOSALS.md ────────────────────────────────────────────────────
proposals_path = DIR / "AUTONOMY_PROPOSALS.md"
if not proposals_path.exists():
    proposals_path.write_text(
        f"# 待审核 Proposal — {DATE}\n\n"
        "_优先级排序，需 Manager 或 Boss 确认后才能 apply_\n\n"
        "## P0（今日必须审核）\n\n无\n\n"
        "## P1（本周审核）\n\n无\n\n"
        "## P2（可延期）\n\n无\n",
        encoding='utf-8'
    )
    print(f"✅ AUTONOMY_PROPOSALS.md 创建")
else:
    print(f"ℹ️  AUTONOMY_PROPOSALS.md 已存在，跳过")

print(f"\n产物目录: {DIR}")
print(json.dumps({"status": "ok", "date": DATE, "dir": str(DIR)}, ensure_ascii=False))
