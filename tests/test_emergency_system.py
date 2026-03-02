#!/usr/bin/env python3
"""
test_emergency_system.py — Unit tests for P0 emergency system.
Tests: 6 total
"""
import sys, os, json, uuid, subprocess, tempfile, shutil, time
from datetime import datetime, timezone, timedelta
import os

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
SCRIPTS = os.path.join(WORKSPACE, "shared", "scripts")
PY = sys.executable

# Override FACTS_DIR for tests
TEST_FACTS_DIR = tempfile.mkdtemp(prefix="oc_test_facts_")
REQUESTS_FILE = os.path.join(TEST_FACTS_DIR, "emergency_requests.json")
PULSE_FILE = os.path.join(TEST_FACTS_DIR, "MARKET_PULSE.json")

os.environ["OC_FACTS_DIR"] = TEST_FACTS_DIR  # not used by scripts but for doc

def run_trigger(symbols: list, reason: str = "test", requests_file: str = None) -> dict:
    """Run emergency_trigger.py in isolated mode by monkeypatching the file path."""
    # We'll run via subprocess and override the FACTS_DIR via env trick
    # Since scripts hardcode FACTS_DIR, we patch the file path using a wrapper
    rf = requests_file or REQUESTS_FILE
    # Write a temp wrapper
    wrapper = tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False)
    wrapper.write(f"""
import sys, os, json, uuid, argparse
from datetime import datetime, timezone, timedelta

FACTS_DIR = {repr(TEST_FACTS_DIR)}
REQUESTS_FILE = os.path.join(FACTS_DIR, "emergency_requests.json")
OPS_ALERTS_FILE = os.path.join(FACTS_DIR, "ops_alerts.json")

""")
    # Read the original script body after the imports
    src = open(os.path.join(SCRIPTS, "emergency_trigger.py")).read()
    # Strip shebang and module-level FACTS_DIR assignment
    lines = src.split("\n")
    filtered = []
    skip_next = False
    for line in lines:
        if line.startswith("#!/") or line.startswith('"""') or (
            "FACTS_DIR" in line and "=" in line and "os.path" in line and "TEST" not in line
        ) or "REQUESTS_FILE" in line or "OPS_ALERTS_FILE" in line:
            continue
        filtered.append(line)
    wrapper.write("\n".join(filtered))
    wrapper.close()

    cmd = [PY, wrapper.name] + symbols + ["--reason", reason]
    r = subprocess.run(cmd, capture_output=True, text=True)
    os.unlink(wrapper.name)
    for line in r.stdout.strip().splitlines():
        try:
            return json.loads(line)
        except Exception:
            continue
    return {}


