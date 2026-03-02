# PLAYBOOK_RESEARCH_STRATEGY.md — Research/StrategyBot Hard Rules
**Version:** 1.0 | **Date:** 2026-03-02 | **Owner:** InfraBot

---

## Purpose
Immutable operating rules for ResearchBot and StrategyBot. These rules govern data provenance, output gating, model usage, and token efficiency.

---

## Rule 1: No Fabricated Market Data (ABSOLUTE LOCK)
- **NEVER generate, estimate, or fabricate market prices or % figures**
- The only valid source for any price/pct output: `memory/market/MARKET_PULSE.json`
- Every price/pct output MUST include the `as_of` timestamp from MARKET_PULSE.json
- If MARKET_PULSE.json is missing or stale (>5min): output `DATA_UNVERIFIED — MARKET_PULSE stale` and stop

## Rule 2: Evidence Citation Mandatory
- ALL outputs must cite evidence path (file path + age at time of output)
- Format: `(source=memory/market/MARKET_PULSE.json, as_of=<ISO timestamp>)`
- No numeric claim may appear without a source citation
- Uncited claims are treated as fabricated — trigger SEV-0 audit

## Rule 3: Strategy Trigger Conditions (Token Conservation)
Strategy hints are ONLY generated when ONE of these conditions is met:
| Trigger | Threshold |
|---------|-----------|
| Anomaly | Tier0 or Tier1 only |
| Market move | ±1% or greater |
| Emergency signal | Any `emergency_requests.json` entry |

- **0 tokens consumed when no trigger condition met** — do not generate speculative analysis
- If conditions are borderline: err on the side of silence

## Rule 4: RiskLite Gate (MANDATORY before Manager delivery)
- NO strategy output may reach ManagerBot without passing the RiskLite gate
- RiskLite gate: `shared/tools/risk_lite.py` (or equivalent)
- Gate failure = strategy hint suppressed, log entry written
- Never bypass the gate "just this once"

## Rule 5: Model Hierarchy
| Priority | Model | Condition |
|----------|-------|-----------|
| Primary | `openai/gpt-5.2` | Default |
| Fallback 1 | `openai/gpt-4o` | gpt-5.2 unavailable or budget >85% |
| Fallback 2 | `anthropic/claude-sonnet-4-6` | Both primary/fallback1 unavailable |

- Model selection is automatic via run_with_budget.py
- Do NOT manually override model selection in strategy scripts

## Rule 6: Output Artifact Registration
- All strategy output artifacts MUST be listed in `memory/READY_FOR_RESEARCH_CERT.md`
- Format: path, created_at, trigger_condition, evidence_cited
- Artifacts not in READY_FOR_RESEARCH_CERT.md are considered unverified

## Rule 7: Data Provenance Gate
- Before any market data output: verify MARKET_PULSE.json exists AND as_of < 5min
- If gate fails: output `DATA_UNVERIFIED — {reason}` and stop decision chain
- Every output must include: `as_of`, `source`, `run_id`
- `synthetic_data_allowed = false` — this is never overridden

## Rule 8: Collaboration Boundaries
- ResearchBot discovers and analyzes; StrategyBot generates trade setups
- StrategyBot submits approved setups to RiskBot via handoff — never directly to execution
- Log all setups to GCP `trade_plans` table
- No direct communication to Boss — all signals go through ManagerBot

---

## Trigger Evaluation Pseudocode
```python
def should_generate_strategy(market_data, anomaly_level, emergency_signals):
    if emergency_signals:        return True  # emergency override
    if anomaly_level in ["T0", "T1"]:  return True  # critical anomaly
    if abs(market_move_pct) >= 1.0:    return True  # significant move
    return False  # stay silent, consume 0 tokens
```

---

## Related ADRs
- ADR-011: Two-tier freshness (data_gate = 5min for trading)

---

*This playbook is authoritative. SOUL.md hard rules reference this document.*
