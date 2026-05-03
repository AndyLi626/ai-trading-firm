#!/usr/bin/env python3
"""
GCP BigQuery client for the AI Trading Firm.
Used by all bots to log decisions, token usage, handoffs.
"""
import base64
import json
import os
import time
import urllib.parse
import urllib.request
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

import sys

SECRETS_DIR = os.path.expanduser('~/.openclaw/secrets')
sys.path.insert(0, SECRETS_DIR)

SA_PATH = os.environ.get(
    "GCP_SERVICE_ACCOUNT_FILE",
    os.path.join(SECRETS_DIR, "gcp-service-account.json"),
)
PROJECT = os.environ.get("GCP_PROJECT_ID", "example-gcp-project")
DATASET = os.environ.get("BIGQUERY_DATASET", "trading_firm")

_token_cache = {'token': None, 'expires': 0}

MODEL_NORMALIZE = {
    'claude-sonnet-4-6':      'anthropic/claude-sonnet-4-6',
    'claude-haiku-4-5':       'anthropic/claude-haiku-4-5',
    'claude-opus-4-6':        'anthropic/claude-opus-4-6',
    'qwen-plus':              'qwen/qwen-plus',
    'qwen-turbo':             'qwen/qwen-turbo',
    'qwen-max':               'qwen/qwen-max',
    'gemini-2.5-flash-lite':  'google/gemini-2.5-flash-lite',
    'gemini-2.0-flash':       'google/gemini-2.0-flash',
    'gemini-2.5-pro':         'google/gemini-2.5-pro',
}

def normalize_model(name):
    return MODEL_NORMALIZE.get(name, name)


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
    # Normalize model names to include provider prefix
    model = normalize_model(model)
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


def query(sql: str) -> list:
    """Run a BigQuery SQL query and return list of row dicts."""
    token = get_token()
    url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/queries"
    payload = json.dumps({"query": sql, "useLegacySql": False, "timeoutMs": 30000}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req).read())
    schema = resp.get("schema", {}).get("fields", [])
    rows = []
    for row in resp.get("rows", []):
        values = row.get("f", [])
        rows.append({schema[i]["name"]: values[i].get("v") for i in range(len(schema))})
    return rows


def ensure_table(table_id: str, schema_file: str):
    """Create BigQuery table if it does not exist, using a JSON schema file."""
    import os as _os
    token = get_token()
    # Check existence
    check_url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/datasets/{DATASET}/tables/{table_id}"
    try:
        req = urllib.request.Request(check_url, headers={"Authorization": f"Bearer {token}"})
        urllib.request.urlopen(req).read()
        return {"status": "exists"}
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    # Create table
    with open(schema_file) as f:
        schema_fields = json.load(f)
    create_url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}/datasets/{DATASET}/tables"
    body = json.dumps({
        "tableReference": {"projectId": PROJECT, "datasetId": DATASET, "tableId": table_id},
        "schema": {"fields": schema_fields},
    }).encode()
    req = urllib.request.Request(create_url, data=body, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    resp = json.loads(urllib.request.urlopen(req).read())
    return {"status": "created", "tableId": resp.get("tableReference", {}).get("tableId")}


if __name__ == "__main__":
    # Test
    r = log_decision("infra", "test", "GCP connection verified", "N/A", 0, "init")
    errs = r.get('insertErrors', [])
    print("GCP test:", "OK" if not errs else errs)


def log_handoff(from_bot: str, to_bot: str, summary: str, payload: dict = None, session_id: str = None):
    """Log a cross-bot context handoff to GCP."""
    import uuid
    row = {
        "handoff_id": str(uuid.uuid4()),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bot": from_bot,
        "from_bot": from_bot,
        "to_bot": to_bot,
        "summary": summary,
        "session_id": session_id or "",
        "last_checkpoint": summary,
        "context_summary": summary,
        "next_action": f"to {to_bot}",
        "full_context": json.dumps(payload) if payload else "{}"
    }
    return insert_rows("context_handoffs", [row])


def log_signal(source_bot: str, symbol: str, signal_type: str,
               value_numeric: float = 0.0, value_label: str = "",
               headline: str = "", source_url: str = "",
               confidence: float = 0.0, session_id: str = "",
               raw_data: dict = None) -> dict:
    """Log a market signal to BigQuery market_signals table."""
    from datetime import datetime
    import uuid
    row = {
        "signal_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source_bot": source_bot,
        "symbol": symbol,
        "signal_type": signal_type,
        "value_numeric": value_numeric,
        "value_label": value_label,
        "headline": headline[:500] if headline else "",
        "source_url": source_url[:500] if source_url else "",
        "confidence": confidence,
        "session_id": session_id,
        "raw_data": json.dumps(raw_data or {})
    }
    return insert_rows("market_signals", [row])


def query_usage_today(bot: str = None) -> list:
    """
    Query today's token usage, handling both new (token_usage_runs) and legacy (token_usage) tables.
    Returns list of dicts: [{bot, total_tokens, date}]
    Falls back to legacy table if token_usage_runs is empty.
    Filters out test and non-runtime records.
    """
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    bot_filter = f"AND bot = '{bot}'" if bot else ""

    # Try new table
    sql_new = f"""
        SELECT bot, SUM(total_tokens) AS total_tokens, date
        FROM `{PROJECT}.{DATASET}.token_usage_runs`
        WHERE date = '{today}'
          AND (is_test IS NULL OR is_test = FALSE)
          AND (record_source IS NULL OR record_source = 'runtime')
          {bot_filter}
        GROUP BY bot, date
    """
    try:
        rows = query(sql_new)
        if rows:
            return rows
    except Exception:
        pass

    # Fallback to legacy token_usage table (handles Unix-seconds float timestamps)
    sql_legacy = f"""
        SELECT bot, SUM(total_tokens) AS total_tokens, '{today}' AS date
        FROM `{PROJECT}.{DATASET}.token_usage`
        WHERE (
            SAFE.PARSE_DATE('%Y-%m-%d', SAFE_CAST(
                FORMAT_TIMESTAMP('%Y-%m-%d', SAFE.PARSE_TIMESTAMP('%s',
                    SAFE_CAST(CAST(SAFE_CAST(timestamp AS FLOAT64) AS INT64) AS STRING)))
            AS STRING)) = '{today}'
            OR DATE(timestamp) = '{today}'
        )
        {bot_filter}
        GROUP BY bot
    """
    try:
        return query(sql_legacy)
    except Exception:
        return []
