#!/usr/bin/env python3
"""
Test: ExecutionService — paper order submission, risk gate, GCP logging
Run: python3 tests/test_execution.py
"""
import sys, os, json, uuid, time
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/shared/tools'))
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/execution'))
sys.path.insert(0, os.path.expanduser('~/.openclaw/secrets'))

PASS = []; FAIL = []
def ok(name, val=""): PASS.append(name); print(f"  ✅ {name}{' → '+str(val) if val else ''}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")

print("=== TEST: ExecutionService ===\n")

TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# 1. Import
try:
    from execution_service import execute, alpaca_request
    ok("import execution_service")
except Exception as e:
    fail("import execution_service", e); sys.exit(1)

# 2. Config check
try:
    with open(os.path.expanduser('~/.openclaw/workspace/execution/config.json')) as f:
        cfg = json.load(f)
    assert cfg.get("mode") == "paper", f"mode must be paper, got: {cfg.get('mode')}"
    assert cfg.get("live_enabled") == False, "live_enabled must be False"
    assert cfg.get("hard_rules",{}).get("require_risk_approval") == True
    ok("config: paper mode only", f"mode={cfg['mode']} live={cfg['live_enabled']}")
except Exception as e:
    fail("config check", e)

# 3. Alpaca account health
try:
    resp, _ = alpaca_request("GET", "/account")
    assert "error" not in resp, f"error: {resp.get('error')}"
    assert resp.get("status") == "ACTIVE", f"account status: {resp.get('status')}"
    cash = float(resp.get("cash", 0))
    buying_power = float(resp.get("buying_power", 0))
    ok("Alpaca account", f"cash=${cash:,.0f} bp=${buying_power:,.0f}")
except Exception as e:
    fail("Alpaca account", e)

# 4. Reject order without risk approval
try:
    bad_order = {
        "order_id": str(uuid.uuid4()), "plan_id": "TEST-REJECT",
        "instrument": "SPY", "venue": "alpaca_paper",
        "direction": "long", "order_type": "market",
        "entry_price": 500.0, "stop_loss": 495.0, "take_profit": 511.0,
        "size_notional": 1000, "confidence": 0.6, "thesis": "test reject",
        "risk_approved": False, "risk_review_id": "RSK-TEST",
        "timestamp": TS
    }
    result = execute(bad_order)
    assert result["status"] == "rejected", f"expected rejected, got: {result['status']}"
    assert "risk" in result.get("error_message","").lower(), f"wrong rejection reason: {result.get('error_message')}"
    ok("risk gate: rejects unapproved order")
except Exception as e:
    fail("risk gate rejection", e)

# 5. Accept approved paper order
try:
    good_order = {
        "order_id": str(uuid.uuid4()), "plan_id": f"TST-{str(uuid.uuid4())[:6]}",
        "instrument": "SPY", "venue": "alpaca_paper",
        "direction": "long", "order_type": "market",
        "entry_price": 500.0, "stop_loss": 494.0, "take_profit": 511.0,
        "size_notional": 500, "confidence": 0.65, "thesis": "test approved order",
        "risk_approved": True, "risk_review_id": f"RSK-{str(uuid.uuid4())[:6]}",
        "timestamp": TS
    }
    result = execute(good_order)
    assert result["status"] == "accepted", f"expected accepted, got: {result['status']}"
    ok("approved order executed", f"Alpaca ID {str(result.get('alpaca_order_id',''))[:12]}")
except Exception as e:
    fail("approved order execution", e)

# 6. Verify live_enabled=False in config (live gate is config-level, not runtime)
try:
    with open(os.path.expanduser('~/.openclaw/workspace/execution/config.json')) as f:
        cfg = json.load(f)
    assert cfg.get("live_enabled") == False, "live_enabled must be False"
    assert cfg.get("hard_rules",{}).get("no_live_without_boss_approval") == True
    ok("live gate: live_enabled=False, boss_approval required in config")
except Exception as e:
    fail("live gate config check", e)

print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
sys.exit(0 if not FAIL else 1)
