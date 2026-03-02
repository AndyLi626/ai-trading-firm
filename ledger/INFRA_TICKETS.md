# INFRA_TICKETS.md — Canonical Ticket Ledger

**last_updated**: 2026-03-02T22:16:19 UTC  
**source**: shared/state/ticket_queue.jsonl (latest-event-per-id)  
**parser**: shared/scripts/infra_ticket_status.py  

---

## INFRA-2026-03-02-004

```json
{
  "ticket_id": "INFRA-2026-03-02-004",
  "status": "RESOLVED",
  "priority": "high",
  "from": "manager",
  "to": "infra",
  "owner": "infra",
  "created_at": "2026-03-02T20:24:53+00:00",
  "resolved_at": "2026-03-02T22:15:30.756597+00:00",
  "root_cause": "Reports were reading market data from /tmp/oc_facts/MARKET_PULSE.json (transient, wiped on reboot) instead of canonical memory/market/MARKET_PULSE.json. Freshness gate was absent — no check prevented use of stale data in signals.",
  "fix_summary": "1. data_gate.py ARTIFACT_PATH updated to memory/market/MARKET_PULSE.json. 2. strategy_hint.py /tmp fallback removed. 3. market_data_validator.py MAX_AGE_MIN=5 (trading decision gate). 4. healthcheck.py market_pulse threshold=17min (system health gate). 5. ADR-011 written: two-tier freshness thresholds must not be conflated.",
  "acceptance_evidence_paths": {
    "closure_plan": "ledger/ADRs/ADR-011-freshness-thresholds.md",
    "acceptance_test_2": "memory/data_quality_status.json (status=VERIFIED is_verified=True)",
    "market_pulse_path": "memory/market/MARKET_PULSE.json",
    "market_pulse_as_of": "2026-03-02T22:07:35",
    "data_gate_proof": "data_gate.py PASS age=445s source=alpaca_iex",
    "ready_cert": "memory/READY_FOR_RESEARCH_CERT.md (5/5 PASS)"
  },
  "state_machine": [
    {
      "action": "create",
      "at": "2026-03-02T20:24:53",
      "by": "manager"
    },
    {
      "action": "ack",
      "at": "2026-03-02T20:24:53",
      "by": "infra-auto",
      "status": "IN_PROGRESS"
    },
    {
      "action": "comment",
      "at": "2026-03-02T22:03:20",
      "by": "infra",
      "note": "[状态由 Infra 更新] closure plan executed"
    },
    {
      "action": "resolve",
      "at": "2026-03-02T22:15:30",
      "by": "infra",
      "status": "RESOLVED"
    }
  ]
}
```

**Resolution Summary**  

| Field | Value |
|-------|-------|
| status | `RESOLVED` |
| resolved_at_utc | `2026-03-02T22:15:30 UTC` |
| owner | `infra` |
| root_cause | `/tmp/oc_facts/MARKET_PULSE.json` used instead of canonical `memory/market/MARKET_PULSE.json`; no freshness gate |
| fix | Path locked to canonical; `data_gate.py` freshness=5min; `healthcheck` 17min; ADR-011 written |
| acceptance_test_2 | `DATA_OK 6/6 PASS` — `memory/data_quality_status.json` status=VERIFIED is_verified=True |
| market_pulse_as_of | `2026-03-02T22:07:35 UTC` (age=7.4min ≤ 17min ✅) |
| data_gate | `PASS` source=alpaca_iex age=445s |
| cert | `memory/READY_FOR_RESEARCH_CERT.md` 5/5 PASS |

---

## All Tickets Summary

| Ticket ID | Priority | Status | Resolved At |
|-----------|----------|--------|-------------|
| `171a90a0-cf62-4503-bbba-d97e99b6da7c` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `1f60d767-f87e-4182-b25b-3099a4c7bbb8` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `296c8f63-056b-4afa-9206-100a8dc7562e` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `4f3435d4-e610-4bb3-9274-9dcbdf08f411` | normal | `RESOLVED` | 2026-03-02T20:52:20 |
| `55470d8e-50ed-4fd9-b743-8675a588f023` | normal | `RESOLVED` | 2026-03-02T22:03:44 |
| `62705ef2-f551-4a66-bb52-daed76822512` | normal | `RESOLVED` | 2026-03-02T20:52:20 |
| `62fb3acf-abe2-4df1-b16d-655914064de8` | normal | `RESOLVED` | 2026-03-02T20:52:20 |
| `8bef6ef9-9c07-4277-ac58-98b24bd7447c` | normal | `RESOLVED` | 2026-03-02T20:52:20 |
| `ADR-CHECK-20260302151644` | ? | `RESOLVED` | 2026-03-02T20:52:20 |
| `ADR-CHECK-20260302151701` | ? | `RESOLVED` | 2026-03-02T20:52:20 |
| `GOVERNANCE-CRON-SPRAWL` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `INFRA-2026-03-02-001` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `INFRA-2026-03-02-002` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `INFRA-2026-03-02-003` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `INFRA-2026-03-02-004` | high | `RESOLVED` | 2026-03-02T22:15:30 |
| `INFRA-2026-03-02-005` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `POSTMORTEM-REQUIRED-INCIDENT-006` | ? | `RESOLVED` | 2026-03-02T20:52:20 |
| `POSTMORTEM-REQUIRED-INCIDENT-007` | ? | `RESOLVED` | 2026-03-02T20:52:20 |
| `TEST-001` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `be223823-500f-4017-bbb6-168862a9f87c` | normal | `RESOLVED` | 2026-03-02T20:52:20 |
| `d6dfd5d2-1a98-46bd-98ff-3908bdd0e36e` | normal | `RESOLVED` | 2026-03-02T20:52:20 |
| `d6fa6318-ae72-464b-8eb7-656eaeaa3eab` | normal | `RESOLVED` | 2026-03-02T20:52:20 |
| `dad11f9e-0324-46f6-99f5-3fe5cc811f67` | high | `RESOLVED` | 2026-03-02T20:52:20 |
| `e981d34f-00f6-44a6-8187-d780a3e31b7f` | normal | `RESOLVED` | 2026-03-02T20:52:20 |