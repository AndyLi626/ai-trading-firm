#!/usr/bin/env python3
"""
update_cache.py — Atomically update one bot's section in bot_cache.json.
Usage: python3 update_cache.py <bot_name> '<json_patch>'
Example: python3 update_cache.py media '{"last_sentiment_score":0.15,"last_scan_timestamp":"2026-03-01T22:00:00Z"}'
"""
import sys, os, json
from datetime import datetime, timezone
import os

CACHE = os.path.expanduser('~/.openclaw/workspace/memory/bot_cache.json')

if len(sys.argv) < 3:
    print("usage: update_cache.py <bot> <json_patch>"); sys.exit(1)

bot = sys.argv[1]
patch = json.loads(sys.argv[2])

with open(CACHE) as f:
    cache = json.load(f)

if bot not in cache:
    cache[bot] = {}

cache[bot].update(patch)
cache["_updated"] = datetime.now(timezone.utc).isoformat()

with open(CACHE, "w") as f:
    json.dump(cache, f, indent=2)

print(json.dumps({"ok": True, "bot": bot, "updated_keys": list(patch.keys())}))