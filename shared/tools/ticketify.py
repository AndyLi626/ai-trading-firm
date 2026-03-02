#!/usr/bin/env python3
"""ticketify.py — Conversation→ticket converter"""
import sys, os, json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/shared/tools"))
from ticket_queue import enqueue

WS  = Path(os.path.expanduser("~/.openclaw/workspace"))
now = datetime.now(timezone.utc)

def ticketify(discussion: str, priority: str = "normal", acceptance: str = "") -> dict:
    title = discussion.strip().splitlines()[0][:60]
    if not acceptance:
        acceptance = "file  + Manager  delta "
    t = enqueue(
        message=f"{title}\n\n{discussion}\n\ncriteria: {acceptance}",
        sender="manager",
        priority=priority
    )
    prop_dir = WS / "memory" / "proposals"
    prop_dir.mkdir(parents=True, exist_ok=True)
    date_str = now.strftime("%Y-%m-%d")
    ts_str   = now.strftime("%Y%m%d_%H%M")
    tid_short = t['ticket_id'][:8]
    prop_file = prop_dir / f"ticket_{tid_short}_{ts_str}.md"
    prop_file.write_text(
        f"# Ticket: {title}\n\n"
        f"**ID**: {t['ticket_id']}\n"
        f"**Priority**: {priority}\n"
        f"**Created**: {now.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        f"# #  \n{discussion}\n\n"
        f"# #  criteria\n{acceptance}\n\n"
        f"## evidence path\n"
        f"- shared/state/ticket_index.json\n"
        f"- memory/autonomy/{date_str}/AUTONOMY_OUTPUTS.md\n"
    )
    return {"ticket_id": t["ticket_id"], "title": title, "proposal": str(prop_file)}

if __name__ == "__main__":
    discussion = sys.argv[1] if len(sys.argv) > 1 else "test"
    priority   = next((sys.argv[i+1] for i,a in enumerate(sys.argv)
                       if a=="--priority" and i+1<len(sys.argv)), "normal")
    acceptance = next((sys.argv[i+1] for i,a in enumerate(sys.argv)
                       if a=="--acceptance" and i+1<len(sys.argv)), "")
    print(json.dumps(ticketify(discussion, priority, acceptance), ensure_ascii=False, indent=2))