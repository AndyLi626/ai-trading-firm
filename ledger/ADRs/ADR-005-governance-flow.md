# ADR-005: Architecture Changes Require proposal→review→validate→apply
**Date:** 2026-03-02 | **Status:** Accepted

## Context
Bots were autonomously modifying crons, scripts, and prompts. Changes were not tracked and caused repeated incidents (INCIDENT-001 through INCIDENT-006).

## Decision
All architecture changes (cron / model routing / budget / schema / topology / prompt rewrites) must follow:
1. proposal — describe change + rationale
2. review — Boss approval (or InfraBot for whitelist items)
3. validate — run tests, confirm no regressions
4. apply — execute change, call apply_hook.py
5. rollback — document rollback point (file.bak or git tag)

InfraBot auto-remediation whitelist (no approval needed): rerun collect_*.py, refresh /tmp/oc_facts/, clear temp cache artifacts.

## Consequences
- CHANGELOG.md must have an entry for every apply step
- apply_hook.py enforces: unvalidated architecture changes → exit 1 (rejected)
- Missing CHANGELOG entry = non-compliant change

## Enforcement
apply_hook.py · ledger/CHANGELOG.md · postmortem_enforcer.py (detects incidents without postmortems)
