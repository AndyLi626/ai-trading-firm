#!/usr/bin/env python3
"""
collect_market.py — Collect live crypto prices and market data.
Outputs: /tmp/oc_facts/market_facts.json + /tmp/oc_facts/market_status.json
"""
# Token accounting: log no-op if facts unchanged
import sys, os
import os
sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
try:
    from token_meter import facts_changed, record_run
    _METER_OK = True
except Exception:
    _METER_OK = False

import json, urllib.request, uuid, time as _time
from datetime import datetime, timezone

_RUN_ID   = str(uuid.uuid4())
_BOT      = "main"
_TASK     = "collect_market"
_START    = _time.time()
_PREV_FACTS = "/tmp/oc_facts/market_facts.json"
_NEW_FACTS  = "/tmp/oc_facts/market_facts_new.json"

FACTS_DIR = "/tmp/oc_facts"
os.makedirs(FACTS_DIR, exist_ok=True)

errors = []
facts = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "prices": {},
    "sources_ok": []
}

# Hyperliquid prices
try:
    payload = json.dumps({"type": "allMids"}).encode()
    req = urllib.request.Request(
        "https://api.hyperliquid.xyz/info",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    for sym in ["BTC","ETH","SOL","AVAX","DOGE"]:
        if sym in d:
            facts["prices"][sym] = round(float(d[sym]), 2)
    facts["sources_ok"].append("hyperliquid")
except Exception as e:
    errors.append(f"hyperliquid: {e}")

# FMP for SPY price
try:
    SECRETS = os.path.expanduser('~/.openclaw/secrets')
    fmp_key = open(os.path.join(SECRETS,"fmp_api_key.txt")).read().strip()
    url = f"https://financialmodelingprep.com/stable/quote?symbol=SPY&apikey={fmp_key}"
    with urllib.request.urlopen(url, timeout=10) as r:
        d = json.loads(r.read())
    if d:
        facts["prices"]["SPY"] = round(float(d[0].get("price",0)),2)
        facts["prices"]["SPY_change_pct"] = round(float(d[0].get("changesPercentage",0)),3)
        facts["sources_ok"].append("fmp_spy")
except Exception as e:
    errors.append(f"fmp_spy: {e}")

with open(f"{FACTS_DIR}/market_facts.json", "w") as f:
    json.dump(facts, f, indent=2)

status = {"ok": len(facts["prices"]) > 0,
          "errors": errors, "sources_ok": facts["sources_ok"],
          "prices_count": len(facts["prices"]),
          "timestamp": facts["timestamp"]}
with open(f"{FACTS_DIR}/market_status.json", "w") as f:
    json.dump(status, f, indent=2)

print(json.dumps(status))

# Token accounting: detect no-op (write to _NEW_FACTS for comparison)
import shutil as _shutil
_shutil.copy(f"{FACTS_DIR}/market_facts.json", _NEW_FACTS)
if _METER_OK:
    _changed = facts_changed(_PREV_FACTS, _NEW_FACTS, key_fields=["prices"])
    if not _changed:
        record_run(_RUN_ID, _BOT, _TASK, llm_calls=0, total_input=0,
                   total_output=0, duration_sec=_time.time()-_START, status="no_op")
    else:
        record_run(_RUN_ID, _BOT, _TASK, llm_calls=0, total_input=0,
                   total_output=0, duration_sec=_time.time()-_START, status="ok")