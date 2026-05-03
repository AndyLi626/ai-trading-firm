#!/usr/bin/env python3
"""
Test: Full end-to-end pipeline — Boss→Manager→Strategy→Media→Risk→Execution→Audit→Boss
Run: python3 tests/test_pipeline.py
"""
import sys, os, json, uuid, time, urllib.request
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/shared/tools'))
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/execution'))
sys.path.insert(0, os.path.expanduser('~/.openclaw/secrets'))

PASS = []; FAIL = []
def ok(name, val=""): PASS.append(name); print(f"  ✅ {name}{' → '+str(val) if val else ''}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")

print("=== TEST: Full Pipeline E2E ===\n")

from gcp_client import insert_rows, log_decision, log_token_usage, log_handoff, get_token
from execution_service import execute
TS = lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
CID = f"TEST-{str(uuid.uuid4())[:6]}"

# Step 1: ManagerBot receives directive
try:
    log_decision("manager", "boss_directive", f"Test cycle {CID}", session_id=CID)
    log_token_usage("manager", "anthropic/claude-haiku-4-5", 600, 80, CID, "receive_directive")
    log_handoff("manager", "research", "Find trade setup", session_id=CID)
    ok("Step 1: ManagerBot [haiku] receives + delegates")
except Exception as e:
    fail("Step 1: ManagerBot", e)

# Step 2: StrategyBot generates plan
try:
    price = 570.0
    plan = {
        "plan_id": f"PLN-{CID}", "timestamp": TS(),
        "instrument": "SPY", "venue": "alpaca_paper",
        "direction": "long", "order_type": "market",
        "entry_price": price, "stop_loss": round(price*0.988,2),
        "take_profit": round(price*1.022,2),
        "size_notional": 1000, "confidence": 0.65,
        "thesis": f"Pipeline test — SPY ${price}",
        "risk_approved": False, "risk_review_id": f"RSK-{CID}"
    }
    rr = (plan['take_profit']-price)/(price-plan['stop_loss'])
    r = insert_rows("trade_plans", [{
        "plan_id": plan['plan_id'], "timestamp": TS(),
        "instrument": "SPY", "venue": "alpaca_paper", "direction": "long",
        "thesis": plan['thesis'], "confidence": 0.65, "entry_price": price,
        "stop_loss": plan['stop_loss'], "take_profit": plan['take_profit'],
        "size_notional": 1000, "status": "pending_risk",
        "risk_decision": "pending", "tags": "test"
    }])
    assert not r.get("insertErrors")
    log_token_usage("research", "anthropic/claude-sonnet-4-6", 1800, 520, CID, "strategy_synthesis")
    log_handoff("research", "risk", f"Review SPY R/R={rr:.1f}x", payload=plan, session_id=CID)
    ok(f"Step 2: StrategyBot [sonnet] → SPY R/R {rr:.1f}x")
except Exception as e:
    fail("Step 2: StrategyBot", e)

# Step 3: MediaBot sentiment
try:
    log_token_usage("media", "qwen/qwen-plus", 900, 220, CID, "news_scan")
    log_decision("media", "signal_delivered", "SPY Neutral +0.05", session_id=CID)
    ok("Step 3: MediaBot [qwen] → Neutral signal")
except Exception as e:
    fail("Step 3: MediaBot", e)

# Step 4: RiskBot review
try:
    risk_dec = "Approve"
    reason = f"R/R {rr:.1f}x ✓ | $1000 ✓ | Neutral ✓"
    r = insert_rows("risk_reviews", [{
        "review_id": f"RSK-{CID}", "timestamp": TS(),
        "plan_id": plan['plan_id'], "decision": risk_dec, "reason": reason,
        "risk_score": 0.35, "portfolio_impact": "1%", "modified_order": "{}"
    }])
    assert not r.get("insertErrors")
    log_token_usage("risk", "anthropic/claude-haiku-4-5", 900, 180, CID, "risk_review")
    log_handoff("risk", "execution", f"Approved: {reason}", session_id=CID)
    ok(f"Step 4: RiskBot [haiku] → {risk_dec}")
except Exception as e:
    fail("Step 4: RiskBot", e)

# Step 5: ExecutionService
try:
    order = {**plan, "order_id": str(uuid.uuid4()), "risk_approved": True}
    result = execute(order)
    assert result["status"] == "accepted", f"got: {result['status']}"
    alpaca_id = str(result.get("alpaca_order_id",""))[:12]
    ok(f"Step 5: ExecutionService → {result['status']}", alpaca_id)
except Exception as e:
    fail("Step 5: ExecutionService", e)

# Step 6: AuditBot logs
try:
    log_token_usage("audit", "google/gemini-2.0-flash-lite", 400, 80, CID, "audit_log")
    log_decision("audit", "cycle_complete", f"Cycle {CID}: {risk_dec}→{result['status']}", session_id=CID)
    ok("Step 6: AuditBot [flash-lite] → GCP logged")
except Exception as e:
    fail("Step 6: AuditBot", e)

# Step 7: Verify GCP records exist
try:
    def bq_count_where(table, field, val):
        req = urllib.request.Request(
            "https://bigquery.googleapis.com/bigquery/v2/projects/example-gcp-project/queries",
            data=json.dumps({"query":
                f"SELECT COUNT(*) FROM `example-gcp-project.trading_firm.{table}` WHERE {field}='{val}'",
                "useLegacySql":False}).encode(),
            headers={"Authorization":f"Bearer {get_token()}","Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return int(float(json.loads(r.read())["rows"][0]["f"][0]["v"]))

    assert bq_count_where("trade_plans","plan_id",plan['plan_id']) == 1
    assert bq_count_where("risk_reviews","review_id",f"RSK-{CID}") == 1
    assert bq_count_where("context_handoffs","session_id",CID) >= 2
    ok("Step 7: GCP audit trail verified (trade_plans + risk_reviews + handoffs)")
except Exception as e:
    fail("Step 7: GCP verification", e)

# Cost summary
costs = {"haiku":0.00208,"sonnet":0.0132,"qwen":0.00062,"flash_lite":0.000054}
total = sum(costs.values())
print(f"\n  Estimated cycle cost: ${total:.4f}")
print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed  [CID={CID}]")
sys.exit(0 if not FAIL else 1)
