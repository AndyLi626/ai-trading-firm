# ADR-004: Budget Enforced Per Provider with Hard Stop
**Date:** 2026-03-02 | **Status:** Accepted

## Context
Global token count ≠ real billing. Anthropic balance hit zero while system reported 73% of "global budget". Failure: no per-provider isolation.

## Decision
Each provider has independent daily $ cap + hard stop:
- anthropic: $1.00/day
- qwen: $0.50/day
- google: $0.30/day

Failed providers enter cooldown (15min), switch to alias model or stop. Budget state tracked in bot_cache.budget.{provider}_hard_stop.

Manual reset: /budget refresh (probe + recalculate, never resets spent tokens).

## Consequences
- provider_budget_guard.py is the gate (called by all LLM paths before execution)
- budget_refresh.py is the manual recovery tool (Boss-only)
- model_override_reset.py resets temp overrides at UTC 00:00

## Enforcement
provider_budget_guard.py · budget_refresh.py · model_aliases.json caps · test_model_governance.py
