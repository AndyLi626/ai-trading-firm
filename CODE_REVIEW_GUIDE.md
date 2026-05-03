# Code Review Guide

## Scope

This repository is a paper-trading engineering prototype focused on multi-agent
orchestration, cost control, auditability, and safe execution boundaries. It is
not a live trading system and does not include real-money execution.

The intended review target is the engineering shape of the system: how work is
routed, how claims are guarded, how token usage is controlled, and how execution
is kept behind a paper-trading boundary.

## Suggested Review Path

1. `README.md` - High-level system map, safety scope, and the main operating
   concepts.

2. `shared/scripts/infra_poll_unified.py` and `shared/tools/ticket_queue.py` -
   Deterministic task routing between agents through file-backed tickets rather
   than direct bot-to-bot chat.

3. `shared/scripts/run_with_budget.py` and `shared/tools/budget_guard.py` -
   Token and cost guardrails for agent runs, including warn/degrade/stop
   thresholds.

4. `shared/tools/evidence_gate.py` and `shared/tools/config_check.py` -
   Reviewable guardrails for sourced claims and controlled configuration
   changes.

5. `execution/execution_service.py` - The paper-trading execution boundary.
   Orders must be risk-approved and are routed only to paper/test venues.

6. `shared/tools/gcp_client.py`, `shared/tools/token_meter.py`, and `tests/` -
   Audit logging, token accounting, and the smoke-test harness used to check
   operational assumptions.

## What to Ignore First

- `runtime_state/` and `workspace-manager/runtime_state/`
- local logs and generated JSONL files
- generated state snapshots under `shared/state/`
- archived experiments under `quarantine/`
- historical ledgers or rollback snapshots unless you are reviewing operating
  process

Those artifacts are useful context, but they are not the best first signal of
code quality.

## Quick Local Checks

These checks do not require live trading credentials:

```bash
py -m compileall .
py shared/tools/config_check.py
```

On macOS/Linux, replace `py` with `python3`.

Current smoke-test status: the full smoke suite is environment-dependent. It
expects a local OpenClaw workspace plus configured GCP/Alpaca paper credentials,
so it is not a pure fresh-clone test yet.

## Known Limitations

- Prototype-level market and risk modeling.
- Paper-trading/test venues only; no real-money execution is included.
- Some operational tests depend on local OpenClaw, GCP, and market-data setup.
- Future work: stronger fresh-clone tests, stricter type validation, better
  cross-platform file locking, and cleaner deployment automation.
