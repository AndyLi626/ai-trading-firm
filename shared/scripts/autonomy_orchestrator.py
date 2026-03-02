#!/usr/bin/env python3
"""autonomy_orchestrator.py — Hourly autonomy queue refresh.
Pure Python; no LLM calls, no sessions_spawn.
"""
import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
CRON_RUNS_DIR = os.environ.get("CRON_RUNS_DIR", os.path.expanduser("~/.openclaw/cron/runs"))
BUDGET_SCRIPT = os.path.join(WORKSPACE, "shared/scripts/run_with_budget.py")


def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def get_today_dir(date_str=None):
    if date_str is None:
        date_str = today_str()
    return os.path.join(WORKSPACE, "memory", "autonomy", date_str)


def check_budget():
    if not os.path.exists(BUDGET_SCRIPT):
        print("WARN: run_with_budget.py not found, skipping budget check")
        return True
    try:
        result = subprocess.run(
            [sys.executable, BUDGET_SCRIPT, "manager", "5000"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 1:
            print("BUDGET HARD STOP — orchestrator aborted.")
            return False
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        if lines:
            data = json.loads(lines[-1])
            if data.get("action") == "stop":
                print("BUDGET HARD STOP — orchestrator aborted.")
                return False
        return True
    except Exception as e:
        print(f"WARN: budget check failed ({e}), proceeding")
        return True


def scan_cron_runs(date_str):
    jobs_run = []
    pattern = os.path.join(CRON_RUNS_DIR, "*.jsonl")
    for fpath in glob.glob(pattern):
        try:
            with open(fpath) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    ts = entry.get("startedAt") or entry.get("ts") or ""
                    if ts.startswith(date_str):
                        jobs_run.append({
                            "name": entry.get("name") or entry.get("jobName", "unknown"),
                            "status": entry.get("status", "unknown"),
                            "startedAt": ts,
                        })
        except Exception:
            continue
    return jobs_run


def load_queue(queue_path):
    if os.path.exists(queue_path):
        with open(queue_path) as f:
            return json.load(f)
    return {"date": today_str(), "queue": [], "metadata": {}}


def update_queue(queue_data, jobs_run):
    run_names = {j["name"] for j in jobs_run}
    for item in queue_data.get("queue", []):
        if item.get("job_name") in run_names:
            item["status"] = "completed"
    completed = sum(1 for i in queue_data["queue"] if i.get("status") == "completed")
    failed = sum(1 for i in queue_data["queue"] if i.get("status") == "failed")
    pending = len(queue_data["queue"]) - completed - failed
    queue_data["metadata"] = {
        "total_jobs": len(queue_data["queue"]),
        "completed": completed,
        "pending": pending,
        "failed": failed,
        "last_refresh": datetime.now(timezone.utc).isoformat(),
        "runs_today": len(jobs_run),
    }
    return queue_data


def append_outputs(outputs_path, jobs_run, queue_data):
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    meta = queue_data.get("metadata", {})
    lines = [
        f"\n## Refresh @ {now}",
        f"- Jobs run today: {meta.get('runs_today', len(jobs_run))}",
        f"- Queue: {meta.get('completed',0)} completed / {meta.get('pending',0)} pending / {meta.get('failed',0)} failed",
    ]
    if jobs_run:
        lines.append("- Recent runs: " + ", ".join(j["name"] for j in jobs_run[-5:]))
    with open(outputs_path, "a") as f:
        f.write("\n".join(lines) + "\n")


def main():
    date_str = today_str()
    today_dir = get_today_dir(date_str)

    init_script = os.path.join(WORKSPACE, "shared/scripts/autonomy_init_day.py")
    if os.path.exists(init_script):
        subprocess.run([sys.executable, init_script], capture_output=True,
                       env={**os.environ, "WORKSPACE": WORKSPACE})
    else:
        os.makedirs(today_dir, exist_ok=True)

    if not check_budget():
        sys.exit(0)

    queue_path = os.path.join(today_dir, "AUTONOMY_QUEUE.json")
    outputs_path = os.path.join(today_dir, "AUTONOMY_OUTPUTS.md")

    jobs_run = scan_cron_runs(date_str)
    queue_data = load_queue(queue_path)
    queue_data = update_queue(queue_data, jobs_run)

    with open(queue_path, "w") as f:
        json.dump(queue_data, f, indent=2)

    if not os.path.exists(outputs_path):
        with open(outputs_path, "w") as f:
            f.write(f"# AUTONOMY_OUTPUTS — {date_str}\n\n")

    append_outputs(outputs_path, jobs_run, queue_data)
    print(f"Orchestrator done. Runs today: {len(jobs_run)}. Queue: {queue_path}")


if __name__ == "__main__":
    main()
