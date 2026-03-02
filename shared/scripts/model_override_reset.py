#!/usr/bin/env python3
"""
model_override_reset.py — Daily UTC 00:00 reset of temp model overrides.
Restores resettable agents to canonical defaults.
Pinned agents (media, audit) are never touched.
"""
import json, os, sys, shutil
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
from gcp_client import log_decision
import os

CFG_PATH  = os.path.expanduser('~/.openclaw/openclaw.json')
CACHE_PATH = os.path.expanduser('~/.openclaw/workspace/memory/bot_cache.json')

CANONICAL_DEFAULTS = {
    'main':     'anthropic/claude-sonnet-4-6',
    'manager':  'anthropic/claude-haiku-4-5',
    'research': 'anthropic/claude-sonnet-4-6',
    'risk':     'anthropic/claude-haiku-4-5',
}
PINNED = {'media', 'audit'}  # never reset

def main():
    now = datetime.now(timezone.utc)
    shutil.copy(CFG_PATH, CFG_PATH + '.bak.reset')
    cfg = json.load(open(CFG_PATH))

    agents_reset = []
    pinned_unchanged = []

    for agent in cfg['agents']['list']:
        agent_id = agent['id']
        if agent_id in PINNED:
            pinned_unchanged.append(agent_id)
            continue
        if agent_id in CANONICAL_DEFAULTS:
            current = agent.get('model', {}).get('primary', '')
            canonical = CANONICAL_DEFAULTS[agent_id]
            if current != canonical:
                agent['model']['primary'] = canonical
                agents_reset.append({'id': agent_id, 'from': current, 'to': canonical})

    json.dump(cfg, open(CFG_PATH, 'w'), indent=2)

    # Clear provider hard stops and cooldowns from bot_cache
    if os.path.exists(CACHE_PATH):
        cache = json.load(open(CACHE_PATH))
        budget = cache.get('budget', {})
        cleared = [k for k in list(budget.keys()) if 'hard_stop' in k or 'cooldown' in k]
        for k in cleared: del budget[k]
        cache['budget'] = budget
        cache['_updated'] = now.isoformat()
        json.dump(cache, open(CACHE_PATH, 'w'), indent=2)

    # Audit log
    summary = f"Daily reset: {len(agents_reset)} overrides cleared, {len(pinned_unchanged)} pinned unchanged"
    try:
        log_decision('system', 'model_override_reset', summary, 'RESET_APPLIED', 1.0)
    except Exception as e:
        print(f"Warning: GCP audit log failed: {e}", file=sys.stderr)

    result = {
        'reset_applied': True,
        'reset_at': now.isoformat(),
        'agents_reset': agents_reset,
        'pinned_unchanged': pinned_unchanged,
    }
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()