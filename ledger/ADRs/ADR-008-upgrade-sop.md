# ADR-008 — OpenClaw Upgrade SOP

****: Approved
**Date**: 2026-03-02  
**Background**: 2026-03-02 CLI(2026.2.26) vs Gateway(2026.2.26) vs user-level(2026.3.1) .
 " " SOP .

---

## Phase 1 — Upgrade Proposal (Proposal)

InfraBot Proposal : `memory/proposals/upgrade_<ver>_<date>.md`

 entries:
```
target_version: 2026.X.Y
current_version: 2026.A.B
change_scope: CLI / gateway / cron runner / skills
risk:
 - config format (package.json changelog )
 - plugins/skills
 - PATH (system vs user-level)
rollback:
 - Backup service file : ~/.config/systemd/user/openclaw-gateway.service.bak_<ver>
 - npm : npm install -g openclaw@<prev_ver>
 - gateway restart → Previous version
```

---

## Phase 2 — Preflight (Required pre-upgrade checks)

```bash
python3 shared/scripts/e2e_smoke.py --dry-run # 6/6 PASS
python3 shared/scripts/arch_lock.py check # drift=0
python3 shared/scripts/check_budget_status.py   # budget_mode != stop
python3 -c "import json; \
  hb=json.load(open('memory/infra_ticket_poller_heartbeat.json')); \
  print('heartbeat:', hb['status'])"             # status=alive
```

** On failure .**

---

## Phase 3 — Apply ()

```bash
# 1. config freeze ( live config )
touch /tmp/openclaw_config_freeze

# 2. Backup service file
cp ~/.config/systemd/user/openclaw-gateway.service \
   ~/.config/systemd/user/openclaw-gateway.service.bak_$(openclaw --version)

# 3. (user-level source of truth)
npm install -g openclaw@<target_ver>
sudo npm install -g openclaw@<target_ver>   # system-level sync

# 4. ExecStart + Description Updated
sed -i "s|/usr/lib/node_modules|$HOME/.npm-global/lib/node_modules|g" \
  ~/.config/systemd/user/openclaw-gateway.service
sed -i "s|v[0-9]*\.[0-9]*\.[0-9]*|v<target_ver>|g" \
  ~/.config/systemd/user/openclaw-gateway.service

# 5. OPENCLAW_SERVICE_VERSION Update environment variable
sed -i "s|OPENCLAW_SERVICE_VERSION=.*|OPENCLAW_SERVICE_VERSION=<target_ver>|" \
  ~/.config/systemd/user/openclaw-gateway.service

# 6. meta Updated
python3 -c "
import json,datetime,pathlib
p = pathlib.Path('/home/lishopping913/.openclaw/openclaw.json')
d = json.load(open(p))
d['meta']['lastTouchedVersion'] = '<target_ver>'
d['meta']['lastTouchedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(d, open(p,'w'), indent=2)
"

# 7. reload + restart (ADR-007 )
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service
sleep 5

# 8. Telegram 1 (1)
openclaw send --to 1555430296 --channel telegram \
 "⬆️ Upgrade applied: openclaw <target_ver> | gateway restart OK | verify "
```

---

## Phase 4 — Verify (verified)

```bash
# 4-way
which openclaw && openclaw --version
~/.npm-global/bin/openclaw --version
node -e "require('/usr/lib/node_modules/openclaw/package.json').version" | xargs echo system:
systemctl --user show openclaw-gateway.service --property=Description

# E2E smoke
python3 shared/scripts/e2e_smoke.py # 6/6 PASS

# Healthcheck
python3 shared/scripts/healthcheck.py # 7/7 PASS

# config freeze (verified )
rm -f /tmp/openclaw_config_freeze
```

**verified : 4-way + smoke 6/6 + healthcheck 7/7**

---

## Phase 5 — Rollback (On failure)

```bash
# 1. Previous version
npm install -g openclaw@<prev_ver>
sudo npm install -g openclaw@<prev_ver>

# 2. Restore service file
cp ~/.config/systemd/user/openclaw-gateway.service.bak_<prev_ver> \
   ~/.config/systemd/user/openclaw-gateway.service

# 3. reload + restart
systemctl --user daemon-reload
systemctl --user restart openclaw-gateway.service

# 4. incident ( postmortem)
# memory/incident_upgrade_fail_<date>.md:
# , Cause, ,

# 5. Telegram 1
openclaw send --to 1555430296 --channel telegram \
 "⚠️ Upgrade rollback: → <prev_ver> | Cause: <reason>"
```

---

## Phase 6 — Automation Strategy ( 1 , Manual upgrade)

**Principle**: . , Boss Approved.

```json
{
  "check_cron": "Every Monday 09:00 UTC",
 "action": "Version check only — proposal ",
  "upgrade_window": "UTC 08:00–10:00 (Outside trading hours)",
 "version_policy": "stable tag (latest )",
  "auto_execute": false,
  "boss_approval_required": true
}
```

Weekly check script location: `shared/scripts/upgrade_check.py`

---

## Change History

| Date | Previous version | Applied version | Method | Result |
|------|---------|---------|------|------|
| 2026-03-02 | 2026.2.26 (service) | 2026.3.1 | Manual (immediately after audit) | PASS |
