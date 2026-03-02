#!/usr/bin/env python3
"""
market_pulse.py — Fetch latest bars for symbols via Alpaca IEX.
Usage: python3 market_pulse.py [SPY,QQQ,PLTR,XOM,GLD]
Output: /tmp/oc_facts/MARKET_PULSE.json + memory/autonomy/YYYY-MM-DD/MARKET_PULSE.json
"""
import sys, os, json, urllib.request, urllib.error, time, uuid
from datetime import datetime, timezone

WORKSPACE = "/home/lishopping913/.openclaw/workspace"
SECRETS = "/home/lishopping913/.openclaw/secrets"
FACTS_DIR = "/tmp/oc_facts"
DEFAULT_SYMBOLS = "SPY,QQQ,PLTR,XOM,GLD"

def load_secret(name):
    p = os.path.join(SECRETS, name)
    return open(p).read().strip() if os.path.exists(p) else ""

def fetch_bars(symbols: list, key: str, secret: str) -> dict:
    """Batch fetch latest bars from Alpaca IEX. Returns raw bars dict."""
    syms = ",".join(symbols)
    url = f"https://data.alpaca.markets/v2/stocks/bars/latest?symbols={syms}&feed=iex"
    req = urllib.request.Request(url, headers={
        "APCA-API-KEY-ID": key,
        "APCA-API-SECRET-KEY": secret,
        "Accept": "application/json"
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def build_quote(bar: dict) -> dict:
    """Convert Alpaca bar dict to quote structure."""
    close = bar.get("c")
    open_ = bar.get("o")
    pct_day = None
    if close and open_ and open_ != 0:
        pct_day = round((close - open_) / open_ * 100, 4)
    return {
        "last_price": close,
        "pct_change_5m": None,
        "pct_change_15m": None,
        "prev_close": open_,  # using open as proxy (no prev close in latest bar)
        "pct_change_day": pct_day,
        "timestamp": bar.get("t"),
        "data_source": "alpaca_iex"
    }

def main():
    symbols_raw = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SYMBOLS
    symbols = [s.strip().upper() for s in symbols_raw.split(",") if s.strip()]

    key = load_secret("alpaca_paper_key.txt")
    secret = load_secret("alpaca_paper_secret.txt")

    quotes = {}
    realtime = True
    generated_at = datetime.now(timezone.utc).isoformat()

    # Alpaca stocks API only handles non-crypto symbols
    stock_symbols = [s for s in symbols if "-USD" not in s]

    try:
        data = fetch_bars(stock_symbols, key, secret) if stock_symbols else {"bars": {}}
        bars = data.get("bars", {})
        for sym in stock_symbols:
            bar = bars.get(sym)
            if bar:
                quotes[sym] = build_quote(bar)
            else:
                quotes[sym] = {
                    "last_price": None, "pct_change_5m": None,
                    "pct_change_15m": None, "prev_close": None,
                    "pct_change_day": None, "timestamp": None,
                    "data_source": "alpaca_iex"
                }
    except Exception as e:
        realtime = False
        for sym in stock_symbols:
            quotes[sym] = {
                "last_price": None, "pct_change_5m": None,
                "pct_change_15m": None, "prev_close": None,
                "pct_change_day": None, "timestamp": None,
                "data_source": "alpaca_iex"
            }
        sys.stderr.write(f"[market_pulse] API error: {e}\n")

    # top movers sorted by abs pct_change_day
    movers = []
    for sym, q in quotes.items():
        if q.get("pct_change_day") is not None:
            movers.append({"symbol": sym, "pct_change_day": q["pct_change_day"]})
    movers.sort(key=lambda x: abs(x["pct_change_day"]), reverse=True)

    # Enrich with crypto (Hyperliquid) for -USD symbols
    crypto_syms = [s for s in symbols if "-USD" in s]
    if crypto_syms:
        cdata = fetch_crypto(crypto_syms)
        quotes.update(cdata)
        for sym, q in cdata.items():
            if q.get("last_price"):
                realtime = True
                movers.append({"symbol": sym, "pct_change_day": q.get("pct_change_day")})

    output = {
        "symbols": symbols,
        "quotes": quotes,
        "top_movers": movers,
        "realtime_data": realtime,
        "generated_at": generated_at,
        "data_source": "alpaca_iex+hyperliquid" if crypto_syms else "alpaca_iex"
    }

    os.makedirs(FACTS_DIR, exist_ok=True)
    tmp_path = os.path.join(FACTS_DIR, "MARKET_PULSE.json")
    with open(tmp_path, "w") as f:
        json.dump(output, f, indent=2)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mem_dir = os.path.join(WORKSPACE, "memory", "autonomy", today)
    os.makedirs(mem_dir, exist_ok=True)
    mem_path = os.path.join(mem_dir, "MARKET_PULSE.json")
    with open(mem_path, "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))

def fetch_crypto(symbols):
    """Fetch crypto prices via Hyperliquid allMids."""
    import urllib.request as _ur
    crypto_map = {}
    try:
        payload = json.dumps({"type": "allMids"}).encode()
        req = _ur.Request("https://api.hyperliquid.xyz/info",
                          data=payload,
                          headers={"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        for sym in symbols:
            hl_sym = sym.replace("-USD", "").replace("-USDT", "")
            if hl_sym in d:
                price = round(float(d[hl_sym]), 4)
                crypto_map[sym] = {
                    "last_price": price,
                    "pct_change_5m": None,
                    "pct_change_15m": None,
                    "prev_close": None,
                    "pct_change_day": None,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "data_source": "hyperliquid"
                }
    except Exception as e:
        pass
    return crypto_map


def enrich_with_crypto(result, requested_syms):
    crypto_syms = [s for s in requested_syms if "-USD" in s or s in ("BTC","ETH","SOL")]
    if not crypto_syms:
        return
    cdata = fetch_crypto(crypto_syms)
    result["quotes"].update(cdata)
    result["symbols"] = list(set(result.get("symbols", [])) | set(cdata.keys()))
    # Update top_movers with crypto (pct_change_day may be None)
    for sym, q in cdata.items():
        result["top_movers"].append({"symbol": sym, "pct_change_day": q.get("pct_change_day")})


if __name__ == "__main__":
    main()
