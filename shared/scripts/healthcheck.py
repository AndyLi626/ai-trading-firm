#!/usr/bin/env python3
"""
healthcheck.py — InfraBot 系统健康检查脚本
运行: python3 shared/scripts/healthcheck.py
输出: memory/healthcheck_<UTC>.md + .json
"""

import json
import os
import subprocess
import sys
import importlib
from datetime import datetime, timezone

WORKSPACE = os.environ.get("HEALTHCHECK_WORKSPACE", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(WORKSPACE, 'shared', 'tools'))

CRON_JOBS_PATH = os.path.expanduser("~/.openclaw/cron/jobs.json")
HEARTBEAT_PATH = os.path.join(WORKSPACE, "workspace-manager", "runtime_state", "infra_heartbeat.json")
MARKET_PULSE_PATH = "/tmp/oc_facts/MARKET_PULSE.json"
ARCH_LOCK_PATH = os.path.join(WORKSPACE, "ledger", "ARCH_LOCK.json")
ARCH_LOCK_SCRIPT = os.path.join(WORKSPACE, "shared", "scripts", "arch_lock.py")
WHITELIST_PATH = os.path.join(WORKSPACE, "shared", "knowledge", "LEGAL_CRON_WHITELIST.md")
EVIDENCE_GATE_PATH = os.path.join(WORKSPACE, "shared", "tools", "evidence_gate.py")


def check_platform():
    """1. platform: gateway running, disk >10% free"""
    result = {"name": "platform", "checks": {}}
    # Gateway probe
    try:
        r = subprocess.run(
            ["openclaw", "gateway", "status"],
            capture_output=True, text=True, timeout=10
        )
        running = "running" in r.stdout.lower() or "rpc probe: ok" in r.stdout.lower()
        result["checks"]["gateway_running"] = "VERIFIED" if running else "FAIL"
    except Exception as e:
        result["checks"]["gateway_running"] = f"FAIL ({e})"

    # Disk space
    try:
        import shutil
        usage = shutil.disk_usage(WORKSPACE)
        free_pct = (usage.free / usage.total) * 100
        result["checks"]["disk_free_pct"] = round(free_pct, 1)
        result["checks"]["disk_free"] = "VERIFIED" if free_pct > 10 else "FAIL"
    except Exception as e:
        result["checks"]["disk_free"] = f"FAIL ({e})"

    result["status"] = "PASS" if all(
        v in ("VERIFIED", "EXISTS", "WIRED") or (isinstance(v, (int, float)) and v > 0)
        for k, v in result["checks"].items() if k not in ("disk_free_pct",)
    ) else "FAIL"
    return result


def check_ticket_poller():
    """2. ticket_poller: heartbeat age < 2min"""
    result = {"name": "ticket_poller", "checks": {}}
    if not os.path.exists(HEARTBEAT_PATH):
        result["checks"]["heartbeat_file"] = "FAIL (file missing)"
        result["heartbeat_age_s"] = None
        result["status"] = "FAIL"
        return result

    result["checks"]["heartbeat_file"] = "EXISTS"
    try:
        with open(HEARTBEAT_PATH) as f:
            hb = json.load(f)
        last_update = hb.get("last_update", hb.get("timestamp", None))
        if last_update:
            ts = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
            age_s = (datetime.now(timezone.utc) - ts).total_seconds()
            result["heartbeat_age_s"] = round(age_s, 1)
            result["checks"]["heartbeat_age"] = "VERIFIED" if age_s < 120 else f"FAIL (age={age_s:.0f}s > 120s)"
        else:
            result["checks"]["heartbeat_age"] = "FAIL (no timestamp)"
    except Exception as e:
        result["checks"]["heartbeat_age"] = f"FAIL ({e})"

    result["status"] = "PASS" if all(
        "FAIL" not in str(v) for v in result["checks"].values()
    ) else "FAIL"
    return result


