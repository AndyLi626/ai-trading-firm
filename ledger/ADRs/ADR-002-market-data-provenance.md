# ADR-002: Market Data Must Have Provenance
**Date:** 2026-03-02 | **Status:** Accepted

## Context
Bots were outputting price/percentage numbers fabricated from session memory or LLM estimation. This is DATA_FABRICATION_RISK.

## Decision
Every market data output must carry: as_of + source + run_id/chain_id. Missing any field → output "DATA_UNVERIFIED" and stop decision chain. Synthetic data prohibited (synthetic=false enforced).

## Consequences
- data_gate.py is the gate: exit 0 = PASS, exit 1 = FAIL
- SEV-0 DATA_FABRICATION_RISK triggered if bot outputs price/% without provenance
- audit_data_violation.py logs to GCP + freezes bot_cache trading proposals

## Enforcement
data_gate.py · SOUL.md § Data Provenance Gate (all 6 bots) · test_data_gate.py (7/7)
