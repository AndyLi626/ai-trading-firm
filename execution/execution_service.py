#!/usr/bin/env python3
"""
ExecutionService — Deterministic execution gateway.
No LLM. No discretionary reasoning. Pure order routing.
RiskBot-approved orders only.
"""
import json, sys, os, time, uuid, urllib.request, urllib.parse
sys.path.insert(0, os.path.expanduser('~/.openclaw/secrets'))
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/shared/tools'))
from load_secrets import alpaca_paper_key, alpaca_paper_secret
from gcp_client import insert_rows

ALPACA_BASE = "https://paper-api.alpaca.markets/v2"
ALPACA_DATA = "https://data.alpaca.markets/v2"

def alpaca_headers():
    return {
        "APCA-API-KEY-ID": alpaca_paper_key(),
        "APCA-API-SECRET-KEY": alpaca_paper_secret(),
        "Content-Type": "application/json"
    }

def alpaca_request(method, path, body=None):
    url = ALPACA_BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=alpaca_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()), r.headers.get("X-Request-ID")
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        return {"error": err, "status_code": e.code}, None

def get_account():
    d, rid = alpaca_request("GET", "/account")
    return d

def validate_order(order: dict) -> tuple:
    required = ['order_id', 'venue', 'instrument', 'direction', 'order_type',
                'size_notional', 'risk_approved', 'risk_review_id']
    for field in required:
        if field not in order:
            return False, f"Missing field: {field}"
    if not order.get('risk_approved'):
        return False, "Not risk-approved"
    if order.get('size_notional', 0) > 10000:
        return False, "Exceeds max notional $10k per order"
    return True, "OK"

def submit_alpaca_order(order: dict) -> dict:
    """Submit to Alpaca paper."""
    direction = order.get('direction', '').lower()
    side = 'buy' if direction in ['long','buy'] else 'sell'
    
    # Calculate qty from notional
    notional = float(order.get('size_notional', 1000))
    
    body = {
        "symbol": order['instrument'],
        "notional": str(round(notional, 2)),
        "side": side,
        "type": order.get('order_type', 'market').lower(),
        "time_in_force": "day"
    }
    
    # Limit order needs price
    if body['type'] == 'limit' and order.get('entry_price'):
        body['limit_price'] = str(order['entry_price'])
        body.pop('notional')
        body['qty'] = "1"

    resp, request_id = alpaca_request("POST", "/orders", body)
    
    result = {
        "order_id": order['order_id'],
        "alpaca_order_id": resp.get('id'),
        "alpaca_request_id": request_id,
        "venue": "alpaca_paper",
        "instrument": order['instrument'],
        "status": resp.get('status', 'error'),
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "requested_price": order.get('entry_price'),
        "fill_price": resp.get('filled_avg_price'),
        "filled_size": resp.get('filled_qty'),
        "slippage": None,
        "fees": 0.0,
        "error_code": str(resp.get('status_code')) if 'error' in resp else None,
        "error_message": str(resp.get('error')) if 'error' in resp else None
    }
    return result

