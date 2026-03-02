# ADR-002: delivery:none for All Autonomous Jobs
**Date:** 2026-03-02 | **Status:** ACCEPTED

## Decision
All cron jobs except manager-30min-report and infra-5min-report use delivery:none.
Only ManagerBot surfaces results to Boss via synthesized delta briefs.

## Why
- Root cause of "Market Scan — No Setup" spam (job 97885e6c, delivery=announce, fell back to infra token)
- Single output channel prevents duplicate/fragmented Telegram messages

## Consequence
MediaBot/ResearchBot/etc. write to /tmp/oc_facts/ and bot_cache. ManagerBot reads and reports.
