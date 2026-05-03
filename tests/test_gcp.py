#!/usr/bin/env python3
"""
Test: GCP BigQuery connectivity and all 7 tables
Run: python3 tests/test_gcp.py
"""
import sys, os, json, uuid, time
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/shared/tools'))

PASS = []; FAIL = []

def ok(name): PASS.append(name); print(f"  ✅ {name}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")

print("=== TEST: GCP BigQuery ===\n")

# 1. Import
try:
    from gcp_client import insert_rows, log_decision, log_token_usage, log_handoff, get_token
    ok("import gcp_client")
except Exception as e:
    fail("import gcp_client", e); sys.exit(1)

# 2. Auth token
try:
    token = get_token()
    assert token and len(token) > 20
    ok("GCP auth token")
except Exception as e:
    fail("GCP auth token", e); sys.exit(1)

# 3. Table row counts (connectivity check)
import urllib.request
PROJECT = "example-gcp-project"
TABLES = ["decisions","token_usage","trade_plans","risk_reviews","execution_logs","context_handoffs","bot_states"]

def bq_count(table):
    req = urllib.request.Request(
        f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/queries",
        data=json.dumps({"query":f"SELECT COUNT(*) FROM `{PROJECT}.trading_firm.{table}`","useLegacySql":False}).encode(),
        headers={"Authorization":f"Bearer {get_token()}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return int(float(json.loads(r.read())["rows"][0]["f"][0]["v"]))

for t in TABLES:
    try:
        n = bq_count(t)
        ok(f"table:{t} ({n} rows)")
    except Exception as e:
        fail(f"table:{t}", e)

# 4. Write tests (one row per table)
TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
RID = str(uuid.uuid4())[:8]

tests = [
    ("decisions", [{"event_id":f"TST-{RID}","timestamp":TS,"bot":"test","decision_type":"test_write",
        "summary":"automated test","session_id":RID,"payload":"{}","risk_status":"ok","token_cost":0.0}]),
    ("token_usage", [{"timestamp":TS,"bot":"test","model":"test/model",
        "input_tokens":1,"output_tokens":1,"cost_usd":0.000001,"session_id":RID,"task_type":"test"}]),
    ("risk_reviews", [{"review_id":f"RSK-{RID}","timestamp":TS,"plan_id":f"PLN-{RID}",
        "decision":"Approve","reason":"test","risk_score":0.1,"portfolio_impact":"0%","modified_order":"{}"}]),
    ("context_handoffs", [{"handoff_id":f"HO-{RID}","timestamp":TS,"bot":"test",
        "session_id":RID,"last_checkpoint":"test→test","context_summary":"test",
        "next_action":"none","full_context":"{}"}]),
    ("bot_states", [{"bot":"test","timestamp":TS,"status":"test","current_task":"pytest",
        "last_decision":"none","session_id":RID}]),
]

for table, rows in tests:
    try:
        r = insert_rows(table, rows)
        assert not r.get("insertErrors"), r.get("insertErrors")
        ok(f"write:{table}")
    except Exception as e:
        fail(f"write:{table}", e)

# 5. log_handoff helper
try:
    r = log_handoff("test", "test", "test handoff", {"x":1}, RID)
    assert not r.get("insertErrors")
    ok("log_handoff()")
except Exception as e:
    fail("log_handoff()", e)

print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
sys.exit(0 if not FAIL else 1)
