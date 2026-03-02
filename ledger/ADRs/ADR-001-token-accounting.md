# ADR-001: Token Accounting via JSONL Harvest
**Date:** 2026-02-xx | **Status:** ACCEPTED

## Decision
Harvest token usage from `cron/runs/*.jsonl` into GCP `token_usage_calls` + `token_usage_runs`.
Call-level granularity from OpenClaw session transcripts.

## Why not runtime hook?
OpenClaw does not expose a hookable LLM wrapper. JSONL harvest is the only viable approach.

## Consequence
- Call-level = run granularity (not per-API-call)
- Message-level data unavailable
- Fallback: /tmp/oc_facts/token_meter_fallback.jsonl + --replay-fallback
