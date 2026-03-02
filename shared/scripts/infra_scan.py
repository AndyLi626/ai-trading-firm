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
CRON_JOBS = os.environ.get("CRON_JOBS_FILE", os.path.expanduser("~/.openclaw/cron/jobs.json"))
CRON_RUNS = os.environ.get("CRON_RUNS_DIR", os.path.expanduser("~/.openclaw/cron/runs"))
PRICING_PATH = os.path.join(WORKSPACE, "shared/knowledge/model_pricing.json")


def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_jobs():
    if not os.path.exists(CRON_JOBS):
        return []
    with open(CRON_JOBS) as f:
        return json.load(f).get("jobs", [])


def get_recent_run_names(hours=24):
    cutoff_str = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%d")
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
    bad = []
    scripts_dir = os.path.join(WORKSPACE, "shared/scripts")
    if not os.path.exists(scripts_dir):
        return bad
    for fpath in glob.glob(os.path.join(scripts_dir, "*.py")):
        try:
            with open(fpath) as f:
                content = f.read()
            if re.search(r'openclaw\.json', content) and re.search(r"open\([^)]*['\"]w", content):
                bad.append(os.path.basename(fpath))
        except Exception:
            continue
    return bad


def audit_jobs(jobs, recent_runs):
    proposals = []
    for job in jobs:
        name = job.get("name", "unknown")
        delivery = job.get("delivery", {})
        payload_msg = ""
        if isinstance(job.get("payload"), dict):
            payload_msg = job["payload"].get("message", "")

        if isinstance(delivery, dict) and delivery.get("mode") != "none":
            proposals.append({
                "type": "delivery_mode",
                "severity": "medium",
                "description": f"Job '{name}' has delivery mode '{delivery.get('mode')}' (should be none)",
                "proposed_fix": f"Set delivery.mode=none for '{name}'",
                "requires_human_review": True,
            })

        if "run_with_budget" not in payload_msg:
            proposals.append({
                "type": "missing_budget_check",
                "severity": "high",
                "description": f"Job '{name}' does not call run_with_budget.py",
                "proposed_fix": f"Add run_with_budget.py as first step in '{name}'",
                "requires_human_review": True,
            })

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
    bad_scripts = check_scripts_for_direct_writes()
    proposals = audit_jobs(jobs, recent_runs)

    for script in bad_scripts:
        proposals.append({
            "type": "governance_violation",
            "severity": "critical",
            "description": f"Script '{script}' may write openclaw.json directly",
            "proposed_fix": "Use config_guard.py instead of direct file writes",
            "requires_human_review": True,
        })

    sev_counts = {}
    for p in proposals:
        sev_counts[p["severity"]] = sev_counts.get(p["severity"], 0) + 1

    out_dir = os.path.join(WORKSPACE, "memory", "autonomy", today_str())
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "infra_proposals.json")
    with open(out_path, "w") as f:
        json.dump({
            "date": today_str(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {"total": len(proposals), "by_severity": sev_counts},
            "proposals": proposals,
        }, f, indent=2)

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

    write_drift_report(proposals, out_dir)
    print(f"Infra scan done: {len(proposals)} proposals. Output: {out_path}")


def write_drift_report(proposals, out_dir):
    """Write ledger/DRIFT_REPORT.md with current scan findings."""
    import os
    WS = os.path.expanduser("~/.openclaw/workspace")
    ledger = os.path.join(WS, "ledger")
    os.makedirs(ledger, exist_ok=True)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    lines = [
        f"# Drift Report — {now.strftime('%Y-%m-%d %H:%M')} UTC",
        "_Auto-generated by infra_scan.py_\n",
        f"**Total issues:** {len(proposals)}\n",
    ]
    by_sev = {"critical":[], "high":[], "medium":[], "low":[]}
    for p in proposals:
        by_sev.setdefault(p.get("severity","low"), []).append(p)
    for sev in ["critical","high","medium","low"]:
        items = by_sev[sev]
        if not items: continue
        icon = {"critical":"🔴","high":"🟠","medium":"🟡","low":"⚪"}.get(sev,"")
        lines.append(f"## {icon} {sev.upper()} ({len(items)})")
        for p in items:
            lines.append(f"- **{p['type']}**: {p['description']}")
            lines.append(f"  - Fix: {p['proposed_fix']}")
            if p.get("requires_human_review"):
                lines.append("  - ⚠️ Requires human review")
        lines.append("")
    open(os.path.join(ledger, "DRIFT_REPORT.md"), "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
