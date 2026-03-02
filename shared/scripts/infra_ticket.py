#!/usr/bin/env python3
"""
infra_ticket.py — Manager→Infra 文件票据通道（替代 Telegram bot 间通信）
写端: python3 infra_ticket.py write "<message>" [--from manager] [--priority high|normal]
读端: python3 infra_ticket.py poll             → 处理 pending tickets，写 processed
巡检: python3 infra_ticket.py status           → 输出待处理数量
"""
import sys, os, json, uuid
from datetime import datetime, timezone

TICKET_FILE = "/tmp/oc_facts/infra_tickets.json"
PROCESSED   = "/tmp/oc_facts/infra_tickets_processed.json"
now_utc     = datetime.now(timezone.utc)


def load(path, default):
    try: return json.load(open(path))
    except Exception: return default

def save(path, data):
    json.dump(data, open(path, "w"), indent=2)


def write_ticket(message, sender="manager", priority="normal"):
    tickets = load(TICKET_FILE, [])
    ticket = {
        "ticket_id": str(uuid.uuid4()),
        "from":      sender,
        "to":        "infra",
        "message":   message,
        "priority":  priority,
        "status":    "pending",
        "created_at": now_utc.isoformat()
    }
    tickets.append(ticket)
    save(TICKET_FILE, tickets)
    print(json.dumps({"status": "ok", "ticket_id": ticket["ticket_id"],
                      "from": sender, "priority": priority}))


def poll_tickets():
    tickets    = load(TICKET_FILE, [])
    processed  = load(PROCESSED, [])
    pending    = [t for t in tickets if t["status"] == "pending"]

    if not pending:
        print(json.dumps({"status": "no_pending", "total": len(tickets)}))
        return

    results = []
    for t in pending:
        t["status"]      = "processed"
        t["processed_at"] = now_utc.isoformat()
        processed.append(t)
        results.append({"ticket_id": t["ticket_id"], "from": t["from"],
                         "priority": t["priority"], "message": t["message"][:100]})

    # Update pending → processed in main file
    for t in tickets:
        if t["status"] == "pending":
            t["status"] = "processed"
            t["processed_at"] = now_utc.isoformat()

    save(TICKET_FILE, tickets)
    save(PROCESSED, processed)
    print(json.dumps({"status": "ok", "processed": len(results), "tickets": results}))


def status():
    tickets = load(TICKET_FILE, [])
    pending = [t for t in tickets if t["status"] == "pending"]
    print(json.dumps({
        "pending":  len(pending),
        "total":    len(tickets),
        "oldest_pending": pending[0]["created_at"] if pending else None
    }))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "write":
        msg      = sys.argv[2] if len(sys.argv) > 2 else "ping"
        sender   = "manager"
        priority = "normal"
        for i, a in enumerate(sys.argv):
            if a == "--from"     and i+1 < len(sys.argv): sender   = sys.argv[i+1]
            if a == "--priority" and i+1 < len(sys.argv): priority = sys.argv[i+1]
        write_ticket(msg, sender, priority)
    elif cmd == "poll":
        poll_tickets()
    elif cmd == "status":
        status()
    else:
        print(f"Usage: infra_ticket.py write|poll|status")
        sys.exit(1)
