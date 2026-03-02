#!/usr/bin/env python3
"""
Test: Options execution via Alpaca paper (level 3 approved)
Run: python3 tests/test_options.py
"""
import sys, os, json, uuid, time, datetime
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/shared/tools'))
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/execution'))

PASS = []; FAIL = []
def ok(name, val=""): PASS.append(name); print(f"  ✅ {name}{' → '+str(val) if val else ''}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")

print("=== TEST: Options Execution (Alpaca Paper) ===\n")

from execution_service import execute, alpaca_request, get_options_chain

TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# 1. Account options approval
try:
    resp, _ = alpaca_request("GET", "/account")
    level = resp.get("options_approved_level", 0)
    assert int(level) >= 1, f"options not approved: level={level}"
    ok("Options approved", f"level={level}")
except Exception as e:
    fail("options approval", e)

# 2. Fetch SPY options chain
try:
    # Get nearest expiry (next Friday)
    today = datetime.date.today()
    days_ahead = (4 - today.weekday()) % 7 or 7
    expiry = (today + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    chain = get_options_chain("SPY", expiry, "call")
    if not chain:
        # Try without expiry filter
        chain = get_options_chain("SPY", option_type="call")
    assert len(chain) > 0, "empty options chain"
    sample = chain[0]
    ok(f"SPY call chain", f"{len(chain)} contracts, sample strike={sample.get('strike_price')} exp={sample.get('expiration_date')}")
except Exception as e:
    fail("SPY options chain", e)

# 3. Buy SPY call (ATM, nearest expiry)
try:
    # Find ATM strike from chain
    spy_price = 570.0  # approximate
    if chain:
        atm = min(chain, key=lambda c: abs(float(c.get('strike_price', 0)) - spy_price))
        strike = float(atm.get('strike_price', spy_price))
        expiry_date = atm.get('expiration_date', expiry)
    else:
        strike = 570.0
        expiry_date = expiry

    order = {
        "order_id": str(uuid.uuid4()),
        "plan_id": f"OPT-{str(uuid.uuid4())[:6]}",
        "instrument": "SPY",
        "option_type": "call",
        "strike_price": strike,
        "expiration_date": expiry_date,
        "contracts": 1,
        "venue": "alpaca_paper_options",
        "direction": "long",
        "order_type": "market",
        "entry_price": 0,
        "stop_loss": 0,
        "take_profit": 0,
        "size_notional": 0,
        "confidence": 0.65,
        "thesis": "options test",
        "risk_approved": True,
        "risk_review_id": "RSK-OPT-TEST",
        "timestamp": TS
    }
    result = execute(order)
    # options market orders only allowed during market hours — treat as expected skip
    if result.get("status") == "error" and "market hours" in str(result.get("error_message", "")):
        ok("SPY call execution (market closed — expected skip)", "market hours restriction confirmed")
    else:
        assert result["status"] == "accepted", f"got: {result['status']} — {result.get('error_message','')}"
        ok(f"SPY call order executed", f"strike={result.get('strike_price')} exp={result.get('expiration_date')} id={str(result.get('alpaca_order_id',''))[:12]}")
except Exception as e:
    fail("SPY call execution", e)

# 4. Options routing detection
try:
    # Verify is_options routing works
    opt_order = {"order_id": str(uuid.uuid4()), "instrument": "SPY",
                 "option_type": "put", "venue": "alpaca_paper",
                 "risk_approved": False}  # Should reject at risk gate, not at routing
    result2 = execute(opt_order)
    # Should be rejected by risk gate (not routing error)
    assert result2["status"] == "rejected", f"expected risk rejection, got {result2['status']}"
    ok("Options routing detected + risk gate works")
except Exception as e:
    fail("options routing check", e)

print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
sys.exit(0 if not FAIL else 1)
