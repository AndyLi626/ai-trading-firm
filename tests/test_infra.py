#!/usr/bin/env python3
"""
Test suite: InfraBot coverage
Checks workspace structure, config files, secrets directory, and key scripts.
No live API calls.
"""
import os, sys, json, ast

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
SECRETS_DIR = os.path.expanduser('~/.openclaw/secrets')
PASS = True

def check(label, ok, msg=""):
    global PASS
    status = "PASS" if ok else "FAIL"
    detail = f" — {msg}" if msg else ""
    print(f"  [{status}] {label}{detail}")
    if not ok:
        PASS = False

print("=== InfraBot Tests ===")

# 1. Core workspace files exist
for fname in ['SOUL.md', 'AGENTS.md', 'IDENTITY.md', 'USER.md', 'TOOLS.md']:
    path = os.path.join(WORKSPACE, fname)
    check(f"{fname} exists", os.path.exists(path))

# 2. Governance docs exist
for fname in ['AUDIT_POLICY.md', 'RISK_LIMITS.md', 'BOT_ROLES.md']:
    path = os.path.join(WORKSPACE, fname)
    check(f"{fname} exists", os.path.exists(path))

# 3. bot_labels.json is valid JSON (check shared location)
shared_labels = os.path.join(WORKSPACE, 'shared/bot_labels.json')
check("shared/bot_labels.json exists", os.path.exists(shared_labels))
if os.path.exists(shared_labels):
    try:
        with open(shared_labels) as f:
            data = json.load(f)
        check("shared/bot_labels.json is valid JSON", True)
    except json.JSONDecodeError as e:
        check("shared/bot_labels.json is valid JSON", False, str(e))

# 5. Secrets directory exists and is not world-readable
check("secrets dir exists", os.path.exists(SECRETS_DIR))
if os.path.exists(SECRETS_DIR):
    mode = oct(os.stat(SECRETS_DIR).st_mode)[-3:]
    world_readable = int(mode[-1]) >= 4
    check("secrets dir not world-readable", not world_readable, f"mode={mode}")

# 6. Execution directory has key files
for fname in ['execution_service.py', 'trading_engine.py']:
    path = os.path.join(WORKSPACE, 'execution', fname)
    check(f"execution/{fname} exists", os.path.exists(path))

# 7. Tests directory is complete
tests_dir = os.path.join(WORKSPACE, 'tests')
test_files = [f for f in os.listdir(tests_dir) if f.startswith('test_') and f.endswith('.py')]
check("tests/ has ≥10 test files", len(test_files) >= 10, f"found {len(test_files)}")
check("run_all.py exists", os.path.exists(os.path.join(tests_dir, 'run_all.py')))

# 8. Shared knowledge directory exists
knowledge_dir = os.path.join(WORKSPACE, 'shared/knowledge')
check("shared/knowledge/ exists", os.path.exists(knowledge_dir))

print()
print("PASS" if PASS else "FAIL")
sys.exit(0 if PASS else 1)
