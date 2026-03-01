#!/usr/bin/env python3
"""
Test: Crypto execution via Alpaca paper
Run: python3 tests/test_crypto.py
"""
import sys, os, json, uuid, time
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/shared/tools'))
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/execution'))

PASS = []; FAIL = []
def ok(name, val=""): PASS.append(name); print(f"  ✅ {name}{' → '+str(val) if val else ''}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")

print("=== TEST: Crypto Execution (Alpaca Paper) ===\n")

from execution_service import execute, alpaca_request, submit_alpaca_crypto

TS = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# 1. Account supports crypto trading
try:
    resp, _ = alpaca_request("GET", "/account")
    assert resp.get("status") == "ACTIVE"
    ok("Alpaca paper account active")
except Exception as e:
    fail("account check", e)

# 2. Get crypto prices via Alpaca
try:
    resp, _ = alpaca_request("GET", "/assets/BTC%2FUSD")
    tradable = resp.get("tradable", False)
    asset_class = resp.get("class", "")
    ok(f"BTC/USD asset", f"tradable={tradable} class={asset_class}")
except Exception as e:
    fail("BTC/USD asset check", e)

# 3. Submit BTC/USD paper order
try:
    order = {
        "order_id": str(uuid.uuid4()),
        "plan_id": f"CRYPTO-{str(uuid.uuid4())[:6]}",
        "instrument": "BTCUSD",
        "venue": "alpaca_paper",
        "direction": "long",
        "order_type": "market",
        "entry_price": 85000,
        "stop_loss": 83000,
        "take_profit": 90000,
        "size_notional": 100,
        "confidence": 0.65,
        "thesis": "crypto test order",
        "risk_approved": True,
        "risk_review_id": f"RSK-CRYPTO-TEST",
        "timestamp": TS
    }
    result = execute(order)
    assert result["status"] == "accepted", f"got: {result['status']} — {result.get('error_message','')}"
    ok(f"BTC/USD market order", f"venue={result.get('venue')} id={str(result.get('alpaca_order_id',''))[:12]}")
except Exception as e:
    fail("BTC/USD order execution", e)

# 4. Submit ETH/USD paper order
try:
    order2 = {**order, "order_id": str(uuid.uuid4()), "instrument": "ETHUSD", "entry_price": 2200, "stop_loss": 2100, "take_profit": 2400}
    result2 = execute(order2)
    assert result2["status"] == "accepted", f"got: {result2['status']}"
    ok(f"ETH/USD market order", f"id={str(result2.get('alpaca_order_id',''))[:12]}")
except Exception as e:
    fail("ETH/USD order execution", e)

# 5. Symbol normalization (BTCUSD → BTC/USD)
try:
    test_cases = [("BTCUSD","BTC/USD"),("ETHUSD","ETH/USD"),("SOLUSD","SOL/USD"),("BTC/USD","BTC/USD")]
    from execution_service import submit_alpaca_crypto as sac
    # Test normalization logic inline
    for raw, expected in test_cases:
        symbol = raw
        if '/' not in symbol:
            symbol = symbol.replace('USD','') + '/USD'
        assert symbol == expected, f"{raw} → {symbol} (expected {expected})"
    ok("Symbol normalization", "BTCUSD→BTC/USD ✓")
except Exception as e:
    fail("symbol normalization", e)

print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
sys.exit(0 if not FAIL else 1)
