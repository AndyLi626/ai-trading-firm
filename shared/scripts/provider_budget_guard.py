#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import GCP client
sys.path.insert(0, '/home/lishopping913/.openclaw/workspace/shared/tools')
import urllib.request
try:
    from gcp_client import get_token
except ImportError as e:
    print(f"Error importing gcp_client: {e}")
    sys.exit(1)

def bq_query(sql):
    """Run a BigQuery query and return list of row dicts."""
    token = get_token()
    payload = json.dumps({'query': sql, 'useLegacySql': False, 'timeoutMs': 10000}).encode()
    req = urllib.request.Request(
        'https://bigquery.googleapis.com/bigquery/v2/projects/ai-org-mvp-001/queries',
        data=payload,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST')
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    schema = [f['name'] for f in d.get('schema', {}).get('fields', [])]
    rows = []
    for row in d.get('rows', []):
        rows.append({schema[i]: row['f'][i]['v'] for i in range(len(schema))})
    return rows

# Load provider caps from config file
CONFIG_PATH = '/home/lishopping913/.openclaw/workspace/shared/config/model_aliases.json'

def load_provider_caps():
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        return config.get('provider_daily_caps_usd', {
            'anthropic': 1.00,
            'qwen': 0.50,
            'google': 0.30
        })
    except Exception as e:
        print(f"Warning: Could not load config from {CONFIG_PATH}: {e}")
        return {
            'anthropic': 1.00,
            'qwen': 0.50,
            'google': 0.30
        }

PROVIDER_CAPS = load_provider_caps()


def map_model_to_provider(model_name):
    """Map model name to provider based on prefix or exact match"""
    if model_name.startswith('anthropic/') or model_name.startswith('claude-'):
        return 'anthropic'
    elif model_name.startswith('qwen/') or model_name.startswith('qwen-'):
        return 'qwen'
    elif model_name.startswith('google/') or model_name.startswith('gemini-'):
        return 'google'
    return None


def main():
    # Create output directory if it doesn't exist
    facts_dir = Path('/tmp/oc_facts')
    facts_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize result structure
    result = {
        'anthropic': {'spent': 0.0, 'cap': PROVIDER_CAPS['anthropic'], 'status': 'ok'},
        'qwen': {'spent': 0.0, 'cap': PROVIDER_CAPS['qwen'], 'status': 'ok'},
        'google': {'spent': 0.0, 'cap': PROVIDER_CAPS['google'], 'status': 'ok'},
        'hard_stop_providers': [],
        'warn_providers': [],
        'checked_at': datetime.now(timezone.utc).isoformat() + 'Z'
    }
    
    try:
        # Query BigQuery for last 24h token usage
        sql = """SELECT bot, model, cost_usd
FROM `ai-org-mvp-001.trading_firm.token_usage`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)"""
        rows = bq_query(sql)
        
        # Process results by provider
        provider_costs = {'anthropic': 0.0, 'qwen': 0.0, 'google': 0.0}
        
        for row in rows:
            model_name = row['model']
            cost = float(row['cost_usd'])
            
            provider = map_model_to_provider(model_name)
            if provider and provider in provider_costs:
                provider_costs[provider] += cost
        
        # Check provider cooldowns
        cache_path = '/home/lishopping913/.openclaw/workspace/memory/bot_cache.json'
        now = datetime.now(timezone.utc)
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)
                
                # Check cooldowns
                for provider in ['anthropic', 'qwen', 'google']:
                    cooldown_key = f'budget.{provider}_cooldown_until'
                    if 'budget' in cache_data and cooldown_key in cache_data['budget']:
                        try:
                            cooldown_until = datetime.fromisoformat(cache_data['budget'][cooldown_key].replace('Z', '+00:00'))
                            if cooldown_until > now:
                                result['hard_stop_providers'].append(provider)
                                # Don't overwrite existing status if already hard_stop
                                if result[provider]['status'] != 'hard_stop':
                                    result[provider]['status'] = 'cooldown'
                        except Exception as e:
                            print(f"Warning: Invalid cooldown format for {provider}: {e}")
            except Exception as e:
                print(f"Warning: Could not read bot_cache.json: {e}")
        
        # Calculate status for each provider
        for provider, spent in provider_costs.items():
            cap = PROVIDER_CAPS[provider]
            result[provider]['spent'] = round(spent, 2)
            
            if provider in result['hard_stop_providers']:
                # Already marked for hard stop (cooldown or other reason)
                continue
            elif spent >= cap:
                result[provider]['status'] = 'hard_stop'
                result['hard_stop_providers'].append(provider)
            elif spent >= cap * 0.9:
                result[provider]['status'] = 'warn'
                result['warn_providers'].append(provider)
            else:
                result[provider]['status'] = 'ok'
                
        # Write result to file
        with open('/tmp/oc_facts/provider_budget.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        # Check for hard stops to determine exit code
        if result['hard_stop_providers']:
            # Update bot_cache.json with hard stop flags
            cache_path = '/home/lishopping913/.openclaw/workspace/memory/bot_cache.json'
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        cache_data = json.load(f)
                    
                    # Ensure budget section exists
                    if 'budget' not in cache_data:
                        cache_data['budget'] = {}
                    
                    # Set hard stop flags
                    for provider in result['hard_stop_providers']:
                        cache_data['budget'][f'{provider}_hard_stop'] = True
                    
                    with open(cache_path, 'w') as f:
                        json.dump(cache_data, f, indent=2)
                except Exception as e:
                    print(f"Warning: Could not update bot_cache.json: {e}")
            
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        print(f"Error in provider_budget_guard: {e}")
        # Still write partial result
        with open('/tmp/oc_facts/provider_budget.json', 'w') as f:
            json.dump(result, f, indent=2)
        sys.exit(1)


if __name__ == '__main__':
    main()
