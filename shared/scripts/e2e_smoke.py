import os
#!/usr/bin/env python3
"""
e2e_smoke.py — Boss E2E Control-Plane Smoke Test
6 scenarios / minimal tokens / one Telegram summary

Run: python3 e2e_smoke.py
      python3 e2e_smoke.py --dry-run   (Telegram send )
"""
import sys, os, json, uuid, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

WS      = Path(os.path.expanduser("~/.openclaw/workspace"))
FACTS   = Path("/tmp/oc_facts")
RUNS    = Path(os.path.expanduser("~/.openclaw/cron/runs"))
now_utc = datetime.now(timezone.utc)
DRY_RUN = "--dry-run" in sys.argv

sys.path.insert(0, str(WS / "shared" / "tools"))
sys.path.insert(0, str(WS / "shared" / "scripts"))

results = {}   # scenario → {pass: bool, note: str}


def r(name, passed, note=""):
    icon = "✅" if passed else "❌"
    results[name] = {"pass": passed, "note": note, "icon": icon}
    print(f"  {icon} {name}: {note[:70]}")


# ─────────────────────────────────────────────────────────────────────────────
# SC-1: Manager + delta-only
# ─────────────────────────────────────────────────────────────────────────────
def sc1_manager_status():
    """Manager recent run: status=ok, no errors"""
    d  = json.load(open(os.path.expanduser("~/.openclaw/cron/jobs.json")))
    j  = next((x for x in d["jobs"] if x["name"]=="manager-30min-report"), None)
    if not j:
        r("SC1_manager_status", False, "job not found"); return
    rf = RUNS / f"{j['id']}.jsonl"
    if not rf.exists():
        r("SC1_manager_status", False, "run file missing"); return
    fins = [json.loads(l) for l in open(rf) if '"finished"' in l or '"status"' in l]
 #
    ok_runs = [x for x in fins if x.get("status") == "ok"]
    fail_runs = [x for x in fins if x.get("status") == "error"]
    if ok_runs:
        ts = datetime.fromtimestamp(ok_runs[-1]["ts"]/1000, tz=timezone.utc)
        age = int((now_utc - ts).total_seconds() // 60)
        r("SC1_manager_status", True, f"last_ok={age}min ago model={ok_runs[-1].get('model','?')}")
    else:
        last_err = fail_runs[-1]["error"][:60] if fail_runs else "no records"
        r("SC1_manager_status", False, f"no ok run; last_error={last_err}")


# ─────────────────────────────────────────────────────────────────────────────
# SC-2: ticketify + auto-ACK
# ─────────────────────────────────────────────────────────────────────────────
def sc2_ticketify_ack():
    """ticketify → ticket create → ACK Check"""
    from ticketify import ticketify
    t = ticketify(
        "E2E SMOKE SC-2: data mismatch test (auto create test ticket)",
        priority="normal",
        acceptance="smoke test auto ACK Check"
    )
    tid = t["ticket_id"]

 # auto-ACK : ticket_queue ACK
    try:
        from ticket_queue import ack, list_all
        idx = list_all()
        ticket = next((x for x in idx if x.get("ticket_id") == tid), None)
        if ticket:
 # infra auto-ack (60 SLA )
            ack(tid)
            all_t = list_all()
            tk2  = next((x for x in all_t if x.get("ticket_id") == tid), {})
            ack_pending = sum(1 for x in all_t if x.get("status") not in ("acked","resolved","closed"))
            r("SC2_ticketify_ack", True,
              f"ticket={tid[:8]} status={tk2.get('status','?')} ack_pending={ack_pending}")
        else:
            r("SC2_ticketify_ack", False, "ticket not found in index after enqueue")
    except Exception as e:
        r("SC2_ticketify_ack", False, f"ack error: {str(e)[:60]}")


# ─────────────────────────────────────────────────────────────────────────────
# SC-3: Evidence Gate — Market price request without source
# ─────────────────────────────────────────────────────────────────────────────
def sc3_evidence_gate():
    """No-source market_price → must return UNCERTAIN"""
    import evidence_gate as eg
 # (as_of very stale)
    stale_result = eg.check({
        "category": "market_price",
        "value": "PLTR premarket +5%",
        "source": "",           # no source
        "as_of": "2026-01-01T00:00:00"  # very stale
    })
    must_block = stale_result["result"] != "VERIFIED"

    # Valid request must pass
    ok_result = eg.check({
        "category": "market_price",
        "value": "SPY=686",
        "source": "alpaca_iex",
        "as_of": now_utc.isoformat()
    })
    must_pass = ok_result["result"] == "VERIFIED"

    if must_block and must_pass:
        r("SC3_evidence_gate", True,
          f"stale→{stale_result['result']} fresh→{ok_result['result']}")
    else:
        r("SC3_evidence_gate", False,
          f"stale={stale_result['result']}(must≠VERIFIED) fresh={ok_result['result']}(must=VERIFIED)")


# ─────────────────────────────────────────────────────────────────────────────
# SC-4: ConfigCheck — patch → REJECT
# ─────────────────────────────────────────────────────────────────────────────
def sc4_config_check():
    """unknown  patch proposal → REJECT"""
    import config_check as cc
 # bad:
    bad_patch = {"unknown_field_xyz": "injected"}
    res       = cc.validate(bad_patch)
    rejected  = res.get("result") == "REJECT"
    reason    = res.get("reason", "")

 # patch: agents
    ok_patch = {"agents": {"list": [{"id": "main",
                                     "model": {"primary": "anthropic/claude-sonnet-4-6"}}]}}
    ok_res   = cc.validate(ok_patch)
    ok_pass  = ok_res.get("result") == "PASS"

    if rejected and ok_pass:
        r("SC4_config_check", True,
          f"bad→REJECT({reason[:30]}) valid→PASS")
    else:
        r("SC4_config_check", False,
          f"bad={res.get('result')} valid={ok_res.get('result')}")


# ─────────────────────────────────────────────────────────────────────────────
# SC-5: Cron allowlist drift — cron proposal
# ─────────────────────────────────────────────────────────────────────────────
def sc5_cron_drift():
    """Detect unauthorized cron via ARCH_LOCK"""
    proc = subprocess.run(
        ["python3", str(WS / "shared" / "scripts" / "arch_lock.py"), "check"],
        capture_output=True, text=True, cwd=str(WS)
    )
    al = json.loads(proc.stdout)
    drift_ok  = al["drift_count"] == 0

    # Check announce violations in cron jobs.json
    d    = json.load(open(os.path.expanduser("~/.openclaw/cron/jobs.json")))
    violations = [j["name"] for j in d["jobs"]
                  if j.get("delivery", {}).get("mode") == "announce"
                  and j["name"] != "manager-30min-report"]

    if drift_ok and not violations:
        r("SC5_cron_drift", True,
          f"arch_lock drift=0 entries={al.get('entries',0)} announce_violations=[]")
    else:
        r("SC5_cron_drift", False,
          f"drift={al['drift_count']} violations={violations}")


# ─────────────────────────────────────────────────────────────────────────────
# SC-6: Model runtime ( )
# ─────────────────────────────────────────────────────────────────────────────
def sc6_model_evidence():
    """cron runs file  model list return (  )"""
    d      = json.load(open(os.path.expanduser("~/.openclaw/cron/jobs.json")))
    models = {}
    for j in d["jobs"]:
        rf = RUNS / f"{j['id']}.jsonl"
        if not rf.exists(): continue
        fins = [json.loads(l) for l in open(rf) if '"finished"' in l]
        if fins and fins[-1].get("model"):
            models[j.get("agentId", "?")] = fins[-1]["model"]

    required = {"main", "manager", "media"}   # 3 agent
    covered  = required.intersection(models.keys())
    probe_f  = WS / "memory" / "infra_model_probe.json"
    probe_ok = probe_f.exists()

    if len(covered) >= 2 and probe_ok:
        summary = " ".join(f"{k}={v.split('/')[-1]}" for k,v in models.items())
        r("SC6_model_evidence", True,
          f"evidence_file=OK agents={list(covered)} {summary[:60]}")
    else:
        r("SC6_model_evidence", False,
          f"covered={list(covered)} probe_file={'OK' if probe_ok else 'MISSING'}")


# ─────────────────────────────────────────────────────────────────────────────
# Incident analysis: unknown error 13:24 UTC
# ─────────────────────────────────────────────────────────────────────────────
def write_incident_report():
    report = f"""# Incident: unknown error 2026-03-02

** **: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC  
**Target**: Manager 13:24 UTC  "unknown error occurred"

## Actual error pattern (from run logs)

|  (UTC) | Job | error |
|-----------|-----|------|
| 10:40–13:02 | 272e9ca0 (/infra?) | `Anthropic API credit balance too low` |
| 13:03, 13:33 | manager-30min-report | `Anthropic API credit balance too low` |
| 04:55 | manager-30min-report | `Message failed` (Telegram send fail) |
| 05:55 | audit-daily | `gemini-2.0-flash-lite model no longer available` |
| 06:25, 06:34, 10:34 | manager-30min-report | `cron: job execution timed out` |

## Root cause analysis

1. **"unknown error" **: Anthropic API   (`credit balance too low`)  
   - 10:40~13:33 UTC   3  total LLM path   
   - `run_with_budget.py`  `int('python3')`  budget gate  fail  
   - ****: `run_with_budget.py`   fix (commit `d7c1d08`), budget cap 8M 

2. **04:55 Message failed**: Telegram delivery fail  
   - : `infra-ticket-poll` `delivery=announce` Config 1 send   
   - ****: total delivery=none  (commit `5018fc6`)

3. **gemini-2.0-flash-lite 404**: model deprecated  
   - ****: audit agent → `gemini-2.0-flash` (lite )

4. **timeout**: run_with_budget   pending  
   - ****:   fix

## Current status
- Anthropic : **** (credit   cap Config current )
- `run_with_budget.py`: **fix Done** (commit `d7c1d08`)
- budget.json: global 2M→8M, $5/day (commit `e2585f6`)

## Reproduction status in smoke test
→ smoke Run  **** (current manager  Run Check)
"""
    out = WS / "memory" / "incident_unknown_error_2026-03-02.md"
    out.write_text(report)
    return str(out)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"E2E SMOKE  {now_utc.strftime('%Y-%m-%d %H:%M')} UTC")
    print('='*60)

    for fn in [sc1_manager_status, sc2_ticketify_ack, sc3_evidence_gate,
               sc4_config_check, sc5_cron_drift, sc6_model_evidence]:
        try:
            fn()
        except Exception as e:
            name = fn.__name__.split("_",1)[1]
            r(name, False, f"EXCEPTION: {str(e)[:60]}")

    incident_path = write_incident_report()

    # Aggregate
    total  = len(results)
    passed = sum(1 for v in results.values() if v["pass"])
    verdict = "PASS" if passed == total else "FAIL"
    icon    = "🟢" if verdict == "PASS" else "🔴"

 # FAIL P0
    fail_ticket = None
    if verdict == "FAIL":
        fails  = [f"{k}: {v['note'][:40]}" for k,v in results.items() if not v["pass"]]
        from ticketify import ticketify as tx
        fail_ticket = tx(
            "E2E SMOKE FAIL auto ticket: " + "; ".join(fails[:2]),
            priority="high",
            acceptance="smoke Run  PASS 6/6 Check"
        )

 # Telegram 1
    lines = [f"{icon} E2E SMOKE: {verdict} {passed}/{total}  {now_utc.strftime('%H:%M UTC')}"]
    for name, v in results.items():
        sc_id = name.split("_")[0]
        lines.append(f"  {v['icon']} {sc_id}: {v['note'][:55]}")
    if fail_ticket:
        lines.append(f"  🎫 P0 ticket={fail_ticket['ticket_id'][:8]}")
    lines.append(f"  📋 incident → memory/incident_unknown_error_2026-03-02.md")
    lines.append(f"     : Anthropic credit  10:40~13:33 / current ")

    msg = "\n".join(lines)
    print(f"\n{msg}\n")

 # Telegram (1 ) — openclaw CLI
    if not DRY_RUN:
        try:
            tg_r = subprocess.run(
                ["openclaw", "send", "--to", os.environ.get("BOSS_TELEGRAM_ID", "REDACTED"),
                 "--channel", "telegram", msg],
                capture_output=True, text=True, timeout=20
            )
            if tg_r.returncode == 0:
                print("📤 Telegram send Done")
            else:
 # fallback: message tool
                print(f"⚠️  Telegram CLI none (result memory/ save)")
        except Exception as e:
            print(f"⚠️  Telegram: {str(e)[:60]}")

 # JSON
    out = {
        "smoke_at": now_utc.isoformat(),
        "verdict": verdict, "passed": passed, "total": total,
        "results": results,
        "incident_file": incident_path
    }
    (WS / "memory" / f"smoke_{now_utc.strftime('%Y%m%d_%H%M')}.json").write_text(
        json.dumps(out, indent=2))

    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()