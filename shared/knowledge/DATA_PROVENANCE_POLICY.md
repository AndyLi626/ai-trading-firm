# Data Provenance Policy — AI Trading Firm
_Effective: 2026-03-02 | Owner: InfraBot_

---

## 1. Valid Market Artifact

A valid market artifact is the file `/tmp/oc_facts/MARKET_PULSE.json` produced by `market_pulse.py`.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | UUID4 string | Unique identifier for this artifact run |
| `chain_id` | UUID4 string | Same as run_id (future: multi-hop chain tracing) |
| `as_of` | ISO-8601 UTC string | Timestamp when data was fetched |
| `source` | string | Non-empty source identifier (e.g. `alpaca_iex`) |
| `synthetic` | boolean | Must be `false` — never synthetic |
| `confidence` | float 0.0–1.0 | Fraction of symbols with live prices |
| `symbols` | list[str] | Symbols included in this artifact |
| `quotes` | dict | Per-symbol price data |

### Freshness SLA

- **Maximum age:** 300 seconds (5 minutes)
- **Stale artifact** = `now - as_of > 300s` → treat as DATA_UNVERIFIED
- Artifact must be regenerated before any market-data output in a new decision cycle

### Approved Sources

- `alpaca_iex` — Alpaca Markets IEX feed (stocks)
- `hyperliquid` — Hyperliquid allMids (crypto)
- `alpaca_iex+hyperliquid` — Combined

---

## 2. DATA_UNVERIFIED

`DATA_UNVERIFIED` is the mandatory output string when the provenance gate fails.

### When to Output DATA_UNVERIFIED

A bot **must** output `DATA_UNVERIFIED — {reason}` and **stop the decision chain** when:

1. `/tmp/oc_facts/MARKET_PULSE.json` does not exist (`artifact_missing`)
2. `as_of` timestamp is older than 5 minutes (`artifact_stale`)
3. `source` field is missing or empty (`source_missing`)
4. `synthetic` field is `true` (`synthetic_data_prohibited`)
5. `run_id` field is missing (`run_id_missing`)
6. File is corrupt or unreadable (`artifact_corrupt`)

### Format

```
DATA_UNVERIFIED — artifact_stale (age=342s > max=300s)
```

Or in structured outputs:
```json
{"gate": "FAIL", "status": "DATA_UNVERIFIED", "reason": "artifact_stale"}
```

---

## 3. Gate Check Sequence

Run `python3 shared/scripts/data_gate.py` before any market data output.

```
1. File exists at /tmp/oc_facts/MARKET_PULSE.json?
       NO  → FAIL: artifact_missing
2. run_id present?
       NO  → FAIL: run_id_missing
3. source non-empty?
       NO  → FAIL: source_missing
4. synthetic == false?
      YES  → FAIL: synthetic_data_prohibited
5. as_of age ≤ 300s?
       NO  → FAIL: artifact_stale
6. All pass → PASS: emit run_id, as_of, source, age_seconds
```

Exit code 0 = PASS. Exit code 1 = FAIL (DATA_UNVERIFIED).

---

## 4. SEV-0: DATA_FABRICATION_RISK

### Definition

A SEV-0 is triggered when a bot outputs price/percentage data **without a valid provenance artifact**.

### Auto-Response

1. `audit_data_violation.py` is invoked with the bot name, output, and context
2. Decision logged to GCP `decisions` table as `SEV0_DATA_FABRICATION`
3. `bot_cache.json` updated: `{bot}.data_violation_active = true`
4. Bot is **frozen** — no further trading decisions until violation is cleared
5. Ticket JSON printed: `{"ticket":"SEV-0","severity":"DATA_FABRICATION_RISK","frozen":true}`

### Clearing a Violation

Manual review required. Set `{bot}.data_violation_active = false` and confirm root cause.

---

## 5. Global Defaults

```
synthetic_data_allowed = false
max_artifact_age_seconds = 300
gate_enforcement = strict
```

These are not overridable by individual bots.

---

## 6. Test Path Exception

Tests may set `is_test=true` in their artifact payload. Test artifacts:

- Are never routed through ManagerBot output
- Never trigger real GCP log_decision calls (mocked in test suite)
- Never count against confidence metrics

The test path is isolated by `tests/test_data_gate.py` using subprocess invocation and mock GCP client.
