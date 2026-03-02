#!/usr/bin/env python3
"""
snapshot_capabilities.py — 只读扫描，生成 ledger/STATUS_MATRIX.md 和 ledger/CAPABILITIES.md
EXISTS / WIRED / VERIFIED 三级标注
"""
import os, sys, json, glob
from datetime import datetime, timezone

WS       = os.path.expanduser("~/.openclaw/workspace")
CRON_F   = os.path.expanduser("~/.openclaw/cron/jobs.json")
RUNS_DIR = os.path.expanduser("~/.openclaw/cron/runs")
FACTS    = "/tmp/oc_facts"
LEDGER   = os.path.join(WS, "ledger")
now_utc  = datetime.now(timezone.utc)
TODAY    = now_utc.strftime("%Y-%m-%d")

os.makedirs(LEDGER, exist_ok=True)

def load_json(p, d=None):
    try: return json.load(open(p))
    except Exception: return d or {}

def cron_jobs():
    d = load_json(CRON_F, {"jobs": []})
    return d.get("jobs", [])

def recent_run_names(hours=24):
    """Return set of job names that have a 'finished' event in last N hours."""
    cutoff_ms = (now_utc.timestamp() - hours * 3600) * 1000
    ran = set()
    for jf in glob.glob(os.path.join(RUNS_DIR, "*.jsonl")):
        try:
            for line in open(jf):
                ev = json.loads(line.strip())
                if ev.get("action") == "finished" and ev.get("ts", 0) > cutoff_ms:
                    ran.add(ev.get("jobName", ""))
        except Exception:
            pass
    return ran

def script_exists(name):
    return os.path.exists(os.path.join(WS, "shared/scripts", name))

def fact_file_recent(name, hours=24):
    p = os.path.join(FACTS, name)
    if not os.path.exists(p): return False
    age = now_utc.timestamp() - os.path.getmtime(p)
    return age < hours * 3600

# ── Inventory definitions ──────────────────────────────────────────────────────
def build_inventory():
    jobs     = cron_jobs()
    job_map  = {j["name"]: j for j in jobs}
    ran_24h  = recent_run_names(24)
    items    = []

    def add(id_, name, category, bot, trigger, script=None, output=None, budget=False):
        exists = script_exists(script) if script else (name in job_map)
        wired  = (name in job_map) or (script and script_exists(script) and
                  any(name in j.get("payload",{}).get("message","") for j in jobs))
        if script:
            wired = wired or any(
                script.replace(".py","") in j.get("payload",{}).get("message","")
                for j in jobs
            )
        verified = wired and (name in ran_24h or (output and fact_file_recent(output)))
        status = "VERIFIED" if verified else ("WIRED" if wired else ("EXISTS" if exists else "MISSING"))
        has_budget = budget or any(
            "run_with_budget" in j.get("payload",{}).get("message","")
            for j in jobs if j["name"] == name
        )
        items.append({
            "id": id_, "name": name, "category": category,
            "bot": bot, "trigger": trigger, "script": script,
            "output": output, "status": status, "has_budget": has_budget
        })

    # Cron jobs
    add("J01", "manager-30min-report",  "cron", "manager",  "every 30m", output="bot_cache.json", budget=True)
    add("J02", "media-intel-scan",      "cron", "media",    "every 15m", script="collect_media.py")
    add("J03", "strategy-scan",         "cron", "research", "every 30m", script="collect_market.py")
    add("J04", "audit-daily",           "cron", "audit",    "every 12h")
    add("J05", "infra-5min-report",     "cron", "main",     "every 12h")
    add("J06", "autonomy-orchestrator", "cron", "manager",  "every 1h",  script="autonomy_orchestrator.py")
    add("J07", "repo-skills-scan",      "cron", "research", "every 24h", script="repo_skills_scan.py")
    add("J08", "infra-12h-scan",        "cron", "infra",    "every 12h", script="infra_scan.py")
    add("J09", "emergency-scan-poll",   "cron", "media",    "every 1m",  script="emergency_scan.py")
    add("J10", "market-pulse-15m",      "cron", "media",    "every 15m", script="market_pulse.py",   output="MARKET_PULSE.json")
    add("J11", "anomaly-detector",      "cron", "media",    "every 5m",  script="market_anomaly_detector.py")

    # Scripts (standalone capabilities)
    for sc, cat, bot, out in [
        ("emergency_trigger.py",     "trigger",  "manager",  "emergency_requests.json"),
        ("emergency_scan.py",        "scan",     "media",    "emergency_scan_result.json"),
        ("strategy_hint.py",         "strategy", "research", "event_proposals.json"),
        ("risk_review_lite.py",      "risk",     "risk",     "risk_verdict.json"),
        ("run_with_budget.py",       "budget",   "infra",    None),
        ("check_budget_status.py",   "budget",   "infra",    None),
        ("token_cost_summary.py",    "reporting","infra",    "cost_summary.json"),
        ("detect_changes.py",        "pipeline", "manager",  None),
        ("config_guard.py",          "governance","infra",   None),
        ("collect_market.py",        "data",     "research", "market_facts.json"),
        ("collect_media.py",         "data",     "media",    "media_facts.json"),
        ("collect_team.py",          "data",     "infra",    "team_facts.json"),
        ("market_pulse.py",          "data",     "media",    "MARKET_PULSE.json"),
        ("market_anomaly_detector.py","detection","media",   "anomaly_events.json"),
        ("harvest_openclaw_usage.py","accounting","infra",   None),
    ]:
        name = sc.replace(".py","")
        exists_flag = script_exists(sc)
        out_fresh   = fact_file_recent(out) if out else False
        status = "VERIFIED" if (exists_flag and out_fresh) else ("WIRED" if exists_flag else "MISSING")
        items.append({
            "id": f"S{len([i for i in items if i['id'].startswith('S')])+1:02d}",
            "name": name, "category": cat, "bot": bot,
            "trigger": "manual/called", "script": sc, "output": out,
            "status": status, "has_budget": False
        })

    return items

