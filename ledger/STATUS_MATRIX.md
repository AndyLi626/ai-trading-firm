# STATUS_MATRIX.md — System Component Status
**Generated: 2026-03-02 15:01 UTC. Based on real filesystem + GCP state.**

| Component | EXISTS | WIRED | VERIFIED | Evidence |
|-----------|--------|-------|----------|----------|
| **token_accounting** | ✅ | ✅ | ⚠️ PARTIAL | gcp_client.log_token_usage() exists; 92 rows in GCP; no `status` column → failed calls untracked |
| **budget_enforcer** | ✅ | ✅ | ✅ | provider_budget_guard.py runs ok; provider_budget.json written; hard_stop logic tested |
| **ticket_system** | ✅ | ⚠️ | ⚠️ | ticket_queue.jsonl exists; infra-ticket-poll DELETED (unauthorized cron cleanup); infra_poll_unified.py exists but no active poller cron |
| **data_provenance_gate** | ✅ | ✅ | ✅ | data_gate.py; 7/7 tests pass; DATA_UNVERIFIED on missing artifact; SOUL.md rule added |
| **emergency_trigger** | ⚠️ QUARANTINED | ❌ | ❌ | emergency_trigger.py in quarantine/; deleted as unauthorized; no active cron |
| **market_pulse** | ⚠️ QUARANTINED | ❌ | ❌ | market_pulse.py in quarantine/; no MARKET_PULSE.json being produced; data_gate always fails |
| **anomaly_detector** | ⚠️ QUARANTINED | ❌ | ❌ | market_anomaly_detector.py in quarantine/; anomaly-detector cron deleted |
| **manager_delta_noop** | ✅ | ❌ | ❌ | manager_cooldown.py exists; NOT yet wired into manager-30min-report cron prompt |
| **config_guard** | ✅ | ✅ | ✅ | cron_drift_enforcer.py; 0 violations on last run (14:59 UTC); ALLOWLIST enforced |
| **postmortem_loop** | ⚠️ PARTIAL | ❌ | ❌ | postmortem_generator.py exists; postmortem_enforcer.py MISSING; no postmortems written yet |
| **model_registry** | ✅ | ✅ | ✅ | model_aliases.json; gemini-2.5-flash-lite probe ok; daily-model-reset cron active |
| **budget_refresh_cmd** | ✅ | ✅ | ✅ | budget_refresh.py; /budget refresh tested 14:21 UTC; anthropic probe ok |
| **archivist** | ⚠️ PARTIAL | ❌ | ❌ | ledger files written; archivist_query.py / apply_hook.py / drift_detector.py MISSING |
| **cron_fleet** | ✅ | ✅ | ✅ | 6 authorized crons; 0 violations; drift_enforcer allowlist correct |
| **GCP_market_signals** | ✅ | ✅ | ⚠️ | Table exists; last signal 05:34 UTC (stale ~9h); last real signal from media bot |
| **bot_cache_memory** | ✅ | ✅ | ⚠️ | bot_cache.json updated 14:55 UTC; media.last_scan 03:43 (stale); cron re-enabled 14:24 |
| **execution_service** | ✅ | ✅ | ✅ | Alpaca paper; crypto 5/5; options tested; $100k paper balance |
| **language_routing** | ✅ | ⚠️ | ⚠️ | SOUL.md rule in all 6 bots; Korean incident (openclaw.json had language_policy key, now removed); no recent test |

## Legend
✅ = Confirmed · ⚠️ = Partial/Uncertain · ❌ = Not present/not working

## Critical Gaps (require action)
1. **market_pulse QUARANTINED** → data_gate always fails → no provenance for market data
2. **ticket poller has no cron** → P0 tickets won't auto-ACK
3. **postmortem_enforcer MISSING** → SEV-0/1 incidents not tracked
4. **manager_cooldown not wired** → 30min same-type reports still fire
5. **archivist scripts MISSING** → query/preflight/apply_hook/drift_detector need to be written
