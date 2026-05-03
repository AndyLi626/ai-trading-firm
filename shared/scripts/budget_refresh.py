#!/usr/bin/env python3
import os
"""
budget_refresh.py — /budget refresh handler (Boss-only, 0 LLM, deterministic)
- Re-reads provider caps from model_aliases.json
- Probes Anthropic availability (minimal call)
- Recalculates budget_mode per provider
- Clears resolved cooldowns/stops from bot_cache
- Writes memory/budget_refresh_<ts>.json + GCP audit event
- Does NOT reset spent tokens to 0
"""
import json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
from gcp_client import get_token as gcp_token, log_decision

SECRETS    = os.path.expanduser('~/.openclaw/secrets')
CACHE_PATH = os.path.expanduser('~/.openclaw/workspace/memory/bot_cache.json')
ALIASES    = os.path.expanduser('~/.openclaw/workspace/shared/config/model_aliases.json')
OUT_DIR    = os.path.expanduser('~/.openclaw/workspace/memory')

def load_caps():
    cfg = json.load(open(ALIASES))
    return cfg['provider_daily_caps_usd'], cfg.get('provider_cooldown_minutes', {})

def get_today_spend():
    """Query GCP token_usage for today's spend by provider."""
    PROVIDER_MAP = {
        'anthropic/': 'anthropic', 'claude-': 'anthropic',
        'qwen/': 'qwen', 'qwen-': 'qwen',
        'google/': 'google', 'gemini-': 'google',
    }
    def to_provider(m):
        for prefix, p in PROVIDER_MAP.items():
            if m.startswith(prefix): return p
        return None

    q = """SELECT model, SUM(cost_usd) cost
FROM `example-gcp-project.trading_firm.token_usage`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY 1"""
    token = gcp_token()
    req = urllib.request.Request(
        'https://bigquery.googleapis.com/bigquery/v2/projects/example-gcp-project/queries',
        data=json.dumps({'query': q, 'useLegacySql': False, 'timeoutMs': 10000}).encode(),
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST')
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())

    spend = {'anthropic': 0.0, 'qwen': 0.0, 'google': 0.0}
    for row in d.get('rows', []):
        model = row['f'][0]['v']
        cost = float(row['f'][1]['v'] or 0)
        p = to_provider(model)
        if p: spend[p] = round(spend[p] + cost, 4)
    return spend

def probe_anthropic():
    """Minimal probe to check if Anthropic key works. Max 5 tokens."""
    key_file = f'{SECRETS}/anthropic_api_key.txt'
    if not os.path.exists(key_file): return 'key_missing'
    key = open(key_file).read().strip()
    try:
        req = urllib.request.Request('https://api.anthropic.com/v1/messages',
            data=json.dumps({'model':'claude-haiku-4-5','max_tokens':5,
                             'messages':[{'role':'user','content':'ping'}]}).encode(),
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01',
                     'content-type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=8) as r:
            code = r.status
        return 'ok' if code == 200 else f'http_{code}'
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:100]
        if 'credit' in body.lower() or 'balance' in body.lower():
            return 'credit_exhausted'
        return f'http_{e.code}'
    except Exception as e:
        return f'error: {e}'

def compute_mode(spent, cap):
    ratio = spent / cap if cap else 0
    if ratio >= 1.0: return 'stop'
    if ratio >= 0.90: return 'degrade'
    if ratio >= 0.75: return 'warn'
    return 'ok'

def main():
    now = datetime.now(timezone.utc)
    ts  = now.strftime('%Y%m%d_%H%M%S')

    caps, cooldown_mins = load_caps()
    spend  = get_today_spend()
    probe  = probe_anthropic()

    # Compute modes
    providers = {}
    for p in ['anthropic', 'qwen', 'google']:
        spent = spend.get(p, 0.0)
        cap   = caps.get(p, 999)
        mode  = compute_mode(spent, cap)
        # Override if probe says anthropic is down despite budget headroom
        if p == 'anthropic' and probe == 'credit_exhausted':
            mode = 'stop'
        if p == 'anthropic' and probe == 'ok' and mode == 'stop':
            mode = 'ok'  # credit restored
        providers[p] = {'spent': spent, 'cap': cap, 'mode': mode, 'probe': probe if p == 'anthropic' else 'n/a'}

    # Clear resolved stops from bot_cache
    cleared = []
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH))
        budget_section = cache.get('budget', {})
        for p, info in providers.items():
            hard_stop_key = f'{p}_hard_stop'
            cooldown_key  = f'{p}_cooldown_until'
            if info['mode'] in ('ok', 'warn'):
                if hard_stop_key in budget_section:
                    del budget_section[hard_stop_key]
                    cleared.append(hard_stop_key)
                if cooldown_key in budget_section:
                    del budget_section[cooldown_key]
                    cleared.append(cooldown_key)
        # Write global budget_mode
        budget_section['global_mode'] = max(
            [p['mode'] for p in providers.values()],
            key=lambda m: ['ok','warn','degrade','stop'].index(m))
        budget_section['last_refresh'] = now.isoformat()
        cache['budget'] = budget_section
        cache['_updated'] = now.isoformat()
        json.dump(cache, open(CACHE_PATH, 'w'), indent=2)

    result = {
        'refreshed_at': now.isoformat(),
        'providers': providers,
        'global_mode': max([p['mode'] for p in providers.values()],
                           key=lambda m: ['ok','warn','degrade','stop'].index(m)),
        'anthropic_probe': probe,
        'cleared_stops': cleared,
        'spend_today': spend,
    }

    out_path = f'{OUT_DIR}/budget_refresh_{ts}.json'
    json.dump(result, open(out_path, 'w'), indent=2)
    # Also write latest symlink
    json.dump(result, open(f'{OUT_DIR}/budget_refresh_latest.json', 'w'), indent=2)

    try:
        modes_str = ', '.join(f'{k}={v["mode"]}' for k, v in providers.items())
        log_decision('system', 'budget_refresh',
            f'Provider modes: {modes_str}. Anthropic probe: {probe}. Cleared: {cleared}.',
            result['global_mode'].upper(), 1.0)
    except Exception as e:
        print(f'Warning: GCP audit log: {e}', file=sys.stderr)

    print(json.dumps(result, indent=2))
    return 0

if __name__ == '__main__':
    sys.exit(main())