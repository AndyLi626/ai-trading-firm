#!/usr/bin/env python3
"""
write_signal.py — Write one signal to GCP market_signals table.
Usage: echo '{"source_bot":"media","symbol":"SPY","signal_type":"sentiment","value_numeric":0.15,"value_label":"Bullish","headline":"...","confidence":0.7,"session_id":""}' | python3 write_signal.py
"""
import sys, os, json
sys.path.insert(0, "/home/lishopping913/.openclaw/workspace/shared/tools")
from gcp_client import log_signal

data = json.loads(sys.stdin.read())
result = log_signal(
    source_bot=data.get("source_bot","unknown"),
    symbol=data.get("symbol",""),
    signal_type=data.get("signal_type",""),
    value_numeric=float(data.get("value_numeric",0)),
    value_label=data.get("value_label",""),
    headline=data.get("headline",""),
    source_url=data.get("source_url",""),
    confidence=float(data.get("confidence",0)),
    session_id=data.get("session_id",""),
    raw_data=data.get("raw_data",{})
)
errors = result.get("insertErrors",[])
print(json.dumps({"ok": not errors, "errors": errors}))
