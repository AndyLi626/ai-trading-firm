#!/usr/bin/env python3
"""
collect_market.py — Collect live crypto prices and market data.
Outputs: /tmp/oc_facts/market_facts.json + /tmp/oc_facts/market_status.json
"""
import sys, os, json, urllib.request
from datetime import datetime, timezone

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
    SECRETS = "/home/lishopping913/.openclaw/secrets"
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
