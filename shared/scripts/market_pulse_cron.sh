#!/bin/bash
# market_pulse_cron.sh — OS 레이어 직접 실행 (LLM 세션 우회)
# 이 스크립트는 openclaw cron payload에서 exec() 로 호출됨
# /tmp 의존 없이 memory/market/ 에 직접 씀
set -e
cd /home/lishopping913/.openclaw/workspace
python3 shared/scripts/market_pulse.py 2>/dev/null
# 검증
python3 -c "
import json
from datetime import datetime, timezone
d   = json.load(open('memory/market/MARKET_PULSE.json'))
now = datetime.now(timezone.utc)
age = int((now - datetime.fromisoformat(d['generated_at'])).total_seconds()//60)
print(f'MARKET_PULSE: age={age}min path=memory/market/ generated_at={d[\"generated_at\"][:19]}')
"
