# ADR-003: File-Based Emergency Trigger (no sessions_send)
**Date:** 2026-03-02 | **Status:** ACCEPTED

## Decision
/pulse command writes to /tmp/oc_facts/emergency_requests.json.
MediaBot polls this file every 1min (not via sessions_send or message tool).

## Why
- sessions_send is not a valid tool in cron agent allow lists
- File-based is deterministic, auditable, and survives session restarts
- Dedup (10min/symbol) and rate limit (3→20/h) enforced at write time

## Consequence
Max latency = 1min (poll interval). Acceptable for out-of-cycle scans.
