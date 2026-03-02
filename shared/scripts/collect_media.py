#!/usr/bin/env python3
"""
collect_media.py — Collect market news, sentiment, and social signals.
Outputs: /tmp/oc_facts/media_facts.json + /tmp/oc_facts/media_status.json
No bot logic. Pure data collection.
"""
# Token accounting: log no-op if facts unchanged
import sys, os
sys.path.insert(0, "/home/lishopping913/.openclaw/workspace/shared/tools")
try:
    from token_meter import facts_changed, record_run
    _METER_OK = True
except Exception:
    _METER_OK = False

import json, urllib.request, urllib.parse, gzip, time, uuid as _uuid
from datetime import datetime, timezone

_RUN_ID    = str(_uuid.uuid4())
_BOT       = "media"
_TASK      = "collect_media"
_START     = time.time()
_PREV_FACTS = "/tmp/oc_facts/media_facts.json"
_NEW_FACTS  = "/tmp/oc_facts/media_facts_new.json"

FACTS_DIR = "/tmp/oc_facts"
os.makedirs(FACTS_DIR, exist_ok=True)

SECRETS = "/home/lishopping913/.openclaw/secrets"
SHARED  = "/home/lishopping913/.openclaw/workspace/shared/tools"
sys.path.insert(0, SHARED)

def load_secret(name):
    p = os.path.join(SECRETS, name)
    return open(p).read().strip() if os.path.exists(p) else None

def brave_news(query, count=4):
    key = load_secret("brave_api_key.txt")
    if not key: return []
    params = urllib.parse.urlencode({"q": query, "count": count, "freshness": "pd"})
    req = urllib.request.Request(
        f"https://api.search.brave.com/res/v1/news/search?{params}",
        headers={"Accept":"application/json","Accept-Encoding":"gzip","X-Subscription-Token":key}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read()
        if raw[:2] == b"\x1f\x8b": raw = gzip.decompress(raw)
    return [{"title":x.get("title",""),"url":x.get("url",""),"desc":x.get("description","")[:150]}
            for x in json.loads(raw).get("results",[])]

def brave_web(query, count=3):
    key = load_secret("brave_api_key.txt")
    if not key: return []
    params = urllib.parse.urlencode({"q": query, "count": count})
    req = urllib.request.Request(
        f"https://api.search.brave.com/res/v1/web/search?{params}",
        headers={"Accept":"application/json","Accept-Encoding":"gzip","X-Subscription-Token":key}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read()
        if raw[:2] == b"\x1f\x8b": raw = gzip.decompress(raw)
    return [{"title":x.get("title",""),"url":x.get("url",""),"desc":x.get("description","")[:150]}
            for x in json.loads(raw).get("web",{}).get("results",[])]

def av_sentiment(symbol):
    key = load_secret("alphavantage_api_key.txt")
    if not key: return None, None
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={symbol}&limit=5&apikey={key}"
    with urllib.request.urlopen(url, timeout=10) as r:
        d = json.loads(r.read())
    feed = d.get("feed", [])
    if not feed: return 0.0, "Neutral"
    scores = [float(f.get("overall_sentiment_score", 0)) for f in feed[:5]]
    avg = sum(scores) / len(scores)
    label = "Bullish" if avg > 0.15 else "Bearish" if avg < -0.15 else "Neutral"
    return round(avg, 4), label

errors = []
facts = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "spy_sentiment_score": None,
    "spy_sentiment_label": "Unknown",
    "top_headlines": [],
    "twitter_signals": [],
    "xhs_signals": [],
    "sources_ok": []
}

# 1. News headlines
try:
    headlines = brave_news("SPY S&P500 stock market today", count=4)
    facts["top_headlines"] = headlines
    facts["sources_ok"].append("brave_news")
except Exception as e:
    errors.append(f"brave_news: {e}")

# 2. Twitter signals
try:
    tweets = brave_web("site:x.com SPY bitcoin market signal analysis", count=3)
    facts["twitter_signals"] = tweets
    facts["sources_ok"].append("twitter")
except Exception as e:
    errors.append(f"twitter: {e}")

# 3. Xiaohongshu
try:
    xhs = brave_web("site:xiaohongshu.com 美股 比特币 投资", count=2)
    facts["xhs_signals"] = xhs
    facts["sources_ok"].append("xhs")
except Exception as e:
    errors.append(f"xhs: {e}")

# 4. AlphaVantage sentiment (last, rate-limit aware)
try:
    score, label = av_sentiment("SPY")
    facts["spy_sentiment_score"] = score
    facts["spy_sentiment_label"] = label
    facts["sources_ok"].append("av_sentiment")
except Exception as e:
    errors.append(f"av_sentiment: {e}")

# Write outputs
with open(f"{FACTS_DIR}/media_facts.json", "w") as f:
    json.dump(facts, f, indent=2)

status = {"ok": len(errors) == 0 or len(facts["sources_ok"]) >= 2,
          "errors": errors, "sources_ok": facts["sources_ok"],
          "timestamp": facts["timestamp"]}
with open(f"{FACTS_DIR}/media_status.json", "w") as f:
    json.dump(status, f, indent=2)

print(json.dumps(status))

# Token accounting: detect no-op
import shutil as _shutil
try:
    _shutil.copy(f"{FACTS_DIR}/media_facts.json", _NEW_FACTS)
except Exception:
    pass
if _METER_OK:
    _changed = facts_changed(_PREV_FACTS, _NEW_FACTS,
                             key_fields=["spy_sentiment_score", "spy_sentiment_label", "top_headlines"])
    _status = "ok" if _changed else "no_op"
    record_run(_RUN_ID, _BOT, _TASK, llm_calls=0, total_input=0,
               total_output=0, duration_sec=time.time()-_START, status=_status)
