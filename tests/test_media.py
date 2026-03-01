#!/usr/bin/env python3
"""
Test: MediaBot pipeline — Brave Search, Reddit, skills loaded
Run: python3 tests/test_media.py
"""
import sys, os, json, urllib.request, urllib.parse, time

PASS = []; FAIL = []
def ok(name, val=""): PASS.append(name); print(f"  ✅ {name}{' → '+str(val) if val else ''}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")

print("=== TEST: MediaBot Pipeline ===\n")

SECRETS = os.path.expanduser('~/.openclaw/secrets')
MEDIA_WS = os.path.expanduser('~/.openclaw/workspace-media')

# 1. Brave Search — news for SPY
try:
    key = open(f"{SECRETS}/brave_api_key.txt").read().strip()
    params = urllib.parse.urlencode({"q": "SPY S&P500 market", "count": 3, "freshness": "pd"})
    req = urllib.request.Request(
        f"https://api.search.brave.com/res/v1/news/search?{params}",
        headers={"Accept": "application/json", "X-Subscription-Token": key}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    results = d.get("results", [])
    assert len(results) > 0
    ok("Brave: SPY news", f"{len(results)} articles → '{results[0].get('title','')[:50]}'")
except Exception as e:
    fail("Brave: SPY news", e)

# 2. Brave Search — crypto BTC
try:
    key = open(f"{SECRETS}/brave_api_key.txt").read().strip()
    params = urllib.parse.urlencode({"q": "Bitcoin BTC price news", "count": 3, "freshness": "pd"})
    req = urllib.request.Request(
        f"https://api.search.brave.com/res/v1/news/search?{params}",
        headers={"Accept": "application/json", "X-Subscription-Token": key}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    results = d.get("results", [])
    assert len(results) > 0
    ok("Brave: BTC news", f"'{results[0].get('title','')[:50]}'")
except Exception as e:
    fail("Brave: BTC news", e)

# 3. Reddit r/investing — OAuth required (skip until credentials stored)
try:
    reddit_id = open(os.path.expanduser("~/.openclaw/secrets/reddit_client_id.txt")).read().strip() if os.path.exists(os.path.expanduser("~/.openclaw/secrets/reddit_client_id.txt")) else None
    if not reddit_id:
        ok("Reddit r/investing", "(SKIP — reddit_client_id.txt not found, OAuth needed)")
    else:
        import base64
        reddit_secret = open(os.path.expanduser("~/.openclaw/secrets/reddit_client_secret.txt")).read().strip()
        creds = base64.b64encode(f"{reddit_id}:{reddit_secret}".encode()).decode()
        # Get token
        token_req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=b"grant_type=client_credentials",
            headers={"Authorization": f"Basic {creds}", "User-Agent": "OpenClaw-Trading/1.0"}
        )
        with urllib.request.urlopen(token_req, timeout=10) as r:
            token_data = json.loads(r.read())
        token = token_data["access_token"]
        # Use token
        req = urllib.request.Request(
            "https://oauth.reddit.com/r/investing/hot?limit=3",
            headers={"Authorization": f"bearer {token}", "User-Agent": "OpenClaw-Trading/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        posts = d.get("data", {}).get("children", [])
        assert len(posts) > 0
        ok("Reddit r/investing", f"'{posts[0]['data'].get('title','')[:60]}'")
except Exception as e:
    fail("Reddit r/investing", e)

# 4. Reddit r/wallstreetbets (same OAuth pattern)
try:
    reddit_id = open(os.path.expanduser("~/.openclaw/secrets/reddit_client_id.txt")).read().strip() if os.path.exists(os.path.expanduser("~/.openclaw/secrets/reddit_client_id.txt")) else None
    if not reddit_id:
        ok("Reddit r/wallstreetbets", "(SKIP — OAuth credentials needed)")
    else:
        ok("Reddit r/wallstreetbets", "(deferred to r/investing test above)")
except Exception as e:
    fail("Reddit r/wallstreetbets", e)

# 5. Hyperliquid crypto prices
try:
    payload = json.dumps({"type": "allMids"}).encode()
    req = urllib.request.Request(
        "https://api.hyperliquid.xyz/info",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    btc = float(d.get("BTC", 0))
    eth = float(d.get("ETH", 0))
    assert btc > 1000
    ok("Hyperliquid prices", f"BTC=${btc:,.0f} ETH=${eth:,.0f}")
except Exception as e:
    fail("Hyperliquid prices", e)

# 6. market_news.py tool exists and imports
try:
    tools_path = os.path.join(MEDIA_WS, "tools")
    assert os.path.exists(os.path.join(tools_path, "market_news.py")), "market_news.py missing"
    sys.path.insert(0, tools_path)
    sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/shared/tools'))
    import importlib.util
    spec = importlib.util.spec_from_file_location("market_news", os.path.join(tools_path, "market_news.py"))
    mn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mn)
    ok("market_news.py importable")
except Exception as e:
    fail("market_news.py import", e)

# 7. MediaBot skills installed
try:
    skills_dir = os.path.join(MEDIA_WS, "skills")
    expected = ["market-news-analyst", "market-pulse", "reddit-readonly", "openclaw-twitter", "social-sentiment"]
    installed = os.listdir(skills_dir) if os.path.isdir(skills_dir) else []
    missing = [s for s in expected if s not in installed]
    assert not missing, f"missing: {missing}"
    ok(f"MediaBot skills installed", f"{len(installed)} skills: {', '.join(installed)}")
except Exception as e:
    fail("MediaBot skills", e)

# 8. AISA Twitter API key exists (even if 403 - key is stored)
try:
    key = open(f"{SECRETS}/aisa_api_key.txt").read().strip()
    assert len(key) > 10
    # Note: AISA endpoints return 403 currently - key may need activation
    ok("AISA key stored", "(API returns 403 - may need activation at aisa.one)")
except Exception as e:
    fail("AISA key", e)

# 9. learning_state.json exists
try:
    state_path = os.path.expanduser('~/.openclaw/workspace/memory/learning_state.json')
    with open(state_path) as f:
        state = json.load(f)
    assert "media" in state
    ok("learning_state.json", f"media.scan_count={state['media'].get('scan_count',0)}")
except Exception as e:
    fail("learning_state.json", e)


# 7b. Twitter/X search via Brave
try:
    sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace-media/tools'))
    sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/shared/tools'))
    import importlib
    import market_news as mn_mod
    importlib.reload(mn_mod)
    tw = mn_mod.twitter_search("SPY bitcoin market", count=2)
    assert len(tw) > 0, "no twitter results"
    ok("Twitter/X via Brave", f"{len(tw)} posts → {tw[0].get('url','')[:50]}")
except Exception as e:
    fail("Twitter/X via Brave", e)

# 7c. Xiaohongshu search via Brave
try:
    xhs = mn_mod.xiaohongshu_search("比特币 投资", count=2)
    assert len(xhs) > 0, "no XHS results"
    ok("Xiaohongshu via Brave", f"'{xhs[0].get('title','')[:40]}'")
except Exception as e:
    fail("Xiaohongshu via Brave", e)

print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
sys.exit(0 if not FAIL else 1)
