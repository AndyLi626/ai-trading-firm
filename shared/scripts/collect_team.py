#!/usr/bin/env python3
"""
collect_team.py — Query GCP for real team state. No hallucination allowed.
Outputs: /tmp/oc_facts/team_facts.json + /tmp/oc_facts/team_status.json
"""
import sys, os, json, urllib.request
from datetime import datetime, timezone

FACTS_DIR = "/tmp/oc_facts"
os.makedirs(FACTS_DIR, exist_ok=True)
sys.path.insert(0, "/home/lishopping913/.openclaw/workspace/shared/tools")

from gcp_client import get_token

def bq(sql):
    token = get_token()
    req = urllib.request.Request(
        "https://bigquery.googleapis.com/bigquery/v2/projects/ai-org-mvp-001/queries",
        data=json.dumps({"query":sql,"useLegacySql":False,"timeoutMs":8000}).encode(),
        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=12) as r:
        d = json.loads(r.read())
    return [[f["v"] for f in row["f"]] for row in d.get("rows",[])]

errors = []
facts = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "decisions_today": 0,
    "executions_total": 0,
    "risk_approvals": 0,
    "recent_signals": [],
    "last_execution": None,
    "bot_costs_usd": {}
}

try:
    r = bq("SELECT COUNT(*) FROM `ai-org-mvp-001.trading_firm.decisions` WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)")
    facts["decisions_today"] = int(r[0][0]) if r else 0
except Exception as e: errors.append(f"decisions: {e}")

try:
    r = bq("SELECT COUNT(*) FROM `ai-org-mvp-001.trading_firm.execution_logs` WHERE status='accepted'")
    facts["executions_total"] = int(r[0][0]) if r else 0
except Exception as e: errors.append(f"executions: {e}")

try:
    r = bq("SELECT COUNT(*) FROM `ai-org-mvp-001.trading_firm.risk_reviews` WHERE decision='Approve'")
    facts["risk_approvals"] = int(r[0][0]) if r else 0
except Exception as e: errors.append(f"risk: {e}")

try:
    rows = bq("SELECT source_bot,symbol,signal_type,value_label,headline FROM `ai-org-mvp-001.trading_firm.market_signals` WHERE source_bot != 'test' ORDER BY timestamp DESC LIMIT 5")
    facts["recent_signals"] = [{"bot":r[0],"symbol":r[1],"type":r[2],"label":r[3],"headline":(r[4] or "")[:80]} for r in rows]
except Exception as e: errors.append(f"signals: {e}")

try:
    rows = bq("SELECT bot, SUM(cost_usd) FROM `ai-org-mvp-001.trading_firm.token_usage` WHERE timestamp > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR) GROUP BY bot")
    facts["bot_costs_usd"] = {r[0]: round(float(r[1] or 0),4) for r in rows}
except Exception as e: errors.append(f"costs: {e}")

with open(f"{FACTS_DIR}/team_facts.json", "w") as f:
    json.dump(facts, f, indent=2)

status = {"ok": len(errors) < 3, "errors": errors, "timestamp": facts["timestamp"]}
with open(f"{FACTS_DIR}/team_status.json", "w") as f:
    json.dump(status, f, indent=2)

print(json.dumps(status))
