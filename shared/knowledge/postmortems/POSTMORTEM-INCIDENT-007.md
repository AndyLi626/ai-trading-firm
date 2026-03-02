# POSTMORTEM: INCIDENT-007
**Severity:** SEV-1
**Date:** 2026-03-02 ~20:07 UTC
**Status:** RESOLVED
**Author:** InfraBot (auto-generated 2026-03-02)

## Timeline
| Time (UTC) | Event |
|------------|-------|
| ~20:07 | InfraBot sessions_spawn with full file contents embedded in task string |
| ~20:07 | Payload: 6 full files (GOVERNANCE.md, CHANGE_LOG.md, smoke_test.py, etc.) |
| ~20:07 | Telegram session at 180,933 tokens (90% of 200k limit) |
| ~20:07 | Serialization/transport layer aborted mid-send: "Request was aborted" |

## Root Cause
Prompt-as-transport anti-pattern: InfraBot embedded full file contents into sessions_spawn task string instead of using file path references. Payload was too large for Telegram transport under heavy session load.

## Impact
- Duration: ~5 min (task aborted, had to be retried)
- Affected bots: main (InfraBot), spawned subagent never started
- Signals lost: 0
- Cost impact: ~$0.00 (aborted)

## What Went Wrong (Facts Only)
1. sessions_spawn task used as file delivery vehicle, not as goal description
2. Session was at 90% token limit — slow and fragile
3. No payload size check before sessions_spawn call

## TODO (requires proposal→review→validate→apply)
- [x] SOUL.md Transport Rules: sessions_spawn = reference-based only | owner: infra | DONE
- [x] SPAWN_TEMPLATE.md created: goal + target files + criteria format | owner: infra | DONE
- [ ] Add pre-send payload size check (>2000 chars → warn/block) | owner: infra | due: TBD

## NOT Auto-Applied
All remaining fixes require: proposal → review → validate → apply
---
Generated: 2026-03-02T15:18:00Z
