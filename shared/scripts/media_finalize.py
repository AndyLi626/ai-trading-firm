#!/usr/bin/env python3
"""
media_finalize.py — Reads media_facts.json, writes GCP signal, updates bot_cache.
One script, no bot ambiguity. Called after collect_media.py succeeds.
"""
import sys, os, json
from datetime import datetime, timezone

sys.path.insert(0, "/home/lishopping913/.openclaw/workspace/shared/tools")
from gcp_client import log_signal

FACTS = "/tmp/oc_facts/media_facts.json"
CACHE = "/home/lishopping913/.openclaw/workspace/memory/bot_cache.json"

facts = json.load(open(FACTS))
score = facts.get("spy_sentiment_score", 0.0) or 0.0
label = facts.get("spy_sentiment_label", "Neutral")
headline = (facts.get("top_headlines") or [{}])[0].get("title", "")
ts = facts.get("timestamp", datetime.now(timezone.utc).isoformat())

# Write signal
result = log_signal("media","SPY","sentiment",score,label,headline,"",0.65,"cron-auto")
signal_ok = not result.get("insertErrors")

# Update cache
cache = json.load(open(CACHE))
cache["media"].update({
    "last_sentiment_score": score,
    "last_sentiment_label": label,
    "last_headline": headline[:100],
    "last_brave_headlines": [h.get("title","") for h in (facts.get("top_headlines") or [])[:2]],
    "last_scan_timestamp": ts,
    "trading_alert": signal_ok and label != "Neutral",
    "alert_summary": f"{label} | {headline[:60]}" if label != "Neutral" else ""
})
cache["_updated"] = datetime.now(timezone.utc).isoformat()
json.dump(cache, open(CACHE,"w"), indent=2)

print(json.dumps({"ok": True, "signal_written": signal_ok, "label": label,
                  "score": score, "headline": headline[:80]}))
