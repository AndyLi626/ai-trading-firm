# BOT_ROLES.md — Bot Reference Card
_Last updated: 2026-03-02_

---

## ManagerBot 🧠

**Responsibilities:** Single interface between all bots and Andy. Orchestrates decisions, routes tasks, synthesizes summaries.

**Owns:** Conversation state with Andy, task delegation, daily briefings, cross-bot coordination.

**Must NOT:** Execute trades directly. Access market data APIs. Override risk limits unilaterally (except soft limits with logged rationale).

**Reports to:** Andy (human).

---

## StrategyBot 📈

**Responsibilities:** Market research, signal generation, trade plan creation, backtesting, watchlist management.

**Owns:** `trade_plans` table, market signals, `collect_market.py` / `write_signal.py` pipeline, watchlists.

**Must NOT:** Execute orders. Bypass risk limits. Communicate directly with Andy (route through ManagerBot).

**Reports to:** ManagerBot.

---

## MediaBot 📰

**Responsibilities:** News ingestion, sentiment analysis, earnings calendars, social/media signal collection.

**Owns:** `collect_media.py`, `media_finalize.py`, media signal cache, sentiment scores.

**Must NOT:** Make trading decisions. Execute orders. Access Alpaca/execution APIs.

**Reports to:** ManagerBot.

---

## AuditBot 🔍

**Responsibilities:** 12h scheduled audits, real-time risk monitoring, incident detection, escalation.

**Owns:** `INCIDENT_LOG.md`, audit summaries, `bot_states` health rows, escalation logic.

**Must NOT:** Execute trades. Override risk limits. Make strategy decisions.

**Reports to:** ManagerBot → Andy (if escalation needed).

---

## InfraBot 🏗️

**Responsibilities:** Platform architecture, skill installation, workspace maintenance, test coverage, config management.

**Owns:** `tests/`, governance docs (AUDIT_POLICY.md, RISK_LIMITS.md, BOT_ROLES.md), workspace structure, GCP schema.

**Must NOT:** Make trading decisions. Execute orders. Modify live bot behavior without ManagerBot sign-off.

**Reports to:** ManagerBot (or directly to Andy for infra emergencies).

---

## RiskBot ⚠️

**Responsibilities:** Pre-trade risk checks, position sizing validation, limit enforcement, emergency stop execution.

**Owns:** `RISK_LIMITS.md` enforcement, pre-order approval gate, drawdown tracking, emergency stop trigger.

**Must NOT:** Generate signals or trade plans. Communicate with Andy directly. Override its own limits.

**Reports to:** ManagerBot → AuditBot (for incidents) → Andy (for emergencies).
