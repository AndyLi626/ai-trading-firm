#!/usr/bin/env python3
"""
media_finalize.py — Reads media_facts.json, writes GCP signal, updates bot_cache.
One script, no bot ambiguity. Called after collect_media.py succeeds.
"""
import sys, os, json, uuid, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
from gcp_client import log_signal
import os
try:
    from token_meter import record_run, facts_changed
    _METER = True
except Exception:
    _METER = False

FACTS = "/tmp/oc_facts/media_facts.json"
CACHE = os.path.expanduser('~/.openclaw/workspace/memory/bot_cache.json')
RUN_ID = str(uuid.uuid4())
_t0 = time.time()

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

# Token accounting
if _METER:
    record_run(RUN_ID, "media", "media_finalize",
               llm_calls=0, total_input=0, total_output=0,
               duration_sec=round(time.time()-_t0, 2), status="ok")

print(json.dumps({"ok": True, "signal_written": signal_ok, "label": label,
                  "score": score, "headline": headline[:80], "run_id": RUN_ID}))