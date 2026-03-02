# GOVERNANCE.md — Architecture Change Policy
_Effective: 2026-03-02_

## InfraBot Operating Modes

### Default Mode: AUDIT (every 12h)
InfraBot may: inspect health, detect stale data/failed crons/broken cache, generate infra reports, auto-remediate whitelist items.

InfraBot must NOT: modify openclaw.json, edit cron schedules/prompts, change schemas, modify agent roles, rewrite governance files, install/remove skills.

### Whitelist: Auto-Remediation Allowed (no approval)
| Action | Condition |
|--------|-----------|
| Rerun collect_media.py | media_facts.json >30min old |
| Rerun collect_market.py | market_facts.json >30min old |
| Rerun collect_team.py | team_facts.json >30min old |
| Rerun media_finalize.py | bot_cache.media.last_scan_timestamp >1h |
| Clear /tmp/oc_facts/ | Files corrupt or unreadable |

### Architecture Change Protocol
Any change outside whitelist:
```
1. PROPOSAL  — what, why, risk, rollback plan
2. TESTS     — test_*.py must pass before apply
3. APPROVAL  — explicit user confirmation ("approved" / "go ahead")
4. APPLY     — make the change
5. LOG       — append to shared/knowledge/CHANGE_LOG.md
```
Tests fail at step 2 → stop. No explicit approval at step 3 → stop.

### Change Categories
| Category | Requires Approval |
|----------|-----------------|
| cron prompt / schedule edits | ✅ |
| openclaw.json edits | ✅ |
| schema changes (BQ tables) | ✅ |
| skill install/uninstall | ✅ |
| SOUL.md / AGENTS.md edits | ✅ |
| new scripts in shared/scripts/ | ✅ |
| secret updates | ✅ |
| whitelist remediation | ❌ auto |
| reading files / querying GCP | ❌ always ok |
| running tests | ❌ always ok |

---

## Scope Freeze (v0.5 cycle)
Only allowed: cache state freshness, failure chain tests, governance push, release gate.
FORBIDDEN this cycle: Kafka, new bots, new Telegram mechanisms, auto-upgrade architecture, complex strategies.

---

## Testing Policy
Tests are mandatory gates — not optional checks.

Layers: unit → integration → smoke. Run order: pre-deploy (unit+integration), post-deploy (smoke).

```bash
python3 tests/run_all.py --fast    # pre-deploy
python3 tests/run_all.py           # full regression
python3 tests/smoke_test.py        # post-deploy
```

Test failure → report to Boss, stop, do not apply. No exceptions.

---

## MediaBot Routing Policy (enforced 2026-03-02)
| Signal type | Route to |
|-------------|----------|
| Source/collector failure | InfraBot via sessions_send |
| Trading-relevant insight | StrategyBot via GCP market_signals |
| Summary / coordination | ManagerBot cache (bot_cache.media) |
| Human notification | ManagerBot (default sender) |
| Critical ops incident | InfraBot direct to human |

See: ACL_SNAPSHOT.md for full permission matrix.
See: CHANGE_LOG.md for audit trail.

## Config Change Guard

All changes to `~/.openclaw/openclaw.json` are mediated by `shared/tools/config_guard.py`, which enforces a strict propose → review → apply → audit pipeline. No bot may edit the live config directly. ManagerBot (and InfraBot) may submit proposals via `propose <bot_id> <json_patch>`; proposals land in `shared/config_proposals/pending/` and are validated against an allowlist of safe paths (`agents.list[*].model.primary`, `agents.list[*].identity.*`, `agents.defaults.*`, and `cron[*].schedule`). Any path outside this allowlist, any forbidden schema key (e.g. `agentToAgent`, `tools`), or any submission from a no-write bot (Media, Research, Risk) is immediately rejected. AuditBot runs `review` to approve or reject pending proposals; only then can InfraBot call `apply`, which backs up the live config, applies the patch, validates with `openclaw gateway status`, restores the backup on failure, and appends an entry to `CHANGE_LOG.md`. The full directory structure and role matrix are documented in `shared/config_proposals/README.md`.
