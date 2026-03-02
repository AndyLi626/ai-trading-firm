# RISK_LIMITS.md — Risk Limits & Controls
_Account: PA37P8G6EG6D (Alpaca Paper) | Size: $100,000_
_Last updated: 2026-03-02_

---

## 1. Hard Limits (Enforced — No Exceptions Without Human Override)

| Limit | Value | Notes |
|---|---|---|
| Max position size (single) | $10,000 (10%) | Per symbol, any asset class |
| Max open positions | 10 | Across all asset classes simultaneously |
| Max daily loss | $2,000 (2%) | Resets at midnight ET; triggers emergency stop |
| Max drawdown from peak | $5,000 (5%) | Trailing from account high-water mark |
| Max single trade loss | $1,000 (1%) | Stop-loss must be set before order entry |
| Max leverage | 1x (no margin) | Paper account — long equity only |
| Max options exposure | $5,000 (5%) | Total notional across all open option positions |
| Max crypto exposure | $3,000 (3%) | Total notional across all crypto positions |
| Min order size | $100 | No penny trades |
| Max single order size | $5,000 | Per single order (can scale in over multiple) |

**If any hard limit is breached:** Execution is halted, AuditBot fires immediately, ManagerBot is notified, and Andy is escalated within 15 minutes.

---

## 2. Soft Limits (Preferred — Can Be Exceeded With Logged Justification)

| Limit | Preferred Value | Hard Cap |
|---|---|---|
| Single position size | $3,000–$5,000 (3–5%) | $10,000 |
| Equity exposure | ≤ 60% of account | No hard cap (see max positions) |
| Sector concentration | ≤ 20% in any single sector | 30% |
| Crypto exposure | ≤ 1% per coin | $3,000 total |
| Options exposure | ≤ 2% total notional | $5,000 |
| Cash reserve | ≥ 10% ($10,000) | None (hard floor not enforced) |
| Holding period | 1–5 days (swing) | No cap, but >14 days needs review |
| Daily trades | ≤ 10 round-trips | PDT rule: ≤ 3 day-trades in 5 days |

**Soft limit breach:** Logged in `bot_states`, flagged in next AuditBot run. No auto-halt.

---

## 3. Asset Class Exposure Guidelines

| Asset Class | Preferred Max | Hard Max |
|---|---|---|
| US Equities (long) | 60% ($60k) | 90% ($90k) |
| ETFs | 30% ($30k) | 50% ($50k) |
| Crypto (spot) | 3% ($3k) | 3% ($3k — hard) |
| Options (notional) | 5% ($5k) | 5% ($5k — hard) |
| Cash / USD | ≥ 10% ($10k) | N/A |

---

## 4. Override Policy

### Who Can Override
- **Andy (human):** Can override any limit, any time. Must be explicitly stated in chat.
- **ManagerBot:** Can temporarily relax soft limits for a single trade, with logged rationale in `decisions` table.
- **RiskBot/AuditBot/StrategyBot:** Cannot override limits. Must escalate.

### Override Process
1. Request logged in `decisions` table (GCP BigQuery) with `override=true` flag
2. Rationale written to `INCIDENT_LOG.md`
3. Override expires after the specific trade closes, or 24h — whichever comes first
4. Andy must acknowledge (reply in chat) for hard limit overrides

---

## 5. Emergency Stop Conditions

Any of the following trigger an **immediate full halt** (no new orders, all pending orders cancelled):

1. Daily loss reaches $2,000 (2%)
2. Account drawdown reaches $5,000 (5%) from high-water mark
3. 3+ consecutive order rejections in 1 hour
4. Any bot enters unrecoverable error state
5. Andy sends "STOP" or "HALT" in any bot channel
6. Alpaca API returns account-level error (margin call, pattern day trader flag, etc.)
7. Market circuit breaker / trading halt detected

**Emergency stop sequence:**
1. ExecutionService stops accepting new orders
2. AuditBot fires immediate audit
3. ManagerBot messages Andy with current state + positions
4. System waits for Andy's explicit "RESUME" before restarting

---

## 6. Policy Ownership

- **Owner:** RiskBot (maintained by InfraBot + AuditBot)
- **Review cycle:** Monthly, or after any emergency stop
- **Override authority:** Andy only for hard limits; ManagerBot for soft limits
