#!/usr/bin/env python3
"""
write_signal.py — Write one signal to GCP market_signals table.
Usage: echo '{"source_bot":"media",...}' | python3 write_signal.py
"""
import sys, os, json, uuid, time
sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
from gcp_client import log_signal
import os
try:
    from token_meter import record_run
    _METER = True
except Exception:
    _METER = False

RUN_ID = str(uuid.uuid4())
_t0 = time.time()

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
ok = not errors

if _METER:
    record_run(RUN_ID, data.get("source_bot","unknown"), "write_signal",
               llm_calls=0, total_input=0, total_output=0,
               duration_sec=round(time.time()-_t0,2), status="ok" if ok else "error")

print(json.dumps({"ok": ok, "errors": errors, "run_id": RUN_ID}))