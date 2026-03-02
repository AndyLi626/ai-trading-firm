#!/usr/bin/env python3
"""Model probe — minimal test call to each provider. Max 5 tokens."""
import json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone
import os

SECRETS = os.path.expanduser('~/.openclaw/secrets')
OUT = os.path.expanduser('~/.openclaw/workspace/memory/model_probe_results.json')

def probe_anthropic():
    key_file = f'{SECRETS}/anthropic_api_key.txt'
    if not os.path.exists(key_file): return {'provider':'anthropic','model':'claude-haiku-4-5','status':'fail','error':'no key file','latency_ms':0,'tokens_used':0}
    key = open(key_file).read().strip()
    t0 = time.time()
    try:
        req = urllib.request.Request('https://api.anthropic.com/v1/messages',
            data=json.dumps({'model':'claude-haiku-4-5','max_tokens':5,'messages':[{'role':'user','content':'hi'}]}).encode(),
            headers={'x-api-key':key,'anthropic-version':'2023-06-01','content-type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=10) as r:
            d=json.loads(r.read())
        return {'provider':'anthropic','model':'claude-haiku-4-5','status':'ok','latency_ms':int((time.time()-t0)*1000),'tokens_used':d.get('usage',{}).get('output_tokens',0),'error':None}
    except urllib.error.HTTPError as e:
        body=e.read().decode()[:200]
        return {'provider':'anthropic','model':'claude-haiku-4-5','status':'fail','latency_ms':int((time.time()-t0)*1000),'tokens_used':0,'error':f'HTTP {e.code}: {body}'}
    except Exception as e:
        return {'provider':'anthropic','model':'claude-haiku-4-5','status':'fail','latency_ms':int((time.time()-t0)*1000),'tokens_used':0,'error':str(e)}

def probe_qwen():
    key_file = f'{SECRETS}/qwen_api_key.txt'
    if not os.path.exists(key_file): return {'provider':'qwen','model':'qwen-plus','status':'fail','error':'no key file','latency_ms':0,'tokens_used':0}
    key = open(key_file).read().strip()
    t0 = time.time()
    try:
        req = urllib.request.Request('https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions',
            data=json.dumps({'model':'qwen-plus','max_tokens':5,'messages':[{'role':'user','content':'hi'}]}).encode(),
            headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=10) as r:
            d=json.loads(r.read())
        tok=d.get('usage',{}).get('completion_tokens',0)
        return {'provider':'qwen','model':'qwen-plus','status':'ok','latency_ms':int((time.time()-t0)*1000),'tokens_used':tok,'error':None}
    except urllib.error.HTTPError as e:
        return {'provider':'qwen','model':'qwen-plus','status':'fail','latency_ms':int((time.time()-t0)*1000),'tokens_used':0,'error':f'HTTP {e.code}'}
    except Exception as e:
        return {'provider':'qwen','model':'qwen-plus','status':'fail','latency_ms':int((time.time()-t0)*1000),'tokens_used':0,'error':str(e)}

def probe_google():
    key_file = f'{SECRETS}/gemini_api_key.txt'
    if not os.path.exists(key_file): return {'provider':'google','model':'gemini-2.0-flash-lite','status':'fail','error':'no key file','latency_ms':0,'tokens_used':0}
    key = open(key_file).read().strip()
    t0 = time.time()
    try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={key}'
        req = urllib.request.Request(url,
            data=json.dumps({'contents':[{'parts':[{'text':'hi'}]}],'generationConfig':{'maxOutputTokens':5}}).encode(),
            headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=10) as r:
            d=json.loads(r.read())
        tok=d.get('usageMetadata',{}).get('candidatesTokenCount',0)
        return {'provider':'google','model':'gemini-2.0-flash-lite','status':'ok','latency_ms':int((time.time()-t0)*1000),'tokens_used':tok,'error':None}
    except urllib.error.HTTPError as e:
        return {'provider':'google','model':'gemini-2.0-flash-lite','status':'fail','latency_ms':int((time.time()-t0)*1000),'tokens_used':0,'error':f'HTTP {e.code}'}
    except Exception as e:
        return {'provider':'google','model':'gemini-2.0-flash-lite','status':'fail','latency_ms':int((time.time()-t0)*1000),'tokens_used':0,'error':str(e)}

results = [probe_anthropic(), probe_qwen(), probe_google()]
out = {'probed_at': datetime.now(timezone.utc).isoformat(), 'results': results}
json.dump(out, open(OUT,'w'), indent=2)
print(json.dumps(out, indent=2))