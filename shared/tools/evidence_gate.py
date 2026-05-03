#!/usr/bin/env python3
"""Evidence Gate.

Claims about market prices, system status, model availability, or cost must
include a source and a fresh timestamp. Missing or stale evidence returns
UNCERTAIN so downstream agents do not overstate confidence.
"""
import json
from datetime import datetime, timezone

GATED_CATEGORIES = {"market_price", "system_status", "model_availability", "cost"}
STALE_THRESHOLD_MIN = 30


def check(claim: dict) -> dict:
    now = datetime.now(timezone.utc)
    cat = claim.get('category')
    if cat not in GATED_CATEGORIES:
        return {'result': 'PASS'}
    src = claim.get('source')
    as_of = claim.get('as_of')
    if not src or not as_of:
        return {'result': 'UNCERTAIN', 'reason': f'missing source/as_of for {cat}'}
    try:
        ts = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
        age = (now - ts).total_seconds() / 60
        if age > STALE_THRESHOLD_MIN:
            return {
                'result': 'UNCERTAIN',
                'reason': f'evidence stale ({int(age)}min > {STALE_THRESHOLD_MIN}min)',
            }
    except Exception:
        return {'result': 'UNCERTAIN', 'reason': 'invalid as_of timestamp'}
    return {'result': 'VERIFIED', 'source': src, 'as_of': as_of}


if __name__ == '__main__':
    import sys

    claim = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    print(json.dumps(check(claim)))
