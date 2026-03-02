#!/usr/bin/env python3
import json, sys, os, uuid
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace-manager/shared/tools'))
from gcp_client import insert_rows, get_token
import urllib.request
import os

LOG_PATH = os.path.expanduser('~/.openclaw/workspace/runtime_state/trading_log.jsonl')
with open(LOG_PATH) as f:
    cycles = [json.loads(l) for l in f if l.strip()]
complete = [c for c in cycles if c.get('status') == 'complete']
print(f"Found {len(complete)} complete cycles")

# Schema: order_id, timestamp, venue, instrument, status, fill_price, requested_price, filled_size, slippage, fees, error_code, error_message
rows = []
for cycle in complete:
    for order in cycle.get('orders', []):
        fill_price = order.get('price', 0)
        rows.append({
            'order_id': order.get('alpaca_id', str(uuid.uuid4())),
            'timestamp': cycle.get('timestamp', ''),
            'venue': order.get('strategy', 'paper'),
            'instrument': order.get('symbol', ''),
            'status': order.get('status', 'complete'),
            'fill_price': fill_price,
            'requested_price': fill_price,
            'filled_size': order.get('size', 0),
            'slippage': 0.0,
            'fees': 0.0,
            'error_code': '',
            'error_message': '',
        })

instruments = list(set(r['instrument'] for r in rows))
print(f"Rows to insert: {len(rows)}, instruments: {instruments}")

resp = insert_rows('execution_logs', rows)
errors = resp.get('insertErrors', [])
if errors:
    print("ERRORS:", json.dumps(errors, indent=2))
else:
    print(f"Inserted {len(rows)} rows successfully, no errors.")

# Verify
token = get_token()
query_url = "https://bigquery.googleapis.com/bigquery/v2/projects/ai-org-mvp-001/queries"
qbody = json.dumps({"query": "SELECT COUNT(*) FROM `ai-org-mvp-001.trading_firm.execution_logs`", "useLegacySql": False, "timeoutMs": 30000}).encode()
qreq = urllib.request.Request(query_url, data=qbody, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
qresp = json.loads(urllib.request.urlopen(qreq).read())
count = qresp.get('rows', [{}])[0].get('f', [{}])[0].get('v', '?')
print(f"execution_logs COUNT after insert: {count}")