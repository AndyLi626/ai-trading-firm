# Rollback Point — v0.4-pre-release
_Created: 2026-03-02 (v05-failure-tests-cache-contract cycle)_

## Git State at Tag

**Tag:** `v0.4-pre-release`
**Commit hash:** `f60d1d0fd7ecf38303750bd5fe472168bd06a684`
**Branch:** master

### git log --oneline -5
```
f60d1d0 v0.3 — MediaBot multi-source: Brave+Twitter+XHS, test suite 11/11
6f46233 v0.2 — crypto+options execution, test suite, session optimization
6ff5577 docs: add INCIDENT_LOG.md + tighten API limits
ca88f27 fix: P1/P2/P3 system fixes
6b30979 chore: cleanup stale dirs, add shared/tools/load_secrets.py
```

## Files Changed This Cycle
| File | Change |
|------|--------|
| `tests/test_failure_chains.py` | **NEW** — 4 failure-chain scenarios (A/B/C/D), 10 checks |
| `shared/scripts/check_manager_cache.py` | **NEW** — ManagerBot cache contract validator |
| `tests/run_all.py` | **MOD** — added failure_chains to suite list |
| `runtime_state/RELEASE_GATE.md` | **NEW** — v0.5 push conditions and gate checklist |
| `shared/knowledge/ACL_SNAPSHOT.md` | **NEW** — ACL governance snapshot |
| `runtime_state/rollback_point.md` | **NEW** — this file |
| `~/.openclaw/cron/jobs.json` | **MOD** — manager cron prompt updated with cache contract |

## Tag Recommendation
- Current tag: `v0.4-pre-release` (tests pass, cache contract in place, not yet live-verified)
- Promote to `v0.4-stable` once: `python3 tests/run_all.py --fast` passes in full
- Promote to `v0.5-stable` once all RELEASE_GATE.md gate items are green

## Rollback Command
```bash
git checkout f60d1d0
openclaw gateway restart
python3 tests/smoke_test.py
```

Or by tag (once promoted):
```bash
git checkout v0.4-pre-release
openclaw gateway restart
python3 tests/smoke_test.py
```
