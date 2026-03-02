#!/usr/bin/env python3
"""
boot_policy_check.py — Deterministic boot gate for InfraBot.
Runs in <5s. No LLM. Must PASS before any LLM-capable cron resumes after gateway restart.

Usage: python3 shared/scripts/boot_policy_check.py
Output: JSON to stdout + summary written to memory/boot_policy_check.md
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# ── Paths ────────────────────────────────────────────────────────────────────
WS = os.path.expanduser("~/.openclaw/workspace")

HEARTBEAT_FILE    = os.path.join(WS, "workspace-manager/runtime_state/infra_heartbeat.json")
EVIDENCE_GATE     = os.path.join(WS, "shared/tools/evidence_gate.py")
CONFIG_CHECK      = os.path.join(WS, "shared/tools/config_check.py")
OPENCLAW_JSON     = os.path.expanduser("~/.openclaw/openclaw.json")
ARCH_LOCK         = os.path.join(WS, "ledger/ARCH_LOCK.json")
MARKET_PULSE      = os.path.join(WS, "memory/market/MARKET_PULSE.json")
TICKET_QUEUE      = os.path.join(WS, "shared/state/ticket_queue.jsonl")
BOOT_RESULT_MD    = os.path.join(WS, "memory/boot_policy_check.md")

HEARTBEAT_MAX_AGE = timedelta(minutes=5)

# ── Helpers ───────────────────────────────────────────────────────────────────

def now_utc():
    return datetime.now(timezone.utc)

def file_age(path):
    """Return age of file as timedelta, or None if file missing."""
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    return now_utc() - datetime.fromtimestamp(mtime, tz=timezone.utc)

# ── Check 1: ticket_poller heartbeat ─────────────────────────────────────────

def check_heartbeat():
    age = file_age(HEARTBEAT_FILE)
    if age is None:
        return "FAIL", f"infra_heartbeat.json missing at {HEARTBEAT_FILE}"
    if age > HEARTBEAT_MAX_AGE:
        mins = age.total_seconds() / 60
        return "FAIL", f"infra_heartbeat.json age={mins:.1f}min > 6min threshold"
    mins = age.total_seconds() / 60
    return "PASS", f"infra_heartbeat.json age={mins:.1f}min (threshold=5min)"

# ── Check 2: Evidence Gate enabled ────────────────────────────────────────────

def check_evidence_gate():
    if os.path.exists(EVIDENCE_GATE):
        return "PASS", f"evidence_gate.py found at {EVIDENCE_GATE}"
    return "FAIL", f"evidence_gate.py missing at {EVIDENCE_GATE}"

# ── Check 3: ConfigCheck available ───────────────────────────────────────────

def check_config_check():
    if os.path.exists(CONFIG_CHECK):
        return "PASS", f"config_check.py found at {CONFIG_CHECK}"
    return "FAIL", f"config_check.py missing at {CONFIG_CHECK}"

# ── Check 4: cron allowlist — all delivery=none except manager-30min-report ──

def check_cron_allowlist():
    """Parse cron/jobs.json and verify delivery policy."""
    jobs_path = os.path.expanduser("~/.openclaw/cron/jobs.json")
    if not os.path.exists(jobs_path):
        return "FAIL", f"cron/jobs.json missing at {jobs_path}"
    try:
        with open(jobs_path) as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        return "FAIL", f"jobs.json parse error: {e}"

    crons = cfg.get("jobs", [])
    if not crons:
        return "PASS", "No crons configured (nothing to check)"

    violations = []
    for cron in crons:
        name = cron.get("name", "<unnamed>")
        delivery_raw = cron.get("delivery", {})
        if isinstance(delivery_raw, dict):
            mode = delivery_raw.get("mode", "none")
        else:
            mode = str(delivery_raw) if delivery_raw else "none"
        # Only manager-30min-report may use delivery=announce
        if name == "manager-30min-report":
            if mode != "announce":
                violations.append(f"{name}: mode={mode} (must be announce)")
        else:
            if mode not in ("none", ""):
                violations.append(f"{name}: mode={mode} (must be none)")

    if violations:
        return "FAIL", "Cron delivery violations: " + "; ".join(violations)
    return "PASS", f"All {len(crons)} crons comply with delivery policy"

# ── Check 5: Archivist snapshot ───────────────────────────────────────────────

def check_arch_lock():
    if not os.path.exists(ARCH_LOCK):
        return "FAIL", f"ARCH_LOCK.json missing at {ARCH_LOCK}"
    try:
        with open(ARCH_LOCK) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return "FAIL", f"ARCH_LOCK.json parse error: {e}"

    # Count entries — ARCH_LOCK format: {generated_at, version, entries:{...}}
    if isinstance(data, dict):
        entries_val = data.get("entries", {})
        if isinstance(entries_val, dict):
            entries = len(entries_val)  # count keys in entries dict
        elif isinstance(entries_val, list):
            entries = len(entries_val)
        elif isinstance(entries_val, int):
            entries = entries_val
        else:
            # fallback: count non-meta top-level keys
            entries = len([k for k in data if k not in ("generated_at", "version", "entries")])
    elif isinstance(data, list):
        entries = len(data)
    else:
        entries = 0

    if entries == 0:
        return "FAIL", "ARCH_LOCK.json exists but has 0 entries"
    return "PASS", f"ARCH_LOCK.json present with {entries} entries"

# ── Check 6: MARKET_PULSE accessible ─────────────────────────────────────────

def check_market_pulse():
    if os.path.exists(MARKET_PULSE):
        return "PASS", f"MARKET_PULSE.json found at {MARKET_PULSE}"
    return "FAIL", f"MARKET_PULSE.json missing at {MARKET_PULSE}"

# ── Check 7: Manager→Infra channel ───────────────────────────────────────────

def check_ticket_queue():
    if os.path.exists(TICKET_QUEUE):
        return "PASS", f"ticket_queue.jsonl found at {TICKET_QUEUE}"
    return "FAIL", f"ticket_queue.jsonl missing at {TICKET_QUEUE}"

# ── Auto-create P0 ticket on failure ─────────────────────────────────────────

def create_p0_ticket(failures):
    """Append a P0 ticket to ticket_queue.jsonl for boot policy failures."""
    ticket_id = f"BOOT-P0-{uuid.uuid4().hex[:8].upper()}"
    ticket = {
        "id": ticket_id,
        "created_at": now_utc().isoformat(),
        "action": "create",
        "priority": "P0",
        "status": "open",
        "requester": "boot_policy_check",
        "title": "Boot policy check FAILED",
        "description": f"boot_policy_check.py detected {len(failures)} failure(s): {'; '.join(failures)}",
        "failures": failures,
        "auto_generated": True,
    }
    try:
        os.makedirs(os.path.dirname(TICKET_QUEUE), exist_ok=True)
        with open(TICKET_QUEUE, "a") as f:
            f.write(json.dumps(ticket) + "\n")
        return ticket_id
    except Exception as e:
        return f"TICKET_WRITE_FAILED:{e}"

# ── Write human-readable summary ──────────────────────────────────────────────

def write_summary(result):
    as_of = result["as_of"]
    status = result["boot_policy_check"]
    checks = result["checks"]
    failures = result["failures"]
    action = result["action"]

    lines = [
        f"# Boot Policy Check — {status}",
        f"**as_of:** {as_of}",
        f"**action:** {action}",
        "",
        "## Check Results",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]
    for check_name, detail in checks.items():
        status_icon = "✅ PASS" if detail.startswith("PASS") else "❌ FAIL"
        detail_text = detail[5:].strip() if detail.startswith(("PASS", "FAIL")) else detail
        lines.append(f"| {check_name} | {status_icon} | {detail_text} |")

    if failures:
        lines += ["", "## Failures", ""]
        for f in failures:
            lines.append(f"- ❌ {f}")

    lines += [
        "",
        "---",
        f"*Generated by boot_policy_check.py at {as_of}*",
    ]

    os.makedirs(os.path.dirname(BOOT_RESULT_MD), exist_ok=True)
    with open(BOOT_RESULT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    check_fns = {
        "heartbeat":    check_heartbeat,
        "evidence_gate": check_evidence_gate,
        "config_check": check_config_check,
        "cron_allowlist": check_cron_allowlist,
        "arch_lock":    check_arch_lock,
        "market_pulse": check_market_pulse,
        "ticket_queue": check_ticket_queue,
    }

    checks_result = {}
    failures = []

    for name, fn in check_fns.items():
        status, detail = fn()
        checks_result[name] = f"{status} — {detail}"
        if status == "FAIL":
            failures.append(f"{name}: {detail}")

    overall = "PASS" if not failures else "FAIL"
    as_of = now_utc().isoformat()
    ticket_id = None

    if failures:
        ticket_id = create_p0_ticket(failures)
        action = f"P0 ticket auto-created: {ticket_id}"
    else:
        action = "system nominal"

    result = {
        "boot_policy_check": overall,
        "as_of": as_of,
        "checks": checks_result,
        "failures": failures,
        "action": action,
    }

    # Write human-readable summary
    write_summary(result)

    # Output JSON to stdout
    print(json.dumps(result, indent=2))

    # Exit code: 0=PASS, 1=FAIL
    sys.exit(0 if overall == "PASS" else 1)


if __name__ == "__main__":
    main()
