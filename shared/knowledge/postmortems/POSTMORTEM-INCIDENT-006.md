# POSTMORTEM: INCIDENT-006
**Severity:** SEV-1
**Date:** 2026-03-01 20:32 UTC
**Status:** RESOLVED
**Author:** InfraBot (auto-generated 2026-03-02)

## Timeline
| Time (UTC) | Event |
|------------|-------|
| 20:30:24 | Session at 185k/200k tokens (93%). Compaction triggered. |
| 20:30:24 | compaction start |
| 20:32:16 | agent start — 112 seconds on compaction |
| 20:32:16 | timeoutSeconds was 120s. Agent had <8s to respond. Timed out. |

## Root Cause
Main session hit 93% token capacity. Compaction took 112s. Agent timeout was still 120s (update to 180s not yet applied). Immediate timeout on resume.

## Impact
- Duration: ~2 min
- Affected bots: main (InfraBot)
- Signals lost/corrupted: 0
- Cost impact: ~$0.00 (aborted before LLM call)

## What Went Wrong (Facts Only)
1. timeoutSeconds=120s was too short for sessions with heavy compaction
2. 180s update had been applied to config but not yet picked up by running session
3. No session token watermark alert to warn before 90%

## TODO (requires proposal→review→validate→apply)
- [x] agents.defaults.timeoutSeconds → 240s | owner: infra | DONE
- [ ] Add session token watermark alert at 80% | owner: infra | due: TBD
- [ ] Reduce session token accumulation (subagent delegation for heavy tasks) | owner: infra | due: TBD

## NOT Auto-Applied
All remaining fixes require: proposal → review → validate → apply
---
Generated: 2026-03-02T15:18:00Z
