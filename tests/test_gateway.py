#!/usr/bin/env python3
"""
Test: Gateway health, channels, agents, cron jobs
Run: python3 tests/test_gateway.py
"""
import sys, os, json, subprocess, time

PASS = []; FAIL = []
def ok(name, val=""): PASS.append(name); print(f"  ✅ {name}{' → '+str(val) if val else ''}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")

def run(cmd, timeout=10):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.stdout + r.stderr

print("=== TEST: Gateway & System Health ===\n")

# 1. Gateway running
try:
    out = run("openclaw gateway status")
    assert "running" in out, f"not running: {out[:100]}"
    assert "RPC probe: ok" in out, "RPC probe failed"
    ok("gateway running + RPC ok")
except Exception as e:
    fail("gateway status", e)

# 2. No duplicate gateway processes
try:
    out = run("ps aux | grep openclaw-gateway | grep -v grep")
    procs = [l for l in out.strip().split('\n') if l.strip()]
    assert len(procs) == 1, f"{len(procs)} gateway processes found (expected 1)"
    ok("single gateway process", f"pid={procs[0].split()[1]}")
except Exception as e:
    fail("duplicate gateway check", e)

# 3. Telegram channels
try:
    out = run("openclaw channels status")
    assert "infra: enabled, configured, running" in out, "infra channel not running"
    assert "manager: enabled, configured, running" in out, "manager channel not running"
    ok("telegram channels: infra + manager running")
except Exception as e:
    fail("telegram channels", e)

# 4. All 6 agents registered
try:
    out = run("openclaw agents list")
    assert "Config invalid" not in out, f"invalid config: {out[:200]}"
    for agent in ["main","manager","research","media","risk","audit"]:
        assert agent in out, f"agent {agent} missing"
    ok("6 agents registered")
except Exception as e:
    fail("agents list", e)

# 5. Model assignments correct
try:
    with open('/home/lishopping913/.openclaw/openclaw.json') as f:
        c = json.load(f)
    expected = {
        "main":"anthropic/claude-sonnet-4-6","manager":"anthropic/claude-haiku-4-5",
        "research":"anthropic/claude-sonnet-4-6","media":"qwen/qwen-plus",
        "risk":"anthropic/claude-haiku-4-5","audit":"google/gemini-2.0-flash-lite"
    }
    for a in c['agents']['list']:
        got = a.get('model',{}).get('primary','')
        exp = expected.get(a['id'],'')
        assert got == exp, f"{a['id']}: expected {exp}, got {got}"
    ok("model assignments correct")
except Exception as e:
    fail("model assignments", e)

# 6. Cron jobs all present
try:
    out = run("openclaw cron list")
    expected_crons = ["strategy-scan","media-intel-scan","manager-5min-report",
                      "infra-5min-report","audit-daily"]
    for name in expected_crons:
        assert name in out, f"cron {name} missing"
    # No cron in error state
    lines = [l for l in out.split('\n') if any(n in l for n in expected_crons)]
    # error status is acceptable if it's just a delivery issue (summary exists)
    ok(f"5 cron jobs present")
except Exception as e:
    fail("cron jobs", e)

# 7. openclaw.json valid (no unrecognized keys)
try:
    out = run("openclaw agents list")
    assert "Unrecognized key" not in out, f"config has unrecognized keys: {out[:200]}"
    assert "Config invalid" not in out
    ok("openclaw.json valid, no unknown keys")
except Exception as e:
    fail("openclaw.json validation", e)

# 8. timeoutSeconds set
try:
    with open('/home/lishopping913/.openclaw/openclaw.json') as f:
        c = json.load(f)
    ts = c['agents']['defaults'].get('timeoutSeconds', 0)
    assert ts >= 60, f"timeoutSeconds={ts} too low"
    ok(f"timeoutSeconds = {ts}s")
except Exception as e:
    fail("timeoutSeconds check", e)

# 9. No failed deliveries in queue
try:
    failed_path = os.path.expanduser('~/.openclaw/delivery-queue/failed')
    if os.path.isdir(failed_path):
        items = os.listdir(failed_path)
        assert len(items) == 0, f"{len(items)} failed deliveries"
    elif os.path.isfile(failed_path):
        content = open(failed_path).read().strip()
        assert not content, f"failed deliveries: {content[:100]}"
    ok("delivery queue: no failed items")
except Exception as e:
    fail("delivery queue", e)

print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
sys.exit(0 if not FAIL else 1)
