#!/usr/bin/env python3
"""infra_scan.py — Twice-daily infrastructure audit.
Checks cron delivery, budget enforcement, pricing gaps, governance.
"""
import glob
import json
import os
import re
from datetime import datetime, timezone, timedelta

WORKSPACE = os.environ.get("WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
CRON_JOBS = os.environ.get("CRON_JOBS_FILE",
    os.path.expanduser("~/.openclaw/cron/jobs.json"))
CRON_RUNS = os.environ.get("CRON_RUNS_DIR",
    os.path.expanduser("~/.openclaw/cron/runs"))
PRICING_PATH = os.path.join(WORKSPACE, "shared/knowledge/model_pricing.json")

def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def load_jobs():
    if not os.path.exists(CRON_JOBS):
        return []
    with open(CRON_JOBS) as f:
        return json.load(f).get("jobs", [])

def get_recent_run_names(hours=24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    ran = set()
    for fpath in glob.glob(os.path.join(CRON_RUNS, "*.jsonl")):
        try:
            with open(fpath) as f:
                for line in f:
                    e = json.loads(line.strip())
                    ts = e.get("startedAt", e.get("ts", ""))
                    if ts >= cutoff_str:
                        ran.add(e.get("name") or e.get("jobName", ""))
        except Exception:
            continue
    return ran

def check_scripts_for_direct_writes():
    """Find scripts that write openclaw.json directly."""
    bad = []
    for fpath in glob.glob(os.path.join(WORKSPACE, "shared/scripts/*.py")):
        try:
            with open(fpath) as f:
                content = f.read()
            if re.search(r'openclaw\.json', content) and re.search(r'open\(.*w', content):
                bad.append(os.path.basename(fpath))
        except Exception:
            continue
    return bad

def load_pricing():
    if not os.path.exists(PRICING_PATH):
        return {}
    with open(PRICING_PATH) as f:
        return json.load(f)

def audit_jobs(jobs, recent_runs, pricing):
    proposals = []
    for job in jobs:
        name = job.get("name", "unknown")
        delivery = job.get("delivery", {})
        payload_msg = ""
        if isinstance(job.get("payload"), dict):
            payload_msg = job["payload"].get("message", "")

        # Check delivery mode
        if isinstance(delivery, dict) and delivery.get("mode") != "none":
            proposals.append({
                "type": "delivery_mode",
                "severity": "medium",
                "description": f"Job '{name}' has delivery mode '{delivery.get('mode')}' (should be none for autonomous jobs)",
                "proposed_fix": f"Set delivery.mode=none for job '{name}'",
                "requires_human_review": True,
            })

        # Check budget enforcement
        if "run_with_budget" not in payload_msg:
            proposals.append({
                "type": "missing_budget_check",
                "severity": "high",
                "description": f"Job '{name}' does not call run_with_budget.py",
                "proposed_fix": f"Add run_with_budget.py call as first step in '{name}' payload",
                "requires_human_review": True,
            })

        # Check recent run
        if name not in recent_runs:
            proposals.append({
                "type": "no_recent_run",
                "severity": "low",
                "description": f"Job '{name}' has no run in last 24h",
                "proposed_fix": "Verify job is enabled and schedule is correct",
                "requires_human_review": False,
            })

    return proposals

def main():
    jobs = load_jobs()
    recent_runs = get_recent_run_names()
    pricing = load_pricing()
    bad_scripts = check_scripts_for_direct_writes()

    proposals = audit_jobs(jobs, recent_runs, pricing)

    for script in bad_scripts:
        proposals.append({
            "type": "governance_violation",
            "severity": "critical",
            "description": f"Script '{script}' may write openclaw.json directly",
            "proposed_fix": "Use config_guard.py instead of direct file writes",
            "requires_human_review": True,
        })

    # Output
    out_dir = os.path.join(WORKSPACE, "memory", "autonomy", today_str())
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "infra_proposals.json")
    summary = {
        "total": len(proposals),
        "high": sum(1 for p in proposals if p["severity"] in ("high", "critical")),
        "medium": sum(1 for p in proposals if p["severity"] == "medium"),
        "low": sum(1 for p in proposals if p["severity"] == "low"),
    }
    with open(out_path, "w") as f:
        json.dump({"date": today_str(),
                   "generated_at": datetime.now(timezone.utc).isoformat(),
                   "proposals": proposals,
                   "summary": summary}, f, indent=2)

    proposals_md = os.path.join(out_dir, "AUTONOMY_PROPOSALS.md")
    if not os.path.exists(proposals_md):
        with open(proposals_md, "w") as f:
            f.write(f"# AUTONOMY_PROPOSALS — {today_str()}\n\n")

    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    with open(proposals_md, "a") as f:
        f.write(f"\n## Infra Scan @ {now} ({len(proposals)} proposals)\n")
        for p in proposals:
            icon = "🔴" if p["severity"] == "critical" else "🟠" if p["severity"] == "high" else "🟡"
            f.write(f"- {icon} [{p['type']}] {p['description']}\n")

    print(f"Infra scan done: {len(proposals)} proposals. Output: {out_path}")

if __name__ == "__main__":
    main()
