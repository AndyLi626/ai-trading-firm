#!/usr/bin/env python3
"""
infra_ticket.py — Infra 工单状态机（确定性控制面，budget-exempt）
状态: OPEN → IN_PROGRESS → RESOLVED | INCIDENT

CLI:
  write  "<msg>" [--from <agent>] [--priority high|normal] [--id <id>]
  poll   — 主循环：auto-ACK + 进度更新 + OVERDUE 升级
  ack    <ticket_id> [--eta <min>]
  update <ticket_id> "<progress>"
  resolve <ticket_id> "<summary>"
  status — 汇总输出
  get    <ticket_id>
"""
import sys, os, json, uuid
from datetime import datetime, timezone, timedelta

TICKET_F  = "/tmp/oc_facts/infra_tickets.json"
WORK_F    = "/tmp/oc_facts/infra_worklist.json"
now_utc   = datetime.now(timezone.utc)

P0_ETA_MIN   = 10   # P0 工单 ETA
NORMAL_ETA   = 30
ACK_TIMEOUT  = 60   # 秒，超过即 OVERDUE_ACK → INCIDENT
UPDATE_GRACE = 600  # 秒，IN_PROGRESS 超过 next_update_at 需补更新


# ─── persistence ─────────────────────────────────────────────────────────────

def load_tickets():
    try:    return json.load(open(TICKET_F))
    except: return []

def save_tickets(tickets):
    json.dump(tickets, open(TICKET_F, "w"), indent=2)

def load_worklist():
    try:    return json.load(open(WORK_F))
    except: return []

def save_worklist(wl):
    json.dump(wl, open(WORK_F, "w"), indent=2)


# ─── core ops ────────────────────────────────────────────────────────────────

def write_ticket(message, sender="manager", priority="normal", ticket_id=None):
    tickets = load_tickets()
    eta_min = P0_ETA_MIN if priority == "high" else NORMAL_ETA
    t = {
        "ticket_id":      ticket_id or str(uuid.uuid4()),
        "from":           sender,
        "to":             "infra",
        "message":        message,
        "priority":       priority,
        "status":         "OPEN",
        "created_at":     now_utc.isoformat(),
        "ack_deadline":   (now_utc + timedelta(seconds=ACK_TIMEOUT)).isoformat(),
        "eta_min":        eta_min,
        "history":        [{"event": "CREATED", "at": now_utc.isoformat(), "by": sender}],
    }
    tickets.append(t)
    save_tickets(tickets)
    return t


def auto_ack(ticket, eta_override=None):
    eta_min = eta_override or ticket.get("eta_min", NORMAL_ETA)
    next_upd = now_utc + timedelta(minutes=min(eta_min, 5))
    ticket["status"]          = "IN_PROGRESS"
    ticket["ack_at"]          = now_utc.isoformat()
    ticket["ack_type"]        = "auto"
    ticket["owner"]           = "infra"
    ticket["eta_min"]         = eta_min
    ticket["next_update_at"]  = next_upd.isoformat()
    ticket["history"].append({
        "event":   "ACK",
        "at":      now_utc.isoformat(),
        "by":      "infra",
        "detail":  f"RECEIVED | ETA={eta_min}min | next_update={next_upd.strftime('%H:%M')} UTC"
    })
    # Add to worklist
    wl = load_worklist()
    if not any(w["ticket_id"] == ticket["ticket_id"] for w in wl):
        wl.append({"ticket_id": ticket["ticket_id"], "priority": ticket["priority"],
                   "added_at": now_utc.isoformat()})
        save_worklist(wl)
    return ticket


def escalate_incident(ticket, reason):
    ticket["status"]  = "INCIDENT"
    ticket["history"].append({
        "event":   "ESCALATED_TO_INCIDENT",
        "at":      now_utc.isoformat(),
        "by":      "infra_auto",
        "reason":  reason
    })
    return ticket


def update_progress(ticket, progress):
    eta_min = ticket.get("eta_min", NORMAL_ETA)
    next_upd = now_utc + timedelta(minutes=min(eta_min, 5))
    ticket["next_update_at"] = next_upd.isoformat()
    ticket["history"].append({
        "event":  "PROGRESS",
        "at":     now_utc.isoformat(),
        "by":     "infra",
        "detail": progress
    })
    return ticket


def resolve_ticket(ticket, summary):
    ticket["status"]      = "RESOLVED"
    ticket["resolved_at"] = now_utc.isoformat()
    ticket["resolution"]  = summary
    ticket["history"].append({
        "event":  "RESOLVED",
        "at":     now_utc.isoformat(),
        "by":     "infra",
        "detail": summary
    })
    # Remove from worklist
    wl = [w for w in load_worklist() if w["ticket_id"] != ticket["ticket_id"]]
    save_worklist(wl)
    return ticket


# ─── poll loop (deterministic, budget-exempt) ─────────────────────────────────

