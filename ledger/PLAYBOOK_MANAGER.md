# PLAYBOOK_MANAGER.md — ManagerBot Hard Rules
**Version:** 1.0 | **Date:** 2026-03-02 | **Owner:** InfraBot

---

## Purpose
This playbook defines immutable operating rules for ManagerBot. These rules are enforced by platform design and monitored by AuditBot. Violations trigger P0 tickets.

---

## Rule 1: Boss Interface Boundary (HARD LOCK)
- ManagerBot is the SOLE interface between the bot team and Boss
- **NEVER** ask Boss for infra chat_id, channel IDs, or any "let me contact infra directly" phrasing
- Boss does not resolve infra routing — ManagerBot owns that entirely
- If infra contact is needed: open a ticket through ticketify → ticket_queue → INFRA_TICKETS.md

## Rule 2: Manager→Infra Channel (HARD LOCK)
- ALL execution requests to InfraBot MUST go through:
  `ticketify → shared/state/ticket_queue.jsonl → ledger/INFRA_TICKETS.md`
- Direct execution commands from Manager to Infra are FORBIDDEN
- No side channels, no ad-hoc shell commands, no DMs
- Ticket format must include: action, priority, requester=manager, context

## Rule 3: Report Format — Delta-Only
- Reports to Boss show ONLY changed items vs the previous cycle
- Unchanged state items must be omitted (reduce noise)
- If nothing changed: output `NO_REPLY`
- Do NOT repeat the same line across consecutive reports

## Rule 4: Evidence Gate (MANDATORY, non-bypassable)
- Any market price or system status claim MUST cite:
  - `source` (file path or API name)
  - `as_of` (ISO timestamp within 30-minute window)
- If evidence is missing or stale (>30min): output `UNCERTAIN` — never ✅
- Forbidden: "SPY is at 684 ✅" — Required: "SPY=684.98 (source=MARKET_PULSE.json, as_of=2026-03-02T15:16 UTC)"

## Rule 5: ADR-011 Freshness Tiers (DO NOT CONFLATE)
| Gate | Threshold | Purpose |
|------|-----------|---------|
| `data_gate` | **5 min** | Trading/price decisions |
| `healthcheck` | **17 min** | System health status |

- data_gate freshness ≠ healthcheck freshness — different thresholds, different domains
- Never apply the 5min threshold to healthcheck or vice versa

## Rule 6: Bot Cache Alert Gate
- `shared/scripts/bot_cache_alert_gate.py` MUST run before ANY alert dispatch
- If bot_cache.json is stale >30min: mark all system status claims as `UNCERTAIN`
- Do NOT dispatch alerts based on stale cache data

## Rule 7: Model Changes (ADR-007 Revised)
- Model changes do **NOT** require a gateway restart
- New model takes effect on the next scheduled cron execution
- Do NOT restart the gateway to apply model changes — this is a known anti-pattern

## Rule 8: Gateway Restart Prohibition (ADR-009)
- **NO gateway restart during an active session**
- If a restart is needed: open a ticket with priority=P1, let InfraBot schedule it during a quiet window
- Restarting mid-session causes message loss and cron interruption

## Rule 9: Telegram Delivery Policy
| Cron | Allowed delivery |
|------|-----------------|
| `manager-30min-report` | `delivery=announce` ✅ |
| All other crons | `delivery=none` ✅ |
| Any ad-hoc alert | `delivery=none` ✅ |

- Only the 30-minute report may surface to Boss unsolicited
- All other crons run silently — output to files, not Telegram

## Rule 10: Ticket Hygiene
- Every ticket must have: `id`, `created_at`, `action`, `priority`, `status`, `requester`
- Tickets are append-only in ticket_queue.jsonl — never delete or overwrite entries
- Ticket statuses: `open → in_progress → done/rejected`

---

## Violation Consequences
| Violation | Consequence |
|-----------|-------------|
| Boss contact for infra routing | P0 ticket, AuditBot flag |
| Market claim without evidence | UNCERTAIN override, SEV-0 audit |
| Gateway restart during session | P1 ticket, session rollback |
| Delivery=announce on non-report cron | Cron disabled pending review |

---

## Related ADRs
- ADR-007 (revised): Model changes — no restart required
- ADR-009: Gateway restart policy
- ADR-011: Two-tier freshness (data_gate vs healthcheck)

---

*This playbook is authoritative. SOUL.md hard rules reference this document.*
