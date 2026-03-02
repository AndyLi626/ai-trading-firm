# ACL_SNAPSHOT.md — Bot Capability & Permission Boundaries
_Issued: 2026-03-02 | Boss directive — freeze before v0.5 push_

This document is a hard boundary reference. Any bot action outside its column is a violation.
Violations must be logged in INCIDENT_LOG.md.

---

## Permission Matrix

| Bot | Can Read | Can Write | Cannot Touch |
|-----|----------|-----------|--------------|
| **ManagerBot** | facts/cache/signals/status/risk_decisions | manager_requests, manager_cache, manager_reports | infra config, cron schedules, schema, strategy logic |
| **InfraBot** | manager_requests, all infra status, all config files | scripts, cron config, infra status, governance docs, CHANGE_LOG | manager policy, strategy verdicts, risk decisions, execution orders |
| **StrategyBot** | market_facts, media_facts, bot_cache.strategy | signals (GCP market_signals), strategy_cache | infra config, risk limits, execution layer, manager directives |
| **MediaBot** | web/news sources, bot_cache.media | media_facts, market_signals (media type), bot_cache.media | strategy verdicts, risk decisions, infra config, cron |
| **RiskBot** | market_signals, market_facts, risk_limits | risk_decisions (GCP), risk verdict per trade_plan | architecture config, cron, bot prompts, execution config |
| **AuditBot** | all logs, all facts, all GCP tables (read-only) | INCIDENT_LOG, audit reports, bot_states (audit field) | any operational config, cron, schema, live execution |

---

## Data Flow — Allowed Signal Chain

```
MediaBot → media_facts → GCP market_signals (media)
StrategyBot → reads market_facts + media_facts → GCP market_signals (strategy)
RiskBot → reads market_signals + market_facts → GCP risk_decisions
ManagerBot → reads facts + cache + risk_decisions → manager_reports
InfraBot → reads all → writes infra status + governance only
AuditBot → reads all → writes incident log + audit reports only
```

Cross-writes outside this chain = violation.

---

## File Ownership

| Path | Owner | Others |
|------|-------|--------|
| `/tmp/oc_facts/media_facts.json` | MediaBot (write) | all (read) |
| `/tmp/oc_facts/market_facts.json` | StrategyBot (write) | all (read) |
| `/tmp/oc_facts/team_facts.json` | InfraBot script (write) | all (read) |
| `/tmp/oc_facts/status.json` | scripts (write) | all (read) |
| `memory/bot_cache.json` | scripts via update_cache.py | all (read) |
| `shared/knowledge/INCIDENT_LOG.md` | AuditBot + InfraBot (append) | all (read) |
| `shared/knowledge/CHANGE_LOG.md` | InfraBot only (append) | all (read) |
| `runtime_state/RELEASE_GATE.md` | InfraBot (update gate status) | all (read) |
| `execution/execution_service.py` | InfraBot (modify) | StrategyBot/RiskBot (import only) |
| `shared/scripts/collect_*.py` | InfraBot (modify) | cron runner (exec only) |

---

## ManagerBot Cache Contract

ManagerBot MUST maintain and use the following fields in `bot_cache.manager`:

```json
{
  "last_round_conclusions": ["..."],
  "open_issues": ["..."],
  "blocked_items": ["..."],
  "last_real_data_timestamp": "ISO8601",
  "pending_requests": ["..."],
  "last_full_chain_status": "ok | degraded | stale | unknown",
  "last_updated": "ISO8601"
}
```

### Write contract (every report cycle):
ManagerBot MUST update all fields above before completing its report.

### Read contract (start of every report cycle):
ManagerBot MUST:
1. Read `bot_cache.manager` from prior round
2. Explicitly reference which open_issues are now resolved
3. Explicitly reference which blocked_items remain blocked
4. NOT produce a new report that ignores prior-round findings
5. If `last_full_chain_status = degraded` → open report with degraded notice, not success framing

### Proof of cache continuation:
ManagerBot report must contain at least one explicit back-reference:
> "Last round: [X]. This round: [Y]. Delta: [Z]."

If bot_cache.manager is missing or stale (>2h): report as `CACHE_MISSING` and refuse to present as fresh state.

---

## Failure Handling Contract (all bots)

| Failure | Required Bot Behavior |
|---------|-----------------------|
| facts stale (>30min) | Report stale, do NOT continue reasoning as if fresh |
| script ok=false | Report error only, do NOT infer/extrapolate |
| signal write failed | Log failure explicitly, downstream bots must NOT assume signal arrived |
| cache update failed / schema mismatch | Mark round as `degraded`, ManagerBot leads with degraded notice |

No bot may silently suppress a failure and present its output as successful.
