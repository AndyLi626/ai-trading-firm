#!/bin/bash
# market_pulse_cron.sh — Direct OS-layer execution (bypasses LLM session)
# Called via exec() from openclaw cron payload
# Writes directly to memory/market/ without /tmp dependency
set -e
cd $(cd "$(dirname "$0")/../.."; pwd)
python3 shared/scripts/market_pulse.py 2>/dev/null
#
python3 -c "
import json
from datetime import datetime, timezone
d   = json.load(open('memory/market/MARKET_PULSE.json'))
now = datetime.now(timezone.utc)
age = int((now - datetime.fromisoformat(d['generated_at'])).total_seconds()//60)
print(f'MARKET_PULSE: age={age}min path=memory/market/ generated_at={d[\"generated_at\"][:19]}')
"