#!/usr/bin/env python3
"""
Test suite: StrategyBot (ResearchBot) coverage
Checks market data scripts, signal writing, and strategy knowledge files.
No live API calls — mocks/skips external calls.
"""
import os, sys, ast, importlib.util

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
PASS = True

def check(label, ok, msg=""):
    global PASS
    status = "PASS" if ok else "FAIL"
    detail = f" — {msg}" if msg else ""
    print(f"  [{status}] {label}{detail}")
    if not ok:
        PASS = False

print("=== StrategyBot Tests ===")

# 1. Key shared scripts exist
for script in [
    'shared/scripts/collect_market.py',
    'shared/scripts/write_signal.py',
    'shared/scripts/update_cache.py',
]:
    path = os.path.join(WORKSPACE, script)
    check(f"{script} exists", os.path.exists(path))

# 2. All strategy scripts are syntactically valid
for script in [
    'shared/scripts/collect_market.py',
    'shared/scripts/write_signal.py',
    'shared/scripts/update_cache.py',
    'shared/scripts/collect_team.py',
]:
    path = os.path.join(WORKSPACE, script)
    if os.path.exists(path):
        try:
            with open(path) as f:
                ast.parse(f.read())
            check(f"syntax OK: {script}", True)
        except SyntaxError as e:
            check(f"syntax OK: {script}", False, str(e))

# 3. execution/trading_engine.py is syntactically valid
engine = os.path.join(WORKSPACE, 'execution/trading_engine.py')
if os.path.exists(engine):
    try:
        with open(engine) as f:
            ast.parse(f.read())
        check("trading_engine.py syntax OK", True)
    except SyntaxError as e:
        check("trading_engine.py syntax OK", False, str(e))

# 4. execution/execution_service.py is syntactically valid
svc = os.path.join(WORKSPACE, 'execution/execution_service.py')
if os.path.exists(svc):
    try:
        with open(svc) as f:
            ast.parse(f.read())
        check("execution_service.py syntax OK", True)
    except SyntaxError as e:
        check("execution_service.py syntax OK", False, str(e))

# 5. write_signal.py has a main signal-writing function/pattern
write_signal = os.path.join(WORKSPACE, 'shared/scripts/write_signal.py')
if os.path.exists(write_signal):
    with open(write_signal) as f:
        src = f.read()
    check("write_signal.py references 'signal'", 'signal' in src.lower())

# 6. LEARNING_CRON_PROMPT.md exists (strategy learning loop)
learning = os.path.join(WORKSPACE, 'shared/knowledge/LEARNING_CRON_PROMPT.md')
check("LEARNING_CRON_PROMPT.md exists", os.path.exists(learning))

print()
print("PASS" if PASS else "FAIL")
sys.exit(0 if PASS else 1)