def check_cron_allowlist():
    """3. cron_allowlist: LEGAL_CRON_WHITELIST.md vs jobs.json delivery"""
    result = {"name": "cron_allowlist", "checks": {}}

    result["checks"]["whitelist_file"] = "EXISTS" if os.path.exists(WHITELIST_PATH) else "FAIL"

    ALLOWED_DELIVERIES = {"none", "log"}
    WHITELIST_ANNOUNCE_EXEMPT = {"manager-30min-report"}  # ADR-001 exempt

    violations = []
    try:
        with open(CRON_JOBS_PATH) as f:
            data = json.load(f)
        jobs = data.get("jobs", [])
        for job in jobs:
            name = job.get("name", "?")
            delivery = job.get("delivery", {})
            if isinstance(delivery, dict):
                mode = delivery.get("mode", "none")
            else:
                mode = str(delivery)
            if mode not in ALLOWED_DELIVERIES and name not in WHITELIST_ANNOUNCE_EXEMPT:
                violations.append(f"{name}:delivery={mode}")
        result["checks"]["delivery_compliance"] = "VERIFIED" if not violations else f"FAIL (violations: {violations})"
        result["violations"] = violations
    except Exception as e:
        result["checks"]["delivery_compliance"] = f"FAIL ({e})"

    result["status"] = "PASS" if all(
        "FAIL" not in str(v) for v in result["checks"].values()
    ) else "FAIL"
    return result


def check_model_runtime():
    """4. model_runtime: 读最近 cron runs 中 model 字段"""
    result = {"name": "model_runtime", "checks": {}}

    # 尝试从 jobs.json state 中读取最近执行信息
    try:
        with open(CRON_JOBS_PATH) as f:
            data = json.load(f)
        jobs = data.get("jobs", [])
        recent_ok = []
        recent_err = []
        for job in jobs:
            state = job.get("state", {})
            status = state.get("lastRunStatus", "?")
            name = job.get("name", "?")
            agent = job.get("agentId", "?")
            if status == "ok":
                recent_ok.append(f"{name}({agent})")
            elif status == "error":
                err = state.get("lastError", "")
                recent_err.append(f"{name}({agent}): {err[:80]}")

        result["checks"]["cron_state_readable"] = "VERIFIED"
        result["recent_ok"] = recent_ok[:5]
        result["recent_errors"] = recent_err[:3]
        result["checks"]["model_evidence"] = "WIRED (via cron lastRunStatus; actual model= field requires run logs)"
    except Exception as e:
        result["checks"]["cron_state_readable"] = f"FAIL ({e})"

    result["status"] = "PASS" if all(
        "FAIL" not in str(v) for v in result["checks"].values()
    ) else "FAIL"
    return result


def check_market_pulse():
    """5. market_pulse: MARKET_PULSE.json age < 5min — INFRA-004"""
    result = {"name": "market_pulse", "checks": {}}

    if not os.path.exists(MARKET_PULSE_PATH):
        result["checks"]["market_pulse_file"] = "FAIL (missing)"
        result["status"] = "FAIL"
        return result

    result["checks"]["market_pulse_file"] = "EXISTS"
    try:
        with open(MARKET_PULSE_PATH) as f:
            mp = json.load(f)
        gen_at = mp.get("generated_at", mp.get("as_of", None))
        if gen_at:
            ts = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - ts).total_seconds() / 60
            result["age_min"] = round(age_min, 1)
            result["generated_at"] = gen_at
            result["checks"]["freshness"] = "VERIFIED" if age_min < 5 else f"FAIL (age={age_min:.1f}min > 5min)"
        else:
            result["checks"]["freshness"] = "FAIL (no timestamp)"
    except Exception as e:
        result["checks"]["freshness"] = f"FAIL ({e})"

    result["status"] = "PASS" if all(
        "FAIL" not in str(v) for v in result["checks"].values()
    ) else "FAIL"
    return result