# ── Write STATUS_MATRIX.md ─────────────────────────────────────────────────────
def write_status_matrix(items):
    lines = [
        f"# Status Matrix — {TODAY}",
        "_Auto-generated by snapshot_capabilities.py_\n",
        "| ID | Name | Category | Bot | Trigger | Status | Budget | Output |",
        "|----|------|----------|-----|---------|--------|--------|--------|"
    ]
    counts = {"VERIFIED": 0, "WIRED": 0, "EXISTS": 0, "MISSING": 0}
    for it in items:
        icon = {"VERIFIED":"✅","WIRED":"🔗","EXISTS":"📄","MISSING":"❌"}.get(it["status"],"?")
        budget = "✅" if it["has_budget"] else "—"
        out = it["output"] or "—"
        lines.append(f"| {it['id']} | `{it['name']}` | {it['category']} | {it['bot']} | {it['trigger']} | {icon} {it['status']} | {budget} | {out} |")
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    lines.append(f"\n**Summary:** ✅ VERIFIED={counts['VERIFIED']} | 🔗 WIRED={counts['WIRED']} | 📄 EXISTS={counts['EXISTS']} | ❌ MISSING={counts['MISSING']}")
    open(os.path.join(LEDGER, "STATUS_MATRIX.md"), "w").write("\n".join(lines))
    return counts

# ── Write CAPABILITIES.md ──────────────────────────────────────────────────────
def write_capabilities(items):
    by_cat = {}
    for it in items:
        by_cat.setdefault(it["category"], []).append(it)
    lines = [f"# System Capabilities — {TODAY}", "_Auto-generated_\n"]
    for cat, its in sorted(by_cat.items()):
        lines.append(f"## {cat.upper()}")
        for it in its:
            icon = {"VERIFIED":"✅","WIRED":"🔗","EXISTS":"📄","MISSING":"❌"}.get(it["status"],"?")
            lines.append(f"- {icon} **{it['name']}** ({it['bot']}) — {it['trigger']}" +
                         (f" → `{it['output']}`" if it["output"] else ""))
        lines.append("")
    open(os.path.join(LEDGER, "CAPABILITIES.md"), "w").write("\n".join(lines))

def main():
    items  = build_inventory()
    counts = write_status_matrix(items)
    write_capabilities(items)
    print(json.dumps({
        "status": "ok",
        "items": len(items),
        "counts": counts,
        "ledger_dir": LEDGER,
        "generated_at": now_utc.isoformat()
    }))

if __name__ == "__main__":
    main()
