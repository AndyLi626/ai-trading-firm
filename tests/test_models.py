#!/usr/bin/env python3
"""
Test: All AI model endpoints — Anthropic (Haiku+Sonnet), Qwen, Gemini Flash Lite
Run: python3 tests/test_models.py
"""
import sys, os, json, urllib.request, time
sys.path.insert(0, os.path.expanduser('~/.openclaw/secrets'))

PASS = []; FAIL = []
def ok(name, val=""): PASS.append(name); print(f"  ✅ {name}{' → '+str(val) if val else ''}")
def fail(name, err): FAIL.append(name); print(f"  ❌ {name}: {err}")

print("=== TEST: AI Model Endpoints ===\n")

SECRETS = '/home/lishopping913/.openclaw/secrets'

def anthropic_call(model):
    key = open(f'{SECRETS}/anthropic_api_key.txt').read().strip()
    payload = json.dumps({"model":model,"max_tokens":10,
        "messages":[{"role":"user","content":"reply: ok"}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload,
        headers={"x-api-key":key,"anthropic-version":"2023-06-01","content-type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    return d["model"], d["content"][0]["text"].strip()[:20]

def qwen_call(model):
    key = open(f'{SECRETS}/qwen_api_key.txt').read().strip()
    payload = json.dumps({"model":model,"max_tokens":10,
        "messages":[{"role":"user","content":"reply: ok"}]}).encode()
    req = urllib.request.Request(
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions",
        data=payload,
        headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    return d["model"], d["choices"][0]["message"]["content"].strip()[:20]

def gemini_call(model):
    key = open(f'{SECRETS}/gemini_api_key.txt').read().strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = json.dumps({"contents":[{"parts":[{"text":"reply: ok"}]}],
        "generationConfig":{"maxOutputTokens":10}}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    text = d["candidates"][0]["content"]["parts"][0]["text"].strip()[:20]
    return model, text

# 1. claude-haiku-4-5 (ManagerBot + RiskBot)
try:
    model, reply = anthropic_call("claude-haiku-4-5")
    ok(f"claude-haiku-4-5 [manager/risk]", f"{model} → '{reply}'")
except Exception as e:
    fail("claude-haiku-4-5", e)

# 2. claude-sonnet-4-6 (StrategyBot + InfraBot)
try:
    model, reply = anthropic_call("claude-sonnet-4-6")
    ok(f"claude-sonnet-4-6 [research/main]", f"{model} → '{reply}'")
except Exception as e:
    fail("claude-sonnet-4-6", e)

# 3. qwen-plus (MediaBot)
try:
    model, reply = qwen_call("qwen-plus")
    ok(f"qwen-plus [media]", f"{model} → '{reply}'")
except Exception as e:
    fail("qwen-plus", e)

# 4. gemini-2.0-flash-lite (AuditBot)
# generateContent is IP-restricted; validate key + config only via models list API
try:
    import urllib.request as ur2
    key = open(f"{SECRETS}/gemini_api_key.txt").read().strip()
    assert len(key) > 10, "gemini key empty"
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}&pageSize=1"
    with ur2.urlopen(url, timeout=8) as r2:
        d2 = json.loads(r2.read())
    assert d2.get("models"), "no models returned"
    with open("/home/lishopping913/.openclaw/openclaw.json") as cf:
        cc = json.load(cf)
    ids = [m["id"] for m in cc["models"]["providers"]["google"]["models"]]
    assert "gemini-2.0-flash-lite" in ids, f"not in config: {ids}"
    ok("gemini-2.0-flash-lite [audit] key valid + config registered")
except Exception as e:
    fail("gemini-2.0-flash-lite", e)

# 5. Verify openclaw.json model assignments
try:
    with open('/home/lishopping913/.openclaw/openclaw.json') as f:
        config = json.load(f)
    expected = {
        "main":     "anthropic/claude-sonnet-4-6",
        "manager":  "anthropic/claude-haiku-4-5",
        "research": "anthropic/claude-sonnet-4-6",
        "media":    "qwen/qwen-plus",
        "risk":     "anthropic/claude-haiku-4-5",
        "audit":    "google/gemini-2.0-flash-lite",
    }
    agents = {a['id']: a.get('model',{}).get('primary','') for a in config['agents']['list']}
    mismatches = [(k, expected[k], agents.get(k,'?')) for k in expected if agents.get(k) != expected[k]]
    if mismatches:
        for agent, exp, got in mismatches:
            fail(f"config:{agent}", f"expected {exp}, got {got}")
    else:
        ok("openclaw.json model assignments correct")
except Exception as e:
    fail("openclaw.json check", e)

print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
sys.exit(0 if not FAIL else 1)