def check_archivist():
    """6. archivist: ARCH_LOCK.json exists + entries > 0 + drift=0"""
    result = {"name": "archivist", "checks": {}}

    result["checks"]["arch_lock_file"] = "EXISTS" if os.path.exists(ARCH_LOCK_PATH) else "FAIL"
    if not os.path.exists(ARCH_LOCK_PATH):
        result["status"] = "FAIL"
        return result

    try:
        with open(ARCH_LOCK_PATH) as f:
            lock = json.load(f)
        entries = lock.get("entries", [])
        result["entries_count"] = len(entries)
        result["checks"]["entries_gt_0"] = "VERIFIED" if len(entries) > 0 else "FAIL (entries=0)"
    except Exception as e:
        result["checks"]["entries_readable"] = f"FAIL ({e})"

    # Run drift check
    try:
        r = subprocess.run(
            ["python3", ARCH_LOCK_SCRIPT, "check"],
            capture_output=True, text=True, timeout=15, cwd=WORKSPACE
        )
        drift_data = json.loads(r.stdout)
        drift_count = drift_data.get("drift_count", -1)
        status = drift_data.get("status", "?")
        result["drift_count"] = drift_count
        result["drift_status"] = status
        result["checks"]["arch_lock_drift"] = "VERIFIED" if drift_count == 0 else f"FAIL (drift_count={drift_count}, status={status})"
    except Exception as e:
        result["checks"]["arch_lock_drift"] = f"FAIL ({e})"

    result["status"] = "PASS" if all(
        "FAIL" not in str(v) for v in result["checks"].values()
    ) else "FAIL"
    return result


def check_evidence_gate():
    """7. evidence_gate: shared/tools/evidence_gate.py exists and importable"""
    result = {"name": "evidence_gate", "checks": {}}

    result["checks"]["evidence_gate_file"] = "EXISTS" if os.path.exists(EVIDENCE_GATE_PATH) else "FAIL"
    if not os.path.exists(EVIDENCE_GATE_PATH):
        result["status"] = "FAIL"
        return result

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("evidence_gate", EVIDENCE_GATE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result["checks"]["evidence_gate_import"] = "VERIFIED"
    except Exception as e:
        result["checks"]["evidence_gate_import"] = f"FAIL ({e})"

    result["status"] = "PASS" if all(
        "FAIL" not in str(v) for v in result["checks"].values()
    ) else "FAIL"
    return result


def main():
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    checks = [
        check_platform(),
        check_ticket_poller(),
        check_cron_allowlist(),
        check_model_runtime(),
        check_market_pulse(),
        check_archivist(),
        check_evidence_gate(),
    ]

    pass_count = sum(1 for c in checks if c.get("status") == "PASS")
    total = len(checks)

    # Write JSON
    output_json = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "pass_count": pass_count,
        "total": total,
        "checks": checks
    }
    json_path = os.path.join(WORKSPACE, "memory", f"healthcheck_{now_utc}.json")
    with open(json_path, "w") as f:
        json.dump(output_json, f, indent=2, ensure_ascii=False)

    # Write MD
    lines = [
        f"# Healthcheck Report — {now_utc}",
        f"**Pass率: {pass_count}/{total}**",
        "",
        "| # | 检查项 | 状态 | 详情 |",
        "|---|-------|------|------|",
    ]
    for i, c in enumerate(checks, 1):
        status = c.get("status", "?")
        icon = "✅" if status == "PASS" else "❌"
        details = "; ".join(f"{k}={v}" for k, v in c.get("checks", {}).items())
        lines.append(f"| {i} | {c['name']} | {icon} {status} | {details[:120]} |")

    lines += ["", "## 详细结果", "```json", json.dumps(output_json, indent=2, ensure_ascii=False), "```"]

    md_path = os.path.join(WORKSPACE, "memory", f"healthcheck_{now_utc}.md")
    with open(md_path, "w") as f:
        f.write("\n".join(lines))

    print(f"✅ Healthcheck 完成: {pass_count}/{total} PASS")
    print(f"   MD:   {md_path}")
    print(f"   JSON: {json_path}")

    for c in checks:
        icon = "✅" if c.get("status") == "PASS" else "❌"
        print(f"  {icon} {c['name']}: {c.get('status')}")

    return 0 if pass_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
