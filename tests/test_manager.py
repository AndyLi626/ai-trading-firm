#!/usr/bin/env python3
"""
Test suite: ManagerBot coverage
Checks bot orchestration config, roles doc, and bot_labels registry.
No live API calls.
"""
import os, sys, json

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
PASS = True

def check(label, ok, msg=""):
    global PASS
    status = "PASS" if ok else "FAIL"
    detail = f" — {msg}" if msg else ""
    print(f"  [{status}] {label}{detail}")
    if not ok:
        PASS = False

print("=== ManagerBot Tests ===")

# 1. BOT_ROLES.md exists
bot_roles = os.path.join(WORKSPACE, 'BOT_ROLES.md')
check("BOT_ROLES.md exists", os.path.exists(bot_roles))

# 2. BOT_ROLES.md covers all 6 bots
if os.path.exists(bot_roles):
    with open(bot_roles) as f:
        content = f.read().lower()
    for bot in ['managerbot', 'strategybot', 'mediabot', 'auditbot', 'infrabot', 'riskbot']:
        check(f"BOT_ROLES.md covers {bot}", bot in content)

# 3. bot_labels.json has expected bots
for path in [
    os.path.join(WORKSPACE, 'agents/bot_labels.json'),
    os.path.join(WORKSPACE, 'shared/bot_labels.json'),
]:
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
            bots = [str(k).lower() for k in data.keys()] if isinstance(data, dict) else []
            # just check it's non-empty
            check(f"{os.path.basename(path)} has entries", len(data) > 0, f"{len(data)} entries")
        except Exception as e:
            check(f"{os.path.basename(path)} readable", False, str(e))

# 4. STATE.md or memory dir exists (continuity)
memory_dir = os.path.join(WORKSPACE, 'memory')
state_md = os.path.join(WORKSPACE, 'STATE.md')
has_continuity = os.path.exists(memory_dir) or os.path.exists(state_md)
check("workspace has memory/continuity mechanism", has_continuity,
      f"memory/={os.path.exists(memory_dir)}, STATE.md={os.path.exists(state_md)}")

# 5. Shared knowledge README exists
readme = os.path.join(WORKSPACE, 'shared/knowledge/README.md')
check("shared/knowledge/README.md exists", os.path.exists(readme))

print()
print("PASS" if PASS else "FAIL")
sys.exit(0 if PASS else 1)
