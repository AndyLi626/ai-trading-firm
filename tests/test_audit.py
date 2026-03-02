#!/usr/bin/env python3
"""
Test suite: AuditBot coverage
Smoke-checks audit-related shared components and knowledge files.
No live API calls.
"""
import os, sys, ast

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
PASS = True

def check(label, ok, msg=""):
    global PASS
    status = "PASS" if ok else "FAIL"
    detail = f" — {msg}" if msg else ""
    print(f"  [{status}] {label}{detail}")
    if not ok:
        PASS = False

print("=== AuditBot Tests ===")

# 1. INCIDENT_LOG.md exists and is readable
incident_log = os.path.join(WORKSPACE, 'shared/knowledge/INCIDENT_LOG.md')
check("INCIDENT_LOG.md exists", os.path.exists(incident_log))

# 2. AUDIT_POLICY.md exists (governance file)
audit_policy = os.path.join(WORKSPACE, 'AUDIT_POLICY.md')
check("AUDIT_POLICY.md exists", os.path.exists(audit_policy))

# 3. BOT_SKILLS_REGISTRY.md exists
skills_reg = os.path.join(WORKSPACE, 'shared/knowledge/BOT_SKILLS_REGISTRY.md')
check("BOT_SKILLS_REGISTRY.md exists", os.path.exists(skills_reg))

# 4. Shared scripts are syntactically valid Python
scripts_dir = os.path.join(WORKSPACE, 'shared/scripts')
for fname in os.listdir(scripts_dir):
    if fname.endswith('.py'):
        path = os.path.join(scripts_dir, fname)
        try:
            with open(path) as f:
                ast.parse(f.read())
            check(f"syntax OK: shared/scripts/{fname}", True)
        except SyntaxError as e:
            check(f"syntax OK: shared/scripts/{fname}", False, str(e))

# 5. Shared tools are syntactically valid Python
tools_dir = os.path.join(WORKSPACE, 'shared/tools')
for fname in os.listdir(tools_dir):
    if fname.endswith('.py'):
        path = os.path.join(tools_dir, fname)
        try:
            with open(path) as f:
                ast.parse(f.read())
            check(f"syntax OK: shared/tools/{fname}", True)
        except SyntaxError as e:
            check(f"syntax OK: shared/tools/{fname}", False, str(e))

# 6. load_secrets module importable (no secrets dir needed for import check)
try:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "load_secrets",
        os.path.join(WORKSPACE, 'shared/tools/load_secrets.py')
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    check("load_secrets module loadable", True)
    check("load_secrets has .load()", callable(getattr(mod, 'load', None)))
except Exception as e:
    check("load_secrets module loadable", False, str(e))

print()
print("PASS" if PASS else "FAIL")
sys.exit(0 if PASS else 1)
