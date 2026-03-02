# ADR-010 — MARKET_PULSE.json as Single Source of Truth for Market Data

**Status**: Approved  
**Date**: 2026-03-02  

## Decision

`memory/market/MARKET_PULSE.json` is the **sole authoritative source** for real-time market data
in this system. No other path, LLM-generated value, or cached variable may be cited as a market price.

## Rules

1. **MARKET_PULSE.json is written exclusively by `market_pulse.py`** — executed via OS cron (no LLM session)
2. **LLM agents MUST NOT generate, estimate, or "fill in" price values** — any market claim without
   citation of `MARKET_PULSE.json` + `as_of` timestamp → `DATA_UNVERIFIED`
3. **Staleness limit**: data older than 20 minutes is automatically `DATA_UNVERIFIED`
4. **Validation**: `market_data_validator.py` runs after every pulse, writes
   `memory/data_quality_status.json`. If `is_verified=false`, downstream consumers treat data as unreliable.
5. **Cross-check**: internal price consistency checked on every validation run;
   deviations >1% logged as incidents (non-blocking)

## Data Flow

```
OS cron (15min)
  → market_pulse.py
  → memory/market/MARKET_PULSE.json  ← SINGLE SOURCE OF TRUTH
  → market_data_validator.py
  → memory/data_quality_status.json  ← Evidence Gate reads this
```

## Evidence Gate Integration

`evidence_gate.py` must check `data_quality_status.json.is_verified` before returning `VERIFIED`
for any market price claim. If `is_verified=false`, return `UNCERTAIN` regardless of as_of.

## Paper Trading

Paper trading account data is sourced exclusively from Alpaca Paper API
(not from MARKET_PULSE). See `paper_account_monitor.py`.
