# ADR-003: Unauthorized Cron Jobs Are Immediately Disabled
**Date:** 2026-03-02 | **Status:** Accepted

## Context
Bots autonomously created 8+ cron jobs (market-pulse-15m, emergency-scan-poll, anomaly-detector, etc.) without approval. These ran at 1-minute intervals, burned budget, and caused signal spam.

## Decision
ALLOWLIST of 6 authorized crons is the single source of truth. Any cron not in the list is: (1) immediately disabled via openclaw cron remove, (2) logged as CRON-DRIFT ticket, (3) root cause investigated.

ALLOWLIST: media-intel-scan, strategy-scan, manager-30min-report, infra-5min-report, audit-daily, daily-model-reset.

## Consequences
- Root cause was snapshot_capabilities.py hardcoding J06-J11; file quarantined
- All new crons require proposal→review→validate→apply (apply_hook.py enforces)
- InfraBot 12h audit runs cron_drift_enforcer.py as first step

## Enforcement
cron_drift_enforcer.py (ALLOWLIST hardcoded) · infra-5min-report cron (12h scan)
