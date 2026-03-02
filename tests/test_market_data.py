#!/usr/bin/env python3
"""
Test: Market data APIs — AlphaVantage, FMP, Hyperliquid
Run: python3 tests/test_market_data.py
"""
import sys, os, json, urllib.request, time
sys.path.insert(0, os.path.expanduser('~/.openclaw/secrets'))

PASS = []; FAIL = []
def ok(name, val=""): PASS.append(name); print(f"  ✅ {name}{' → '+str(val) if val else ''}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")

print("=== TEST: Market Data APIs ===\n")

# Load secrets
try:
    from load_secrets import alphavantage, fmp as fmp_api_key
    AV_KEY = alphavantage()
    FMP_KEY = fmp_api_key()
    ok("load secrets")
except Exception as e:
    fail("load secrets", e); sys.exit(1)

# 1. AlphaVantage — Global Quote
try:
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=SPY&apikey={AV_KEY}"
    with urllib.request.urlopen(url, timeout=10) as r:
        d = json.loads(r.read())
    q = d.get("Global Quote", {})
    price = q.get("05. price")
    note = d.get("Note","")
    info = d.get("Information", "")
    if note or info:
        ok("AlphaVantage quote (rate limited, key valid)")
    elif price:
        ok("AlphaVantage quote", f"SPY=${price}")
    else:
        fail("AlphaVantage quote", f"unexpected response: {list(d.keys())}")
except Exception as e:
    fail("AlphaVantage quote", e)

time.sleep(12)  # AV free tier: 5 req/min

# 2. AlphaVantage — News Sentiment
try:
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers=SPY&limit=1&apikey={AV_KEY}"
    with urllib.request.urlopen(url, timeout=10) as r:
        d = json.loads(r.read())
    feed = d.get("feed", [])
    note = d.get("Note","")
    if note:
        ok("AlphaVantage news (rate limited, key valid)")
    elif isinstance(feed, list):
        sentiment = feed[0].get("overall_sentiment_label","?") if feed else "no feed"
        ok("AlphaVantage news sentiment", sentiment)
    else:
        fail("AlphaVantage news", f"unexpected: {list(d.keys())}")
except Exception as e:
    fail("AlphaVantage news", e)

# 3. FMP — stable/quote endpoint
try:
    url = f"https://financialmodelingprep.com/stable/quote?symbol=SPY&apikey={FMP_KEY}"
    with urllib.request.urlopen(url, timeout=10) as r:
        d = json.loads(r.read())
    if isinstance(d, list) and d:
        ok("FMP stable/quote", f"SPY=${d[0].get('price','?')}")
    elif isinstance(d, dict) and d.get("Error Message"):
        fail("FMP stable/quote", d["Error Message"])
    else:
        fail("FMP stable/quote", f"unexpected: {d}")
except Exception as e:
    fail("FMP stable/quote", e)

# 4. Hyperliquid (read-only, no key needed)
try:
    url = "https://api.hyperliquid.xyz/info"
    payload = json.dumps({"type":"allMids"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=8) as r:
        d = json.loads(r.read())
    btc = d.get("BTC") or d.get("@1") or next(iter(d.values()), None)
    ok("Hyperliquid allMids", f"BTC~${float(btc or 0):,.0f}" if btc else "connected")
except Exception as e:
    fail("Hyperliquid", e)

# 5. Alpaca paper account connectivity
try:
    from load_secrets import alpaca_paper_key, alpaca_paper_secret
    req = urllib.request.Request(
        "https://paper-api.alpaca.markets/v2/account",
        headers={"APCA-API-KEY-ID": alpaca_paper_key(),
                 "APCA-API-SECRET-KEY": alpaca_paper_secret()})
    with urllib.request.urlopen(req, timeout=10) as r:
        acc = json.loads(r.read())
    ok("Alpaca paper account", f"${float(acc.get('cash',0)):,.0f} cash")
except Exception as e:
    fail("Alpaca paper account", e)

# 5. Brave Search API
try:
    import urllib.parse
    import time as _time
    brave_key = open(os.path.expanduser('~/.openclaw/secrets/brave_api_key.txt')).read().strip()
    params = urllib.parse.urlencode({"q": "SPY stock market", "count": 3, "freshness": "pd"})
    url = f"https://api.search.brave.com/res/v1/news/search?{params}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "X-Subscription-Token": brave_key
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    results = d.get("results", [])
    assert len(results) > 0, "no results"
    ok("Brave Search API", f"{len(results)} results → '{results[0].get('title','')[:50]}'")
except Exception as e:
    fail("Brave Search API", e)

# 6. market_news.py (MediaBot combined tool)
try:
    sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace-media/tools'))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "market_news",
        os.path.expanduser('~/.openclaw/workspace-media/tools/market_news.py')
    )
    mn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mn)
    # Test brave_search only (skip av_sentiment to avoid rate limit)
    results = mn.brave_search("bitcoin crypto market", count=2)
    assert results.get("results"), "no brave results"
    ok("market_news.brave_search", f"{len(results['results'])} articles")
except Exception as e:
    fail("market_news.brave_search", e)

print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
sys.exit(0 if not FAIL else 1)
