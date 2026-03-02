# ADR-011 — Two-Tier Freshness Thresholds for Market Data

**Status**: Approved  
**Date**: 2026-03-02  
**Context**: After INFRA-004 closure, two distinct freshness thresholds are in use.
Mixing them causes false healthcheck failures (5min gate vs 15min cron cadence).

## Decision

Two separate thresholds exist for different purposes. They MUST NOT be conflated.

| Layer | Threshold | Enforced by | Purpose |
|-------|-----------|-------------|---------|
| **Trading decision gate** | **≤ 5 min** | `data_gate.py`, `market_data_validator.py` | Can we trust this data for an actual trade/signal? |
| **System health check** | **≤ 17 min** | `healthcheck.py check_market_pulse` | Is the market-pulse-15m cron still running? (15min + 2min buffer) |

## Rules

1. `data_gate.py --max-age-seconds 300` (5min) gates all trade-facing paths.
2. `market_data_validator.py` MAX_AGE_MIN = 5 gates signal generation.
3. `healthcheck.py` market_pulse check = 17min (confirms cron is alive, not data freshness).
4. **Do NOT tighten healthcheck to match trading gate** — this creates false failures
   during the normal 15min cron window.
5. If tighter trading data is needed in future → change cron cadence, NOT healthcheck threshold.

## Rationale

- market-pulse-15m cron fires every 900s. Data is "stale" for up to 900s between runs.
- A 5min healthcheck gate would fail ~66% of the time even with a healthy cron.
- The healthcheck gate tests "is the cron running?" not "is data trade-fresh?".
