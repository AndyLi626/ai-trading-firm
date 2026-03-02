# Config Proposals — Directory Structure

All changes to `~/.openclaw/openclaw.json` **must** flow through this pipeline. Direct edits are prohibited.

## Flow

```
propose → pending/  →  review → reviewed/  →  apply → applied/
                         (AuditBot)             (InfraBot)
```

### 1. Propose (`pending/`)
Any authorized bot submits a JSON patch via:
```bash
python3 shared/tools/config_guard.py propose <bot_id> '<json_patch>'
```
Files land here as `<timestamp>_<bot>.json` with status `pending`.

### 2. Review (`reviewed/`)
AuditBot validates the proposal against the allowlist and schema:
```bash
python3 shared/tools/config_guard.py review shared/config_proposals/pending/<file>
```
Status becomes `approved` or `rejected`. Rejected proposals stay here for audit.

### 3. Apply (`applied/`)
InfraBot applies **approved** proposals only:
```bash
python3 shared/tools/config_guard.py apply shared/config_proposals/reviewed/<file>
```
- Backs up live config to `~/.openclaw/backups/`
- Applies the patch
- Runs `openclaw gateway status` to validate
- Restores backup on failure
- Logs result to `shared/knowledge/CHANGE_LOG.md`
- Moves proposal here on success

## Roles
| Bot | Permission |
|-----|-----------|
| ManagerBot | propose only |
| AuditBot | review only |
| InfraBot | apply only |
| Media/Research/Risk | no write access |

## Allowlisted Paths
- `agents.list[*].model.primary`
- `agents.list[*].identity.name`
- `agents.list[*].identity.emoji`
- `agents.defaults.timeoutSeconds`
- `agents.defaults.contextTokens`
- `cron[*].schedule`

Everything else is **REJECTED**.
