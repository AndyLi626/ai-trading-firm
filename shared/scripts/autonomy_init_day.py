#!/usr/bin/env python3
"""autonomy_init_day.py — Create today's autonomy directory + skeleton files.
Idempotent: existing files are not overwritten.
"""
import json
import os
import sys
from datetime import datetime, timezone

WORKSPACE = os.environ.get("WORKSPACE", os.path.expanduser(
    "~/.openclaw/workspace"))


def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def init_day(base_dir=None, date_str=None):
    if date_str is None:
        date_str = today_str()
    if base_dir is None:
        base_dir = os.path.join(WORKSPACE, "memory", "autonomy", date_str)

    os.makedirs(base_dir, exist_ok=True)

    queue_path = os.path.join(base_dir, "AUTONOMY_QUEUE.json")
    outputs_path = os.path.join(base_dir, "AUTONOMY_OUTPUTS.md")
    proposals_path = os.path.join(base_dir, "AUTONOMY_PROPOSALS.md")

    if not os.path.exists(queue_path):
        skeleton = {
            "date": date_str,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "1.0",
            "queue": [],
            "metadata": {
                "total_jobs": 0,
                "completed": 0,
                "pending": 0,
                "failed": 0,
            }
        }
        with open(queue_path, "w") as f:
            json.dump(skeleton, f, indent=2)
        print(f"Created {queue_path}")
    else:
        print(f"Exists (skip): {queue_path}")

    if not os.path.exists(outputs_path):
        with open(outputs_path, "w") as f:
            f.write(f"# AUTONOMY_OUTPUTS — {date_str}\n\n")
            f.write("_Populated by autonomy_orchestrator.py each hour._\n\n")
        print(f"Created {outputs_path}")
    else:
        print(f"Exists (skip): {outputs_path}")

    if not os.path.exists(proposals_path):
        with open(proposals_path, "w") as f:
            f.write(f"# AUTONOMY_PROPOSALS — {date_str}\n\n")
            f.write("_Populated by infra_scan.py._\n\n")
        print(f"Created {proposals_path}")
    else:
        print(f"Exists (skip): {proposals_path}")

    return base_dir


if __name__ == "__main__":
    result = init_day()
    print(f"Day initialized: {result}")