def submit_alpaca_crypto(order: dict) -> dict:
    """Submit crypto order to Alpaca paper (crypto-specific endpoint)."""
    symbol = order.get('instrument', 'BTC/USD')
    # Alpaca crypto uses symbol like BTC/USD
    if '/' not in symbol:
        symbol = symbol.replace('USD','') + '/USD'

    direction = order.get('direction', '').lower()
    side = 'buy' if direction in ['long','buy'] else 'sell'
    notional = float(order.get('size_notional', 100))

    body = {
        "symbol": symbol,
        "notional": str(notional),
        "side": side,
        "type": "market",
        "time_in_force": "gtc"
    }

    resp, _ = alpaca_request("POST", "/orders", body)

    if resp.get("error"):
        return {
            "order_id": order.get("order_id"),
            "status": "error",
            "error_message": str(resp.get("error")),
            "venue": "alpaca_paper_crypto",
            "instrument": symbol,
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

    return {
        "order_id": order.get("order_id"),
        "alpaca_order_id": resp.get("id"),
        "status": "accepted",
        "venue": "alpaca_paper_crypto",
        "instrument": symbol,
        "side": side,
        "notional": notional,
        "filled_qty": resp.get("filled_qty", "0"),
        "fill_price": float(resp.get("filled_avg_price") or 0),
        "submitted_at": resp.get("submitted_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    }


def get_options_chain(symbol: str, expiration_date: str = None, option_type: str = None) -> list:
    """Fetch options contracts for a symbol.
    option_type: 'call' or 'put'
    expiration_date: 'YYYY-MM-DD' or None for nearest
    """
    params = f"underlying_symbols={symbol}&limit=10&status=active"
    if expiration_date:
        params += f"&expiration_date={expiration_date}"
    if option_type:
        params += f"&type={option_type}"
    resp, _ = alpaca_request("GET", f"/options/contracts?{params}")
    return resp.get("option_contracts", []) if isinstance(resp, dict) else []

def submit_alpaca_option(order: dict) -> dict:
    """Submit an options order to Alpaca paper.

    order must contain:
    - instrument: underlying symbol e.g. 'SPY'
    - option_type: 'call' or 'put'
    - strike_price: float
    - expiration_date: 'YYYY-MM-DD'
    - contracts: int (number of contracts, 1 contract = 100 shares)
    - direction: 'long' (buy to open) or 'short' (sell to open)
    """
    symbol = order.get('instrument', 'SPY')
    opt_type = order.get('option_type', 'call').lower()
    strike = float(order.get('strike_price', 0))
    expiry = order.get('expiration_date', '')
    contracts = int(order.get('contracts', 1))
    direction = order.get('direction', 'long').lower()

    # Find matching contract
    chain = get_options_chain(symbol, expiry, opt_type)
    contract = None
    for c in chain:
        if abs(float(c.get('strike_price', 0)) - strike) < 0.01:
            contract = c
            break

    # If exact strike not found, use closest
    if not contract and chain:
        contract = min(chain, key=lambda c: abs(float(c.get('strike_price', 0)) - strike))

    if not contract:
        return {
            "order_id": order.get("order_id"),
            "status": "error",
            "error_message": f"No options contract found for {symbol} {opt_type} ~{strike} exp {expiry}",
            "venue": "alpaca_paper_options",
            "instrument": symbol,
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

    contract_symbol = contract.get('symbol')
    side = 'buy' if direction in ['long', 'buy'] else 'sell'

    body = {
        "symbol": contract_symbol,
        "qty": str(contracts),
        "side": side,
        "type": "market",
        "time_in_force": "day",
        "order_class": "simple"
    }

    resp, _ = alpaca_request("POST", "/orders", body)

    if resp.get("error") or resp.get("status_code"):
        return {
            "order_id": order.get("order_id"),
            "status": "error",
            "error_message": str(resp.get("error", resp)),
            "venue": "alpaca_paper_options",
            "instrument": contract_symbol,
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

    return {
        "order_id": order.get("order_id"),
        "alpaca_order_id": resp.get("id"),
        "status": "accepted",
        "venue": "alpaca_paper_options",
        "instrument": contract_symbol,
        "underlying": symbol,
        "option_type": opt_type,
        "strike_price": float(contract.get("strike_price", strike)),
        "expiration_date": contract.get("expiration_date", expiry),
        "contracts": contracts,
        "side": side,
        "fill_price": float(resp.get("filled_avg_price") or 0),
        "submitted_at": resp.get("submitted_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    }


def execute(order_json: str) -> dict:
    order = json.loads(order_json) if isinstance(order_json, str) else order_json
    valid, reason = validate_order(order)
    if not valid:
        result = {"order_id": order.get('order_id','?'), "status": "rejected",
                  "error_message": reason, "venue": order.get('venue','?'),
                  "instrument": order.get('instrument','?'),
                  "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    else:
        venue = order.get('venue', 'alpaca_paper')
        instrument = order.get('instrument', '')
        is_crypto = any(c in instrument.upper() for c in ['BTC', 'ETH', 'SOL', 'DOGE', 'AVAX'])
        is_options = order.get('option_type') is not None or venue == 'alpaca_paper_options'
        if 'alpaca' in venue and is_options:
            result = submit_alpaca_option(order)
        elif 'alpaca' in venue and is_crypto:
            result = submit_alpaca_crypto(order)
        elif 'alpaca' in venue:
            result = submit_alpaca_order(order)
        else:
            result = {"order_id": order['order_id'], "status": "venue_not_implemented",
                      "venue": venue, "instrument": order.get('instrument')}

    insert_rows("execution_logs", [result])
    return result

if __name__ == "__main__":
    if "--account" in sys.argv:
        print(json.dumps(get_account(), indent=2))
    elif len(sys.argv) > 1:
        print(json.dumps(execute(sys.argv[1]), indent=2))
    else:
        acc = get_account()
        print(f"ExecutionService READY | Alpaca Paper | Cash: ${acc.get('cash')} | BP: ${acc.get('buying_power')}")