def run_script(script: str, args: list = None) -> tuple:
    cmd = [PY, os.path.join(SCRIPTS, script)] + (args or [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


PASS = 0
FAIL = 0

def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ PASS: {name}")
    else:
        FAIL += 1
        print(f"  ❌ FAIL: {name}" + (f" — {detail}" if detail else ""))


# Use real FACTS_DIR (scripts are hardcoded)
REAL_REQUESTS_FILE = "/tmp/oc_facts/emergency_requests.json"

# ─── TEST 1: emergency_trigger writes valid request ───────────────────────────
print("\n[Test 1] emergency_trigger.py writes valid request")
# Clear state — use unique symbols to avoid dedup from previous live runs
os.makedirs("/tmp/oc_facts", exist_ok=True)
with open(REAL_REQUESTS_FILE, "w") as _f:
    json.dump([], _f)

code, out, err = run_script("emergency_trigger.py", ["PLTR", "XOM", "GLD", "--reason", "test1"])
try:
    result = json.loads(out.strip().splitlines()[-1])
except Exception:
    result = {}

check("accepted=true", result.get("accepted") is True, str(result))
check("request_id present", bool(result.get("request_id")), str(result))
check("symbols in result", "PLTR" in result.get("symbols", []), str(result))

# Verify file written
if os.path.exists(REAL_REQUESTS_FILE):
    with open(REAL_REQUESTS_FILE) as f:
        reqs = json.load(f)
    check("file has 1+ request", len(reqs) >= 1)
    req = reqs[-1]
    check("status=pending", req.get("status") == "pending")
    check("schema valid", all(k in req for k in ["request_id","symbols","requested_at","status","trigger"]))
else:
    check("file exists", False, f"{REAL_REQUESTS_FILE} missing")
    check("status=pending", False)
    check("schema valid", False)


# ─── TEST 2: Dedup — same symbols within 10min → rejected ─────────────────────
print("\n[Test 2] Dedup: same symbols within 10min → rejected")
code2, out2, err2 = run_script("emergency_trigger.py", ["PLTR", "XOM", "GLD", "--reason", "dedup_test"])
try:
    result2 = json.loads(out2.strip().splitlines()[-1])
except Exception:
    result2 = {}
check("accepted=false (dedup)", result2.get("accepted") is False, str(result2))
check("reason contains 'dedup'", "dedup" in result2.get("reason",""), str(result2))


# ─── TEST 3: Rate limit — 4th request in 60min → rejected ─────────────────────
print("\n[Test 3] Rate limit: 4th request in 60min → rejected")
# We need 3 requests already recorded with different symbols
# Clear and add 3 with different symbols
if os.path.exists("/tmp/oc_facts/emergency_requests.json"):
    with open("/tmp/oc_facts/emergency_requests.json") as f:
        reqs = json.load(f)
else:
    reqs = []

now = datetime.now(timezone.utc)
for i in range(3):
    reqs.append({
        "request_id": str(uuid.uuid4()),
        "symbols": [f"SYM{i}"],
        "reason": "fill",
        "requested_at": (now - timedelta(minutes=i+1)).isoformat(),
        "status": "done",
        "trigger": "emergency"
    })
os.makedirs("/tmp/oc_facts", exist_ok=True)
with open("/tmp/oc_facts/emergency_requests.json", "w") as f:
    json.dump(reqs, f)

code3, out3, err3 = run_script("emergency_trigger.py", ["SPY", "--reason", "rate_test"])
try:
    result3 = json.loads(out3.strip().splitlines()[-1])
except Exception:
    result3 = {}
check("accepted=false (rate_limit)", result3.get("accepted") is False, str(result3))
check("reason contains 'rate_limit'", "rate_limit" in result3.get("reason",""), str(result3))


# ─── TEST 4: market_pulse.py produces MARKET_PULSE.json ───────────────────────
print("\n[Test 4] market_pulse.py produces MARKET_PULSE.json")
code4, out4, err4 = run_script("market_pulse.py", ["SPY,PLTR,GLD"])
mp_file = "/tmp/oc_facts/MARKET_PULSE.json"
check("exit code 0", code4 == 0, f"stderr: {err4[:200]}")
check("MARKET_PULSE.json exists", os.path.exists(mp_file))
if os.path.exists(mp_file):
    with open(mp_file) as f:
        mp = json.load(f)
    check("has 'quotes' key", "quotes" in mp)
    check("has 'realtime_data' key", "realtime_data" in mp)
    check("has 'top_movers' key", "top_movers" in mp)
    check("has 'generated_at'", "generated_at" in mp)
else:
    check("has quotes", False)
    check("has realtime_data", False)
    check("has top_movers", False)
    check("has generated_at", False)


# ─── TEST 5: emergency_scan.py with no pending → no_pending ───────────────────
print("\n[Test 5] emergency_scan.py with no pending → no_pending")
# Set all requests to done
req_file = "/tmp/oc_facts/emergency_requests.json"
if os.path.exists(req_file):
    with open(req_file) as f:
        reqs = json.load(f)
    for r in reqs:
        r["status"] = "done"
    with open(req_file, "w") as f:
        json.dump(reqs, f)
else:
    with open(req_file, "w") as f:
        json.dump([], f)

code5, out5, err5 = run_script("emergency_scan.py")
try:
    result5 = json.loads(out5.strip().splitlines()[-1])
except Exception:
    result5 = {}
check("status=no_pending", result5.get("status") == "no_pending", str(result5))


# ─── TEST 6: schema valid after trigger ───────────────────────────────────────
print("\n[Test 6] emergency_requests.json schema valid after trigger")
# Clear and trigger fresh
with open(req_file, "w") as f:
    json.dump([], f)

code6, out6, err6 = run_script("emergency_trigger.py", ["QQQ", "SPY", "--reason", "schema_test"])
if os.path.exists(req_file):
    with open(req_file) as f:
        reqs = json.load(f)
    check("file is list", isinstance(reqs, list))
    if reqs:
        r = reqs[-1]
        required_keys = ["request_id", "symbols", "reason", "requested_at", "status", "trigger"]
        check("all required keys present", all(k in r for k in required_keys), str(list(r.keys())))
        check("symbols is list", isinstance(r["symbols"], list))
        check("status=pending", r["status"] == "pending")
    else:
        check("has entries", False)
        check("all required keys", False)
        check("symbols is list", False)
        check("status=pending", False)
else:
    check("file is list", False)
    check("all required keys", False)
    check("symbols is list", False)
    check("status=pending", False)


# ─── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*40}")
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} pass  ({FAIL} fail)")

# Cleanup temp dir
shutil.rmtree(TEST_FACTS_DIR, ignore_errors=True)

sys.exit(0 if FAIL == 0 else 1)