def poll():
    tickets = load_tickets()
    actions = []

    for t in tickets:
        status = t.get("status")

        # 1. OPEN → auto-ACK (must happen within ACK_TIMEOUT)
        if status == "OPEN":
            created = datetime.fromisoformat(t["created_at"])
            age_sec = (now_utc - created).total_seconds()
            if age_sec > ACK_TIMEOUT:
                # Overdue ACK → escalate immediately
                t = escalate_incident(t, f"ACK overdue by {int(age_sec - ACK_TIMEOUT)}s")
                actions.append({"action": "INCIDENT", "ticket_id": t["ticket_id"],
                                 "reason": "overdue_ack"})
            else:
                t = auto_ack(t)
                actions.append({"action": "AUTO_ACK", "ticket_id": t["ticket_id"],
                                 "eta_min": t["eta_min"]})

        # 2. IN_PROGRESS → check next_update_at
        elif status == "IN_PROGRESS":
            next_upd_str = t.get("next_update_at")
            if next_upd_str:
                next_upd = datetime.fromisoformat(next_upd_str)
                if now_utc > next_upd:
                    overdue_min = int((now_utc - next_upd).total_seconds() / 60)
                    t = update_progress(t, f"仍在处理中 — overdue {overdue_min}min, still working")
                    actions.append({"action": "PROGRESS_UPDATE", "ticket_id": t["ticket_id"]})

    save_tickets(tickets)
    result = {
        "status":    "ok",
        "polled_at": now_utc.isoformat(),
        "actions":   actions,
        "open":      sum(1 for t in tickets if t["status"] == "OPEN"),
        "in_progress": sum(1 for t in tickets if t["status"] == "IN_PROGRESS"),
        "incidents": sum(1 for t in tickets if t["status"] == "INCIDENT"),
        "resolved":  sum(1 for t in tickets if t["status"] == "RESOLVED"),
    }
    print(json.dumps(result))


# ─── CLI ─────────────────────────────────────────────────────────────────────

def find_ticket(tickets, tid):
    for t in tickets:
        if t["ticket_id"] == tid or t["ticket_id"].startswith(tid):
            return t
    return None


def cmd_status():
    tickets = load_tickets()
    by_status = {}
    for t in tickets:
        by_status.setdefault(t["status"], []).append(t)
    summary = {s: len(v) for s, v in by_status.items()}
    incidents = by_status.get("INCIDENT", [])
    open_t    = by_status.get("OPEN", [])
    in_prog   = by_status.get("IN_PROGRESS", [])
    print(json.dumps({
        "summary":    summary,
        "incidents":  [{"id": t["ticket_id"][:16], "msg": t["message"][:60]} for t in incidents],
        "open":       [{"id": t["ticket_id"][:16], "msg": t["message"][:60]} for t in open_t],
        "in_progress":[{"id": t["ticket_id"][:16], "msg": t["message"][:60],
                        "next_update": t.get("next_update_at","")} for t in in_prog],
    }, indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "write":
        msg      = sys.argv[2] if len(sys.argv) > 2 else "ping"
        sender   = next((sys.argv[i+1] for i,a in enumerate(sys.argv) if a == "--from"    and i+1 < len(sys.argv)), "manager")
        priority = next((sys.argv[i+1] for i,a in enumerate(sys.argv) if a == "--priority" and i+1 < len(sys.argv)), "normal")
        tid      = next((sys.argv[i+1] for i,a in enumerate(sys.argv) if a == "--id"       and i+1 < len(sys.argv)), None)
        t = write_ticket(msg, sender, priority, tid)
        print(json.dumps({"status": "ok", "ticket_id": t["ticket_id"], "priority": priority}))

    elif cmd == "poll":
        poll()

    elif cmd == "ack":
        tid  = sys.argv[2]
        eta  = int(sys.argv[sys.argv.index("--eta")+1]) if "--eta" in sys.argv else None
        tickets = load_tickets()
        t = find_ticket(tickets, tid)
        if t:
            t = auto_ack(t, eta)
            save_tickets(tickets)
            print(json.dumps({"status": "ok", "ack_at": t["ack_at"]}))
        else:
            print(json.dumps({"status": "not_found"})); sys.exit(1)

    elif cmd == "update":
        tid, progress = sys.argv[2], sys.argv[3]
        tickets = load_tickets()
        t = find_ticket(tickets, tid)
        if t:
            t = update_progress(t, progress)
            save_tickets(tickets)
            print(json.dumps({"status": "ok"}))
        else:
            print(json.dumps({"status": "not_found"})); sys.exit(1)

    elif cmd == "resolve":
        tid, summary = sys.argv[2], sys.argv[3]
        tickets = load_tickets()
        t = find_ticket(tickets, tid)
        if t:
            t = resolve_ticket(t, summary)
            save_tickets(tickets)
            print(json.dumps({"status": "ok", "resolved_at": t["resolved_at"]}))
        else:
            print(json.dumps({"status": "not_found"})); sys.exit(1)

    elif cmd == "get":
        tid = sys.argv[2]
        tickets = load_tickets()
        t = find_ticket(tickets, tid)
        print(json.dumps(t if t else {"status": "not_found"}, indent=2))

    elif cmd == "status":
        cmd_status()

    else:
        print(f"Usage: infra_ticket.py write|poll|ack|update|resolve|get|status")
        sys.exit(1)
