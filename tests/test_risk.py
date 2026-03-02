#!/usr/bin/env python3
"""
Test suite: RiskBot coverage
Checks risk_limits knowledge file, governance doc, and execution engine guards.
No live API calls.
"""
import os, sys, re

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
PASS = True

def check(label, ok, msg=""):
    global PASS
    status = "PASS" if ok else "FAIL"
    detail = f" — {msg}" if msg else ""
    print(f"  [{status}] {label}{detail}")
    if not ok:
        PASS = False

print("=== RiskBot Tests ===")

# 1. shared/knowledge/risk_limits.md exists
shared_risk = os.path.join(WORKSPACE, 'shared/knowledge/risk_limits.md')
check("shared/knowledge/risk_limits.md exists", os.path.exists(shared_risk))

# 2. RISK_LIMITS.md governance doc exists
gov_risk = os.path.join(WORKSPACE, 'RISK_LIMITS.md')
check("RISK_LIMITS.md exists", os.path.exists(gov_risk))

# 3. RISK_LIMITS.md contains key sections
if os.path.exists(gov_risk):
    with open(gov_risk) as f:
        content = f.read()
    for section in ['Hard Limit', 'Soft Limit', 'Emergency', 'Override']:
        check(f"RISK_LIMITS.md has '{section}' section", section.lower() in content.lower())

# 4. Execution service exists and has basic structure
exec_svc = os.path.join(WORKSPACE, 'execution/execution_service.py')
check("execution_service.py exists", os.path.exists(exec_svc))

if os.path.exists(exec_svc):
    with open(exec_svc) as f:
        src = f.read()
    # check for some risk-related patterns
    has_risk = 'risk' in src.lower() or 'order' in src.lower() or 'size' in src.lower()
    check("execution_service references risk/order/size", has_risk)

# 5. trading_engine.py exists
engine = os.path.join(WORKSPACE, 'execution/trading_engine.py')
check("trading_engine.py exists", os.path.exists(engine))

# 6. BOT_ROLES.md defines RiskBot
bot_roles = os.path.join(WORKSPACE, 'BOT_ROLES.md')
if os.path.exists(bot_roles):
    with open(bot_roles) as f:
        content = f.read()
    check("BOT_ROLES.md mentions RiskBot", 'riskbot' in content.lower())
else:
    check("BOT_ROLES.md exists", False)

print()
print("PASS" if PASS else "FAIL")
sys.exit(0 if PASS else 1)
