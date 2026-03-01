#!/usr/bin/env python3
"""
GCP BigQuery client for the AI Trading Firm.
Used by all bots to log decisions, token usage, handoffs.
"""
import json, time, base64, urllib.request, urllib.parse, os
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

import sys; sys.path.insert(0, os.path.expanduser('~/.openclaw/secrets')); SA_PATH = os.path.expanduser('~/.openclaw/secrets/gcp-service-account.json')
PROJECT = 'ai-org-mvp-001'
DATASET = 'trading_firm'

_token_cache = {'token': None, 'expires': 0}

def get_token():
    if _token_cache['token'] and time.time() < _token_cache['expires'] - 60:
        return _token_cache['token']
    with open(SA_PATH) as f:
        sa = json.load(f)
    header = base64.urlsafe_b64encode(json.dumps({"alg":"RS256","typ":"JWT"}).encode()).rstrip(b'=').decode()
    now = int(time.time())
    claim = base64.urlsafe_b64encode(json.dumps({
        "iss": sa['client_email'],
        "scope": "https://www.googleapis.com/auth/bigquery",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now, "exp": now + 3600
    }).encode()).rstrip(b'=').decode()
    key = serialization.load_pem_private_key(sa['private_key'].encode(), password=None, backend=default_backend())
    sig = base64.urlsafe_b64encode(key.sign(f"{header}.{claim}".encode(), padding.PKCS1v15(), hashes.SHA256())).rstrip(b'=').decode()
    jwt = f"{header}.{claim}.{sig}"
    data = urllib.parse.urlencode({"grant_type":"urn:ietf:params:oauth:grant-type:jwt-bearer","assertion":jwt}).encode()
    resp = json.loads(urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data)).read())
    _token_cache['token'] = resp['access_token']
    _token_cache['expires'] = now + 3600
    return _token_cache['token']

def insert_rows(table, rows):
    """Insert rows into BigQuery table. rows = list of dicts."""
    token = get_token()
    url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/datasets/{DATASET}/tables/{table}/insertAll"
    payload = json.dumps({"rows": [{"insertId": f"{time.time_ns()}-{i}", "json": r} for i, r in enumerate(rows)]}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp

def log_decision(bot, decision_type, summary, risk_status="N/A", token_cost=0, session_id="", payload=None):
    import uuid
    return insert_rows("decisions", [{
        "event_id": str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bot": bot, "decision_type": decision_type, "summary": summary,
        "risk_status": risk_status, "token_cost": token_cost,
        "session_id": session_id, "payload": json.dumps(payload or {})
    }])

def log_token_usage(bot, model, input_tokens, output_tokens, session_id="", task_type=""):
    # Rough cost estimate for claude-sonnet-4-6
    cost = (input_tokens * 3 + output_tokens * 15) / 1_000_000
    return insert_rows("token_usage", [{
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bot": bot, "model": model,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cost_usd": round(cost, 6), "session_id": session_id, "task_type": task_type
    }])

def log_handoff(bot, session_id, last_checkpoint, context_summary, next_action, full_context=None):
    import uuid
    return insert_rows("context_handoffs", [{
        "handoff_id": str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bot": bot, "session_id": session_id,
        "last_checkpoint": last_checkpoint, "context_summary": context_summary,
        "next_action": next_action, "full_context": json.dumps(full_context or {})
    }])

if __name__ == "__main__":
    # Test
    r = log_decision("infra", "test", "GCP connection verified", "N/A", 0, "init")
    errs = r.get('insertErrors', [])
    print("GCP test:", "OK" if not errs else errs)


def log_handoff(from_bot: str, to_bot: str, task: str, payload: dict = None, session_id: str = None):
    """Log a cross-bot context handoff to GCP."""
    import time, uuid
    row = {
        "handoff_id": str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bot": from_bot,
        "session_id": session_id or "",
        "last_checkpoint": f"{from_bot}→{to_bot}: {task}",
        "context_summary": task,
        "next_action": f"{to_bot}: process {task}",
        "full_context": json.dumps({"from": from_bot, "to": to_bot, "payload": payload or {}})
    }
    return insert_rows("context_handoffs", [row])
