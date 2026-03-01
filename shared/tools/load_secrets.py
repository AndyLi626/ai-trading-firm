#!/usr/bin/env python3
"""
Secrets loader — reads all tokens from ~/.openclaw/secrets/
Never hardcode tokens. Always load from here.
"""
import os

SECRETS_DIR = os.path.expanduser('~/.openclaw/secrets')

def load(name: str) -> str:
    """Load a secret by filename (without extension)."""
    for ext in ['.txt', '.json']:
        path = os.path.join(SECRETS_DIR, name + ext)
        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
    raise FileNotFoundError(f"Secret not found: {name}")

# Convenience accessors
def anthropic():   return load('anthropic_api_key')
def openai():      return load('openai_api_key')
def gemini():      return load('gemini_api_key')
def qwen():        return load('qwen_api_key')
def alphavantage(): return load('alphavantage_api_key')
def fmp():         return load('fmp_api_key')
def odds():        return load('odds_api_key')
def coinbase():    return load('coinbase_api')
def gcp_sa():      return load('gcp-service-account')
def telegram_infra(): return load('telegram_infra_token')
def telegram_manager(): return load('telegram_manager_token')

if __name__ == '__main__':
    print("Secrets available:", [f.replace('.txt','').replace('.json','') 
          for f in os.listdir(SECRETS_DIR) if not f.startswith('.')])

import json as _json

def api_registry() -> dict:
    """Load the full API registry."""
    with open(os.path.join(SECRETS_DIR, 'api_registry.json')) as f:
        return _json.load(f)

def get_api(category: str, name: str) -> dict:
    """Get a specific API config from registry."""
    reg = api_registry()
    return reg.get(category, {}).get(name, {})

def alpaca_paper_key(): return load('alpaca_paper_key')
def alpaca_paper_secret(): return load('alpaca_paper_secret')
def brave_api_key(): return load('brave_api_key')
def alphavantage_api_key(): return load('alphavantage_api_key')
