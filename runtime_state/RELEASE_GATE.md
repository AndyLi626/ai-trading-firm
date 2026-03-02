# RELEASE_GATE.md — v0.5 Push Conditions
_Issued: 2026-03-02 | Boss directive_

## Scope Freeze

This release cycle ONLY addresses:
- cache state freshness (end-to-end)
- failure chain tests (stale / script-fail / signal-fail / cache-degraded)
- governance + ACL snapshot
- release gate enforcement
- rollback point
- post-push smoke check

**NOT in scope this cycle:**
- Kafka or new messaging infra
- New Telegram mechanisms
- Auto-upgrade architecture
- New bots
- More complex strategies

Violation of scope freeze = treat as drift, stop and report to Boss.

---

## Release Gate Checklist

A build may be **committed** when code is complete.
A build may be **tagged stable** only when ALL of the following are green:

### Tests
- [ ] Unit tests: `python3 tests/run_all.py --fast` → all pass
- [ ] Integration tests: `python3 tests/run_all.py` → all pass
- [ ] Smoke tests: `python3 tests/smoke_test.py` → all pass

### Live Verification
- [ ] 1× complete real chain run: MediaBot → GCP signal → StrategyBot reads → RiskBot verdict → ManagerBot reports
- [ ] 3× consecutive cycles with no stale/error suppression (facts fresh, cache updated, signal written)
- [ ] Stale/error handling proof: at least 1 confirmed test of each failure scenario (A/B/C/D)
- [ ] ManagerBot cache continuation proof: ManagerBot reads prior-round conclusions and references them in next report

### Not satisfied → status
| State | Meaning |
|-------|---------|
| committed, not tagged | code merged, not yet verified |
| `v0.5-rc` | tests pass, live verification pending |
| `v0.5-stable` | ALL gate items green |

---

## Rollback Point

Before any push this cycle:
1. Run: `git tag v0.4-stable` (current last known good)
2. Record commit hash in this file
3. Document rollback procedure

**Last stable:** v0.3 → f60d1d0 (MediaBot multi-source)
**Current untagged work:** cron rebuild, GCP upgrades, bot cache, governance

**Rollback procedure:**
```bash
git checkout v0.4-stable   # or specific hash
openclaw gateway restart
python3 tests/smoke_test.py
```

---

## Post-Push Smoke Check (within 5 min of push)

Run immediately after every push:
```bash
python3 /home/lishopping913/.openclaw/workspace/tests/smoke_test.py
```

Manual checklist:
- [ ] `openclaw cron list` → 5 jobs present, no error state
- [ ] facts files updated within last 30 min (`ls -la /tmp/oc_facts/`)
- [ ] `memory/bot_cache.json` `_updated` < 30 min ago
- [ ] ManagerBot next report reads fresh state (not cached stale)
- [ ] GCP market_signals: last row timestamp < 30 min ago
- [ ] No `ok=false` in `/tmp/oc_facts/status.json`
- [ ] INCIDENT_LOG writable (append test entry, then remove)

If any item fails → do NOT mark stable → open incident → fix first.
