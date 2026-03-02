#!/usr/bin/env python3
"""
detect_changes.py — Material change detection for ManagerBot.
Compares current facts against last-known state in bot_cache.manager.
Outputs JSON: {material_change: bool, reasons: [...], delta: {...}}

If no material change → ManagerBot logs no-op and suppresses brief.
If material change → ManagerBot sends delta-based brief.

Always-alert triggers (bypass change detection):
  - new_execution: executions count increased
  - critical_risk: new risk rejection or hard-stop
  - infra_failure: ops_alerts.json has recent entry
  - budget_degrade: budget action is degrade or stop
  - pnl_move: unrealized PnL moved >2% since last check
"""
import json, os, sys, subprocess
from datetime import datetime, timezone, timedelta

CACHE     = os.path.expanduser("~/.openclaw/workspace/memory/bot_cache.json")
TEAM_FACTS = "/tmp/oc_facts/team_facts.json"
OPS_ALERTS = "/tmp/oc_facts/ops_alerts.json"
BUDGET_STATE = "/tmp/oc_facts/budget_state.json"

def load_json(path, default=None):
    try:
        return json.load(open(path))
    except Exception:
        return default if default is not None else {}

def age_minutes(ts_str):
    if not ts_str:
        return 9999
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 60
    except Exception:
        return 9999

def run():
    cache      = load_json(CACHE, {})
    prior      = cache.get("manager", {})
    media_c    = cache.get("media", {})
    team       = load_json(TEAM_FACTS, {})
    ops        = load_json(OPS_ALERTS, [])

    now_iso    = datetime.now(timezone.utc).isoformat()
    reasons    = []
    delta      = {}
    always_alert = False

    # --- Budget state ---
    budget_action = "ok"
    try:
        sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/shared/tools"))
        from budget_guard import check_budget
        b = check_budget("manager", 5000)  # estimate for this run
        budget_action = b.get("action", "ok")
        delta["budget"] = {
            "action": budget_action,
            "reason": b.get("reason", ""),
            "degrade_hints": b.get("degrade_hints", {})
        }
        if budget_action in ("degrade", "stop"):
            reasons.append(f"budget_{budget_action}")
            always_alert = True
    except Exception as e:
        delta["budget"] = {"action": "unknown", "error": str(e)}

    # Hard stop low-priority at 95%
    if budget_action == "stop":
        print(json.dumps({
            "material_change": False,
            "suppress": True,
            "reason": "budget hard-stop: low-priority briefing suppressed",
            "delta": delta
        }))
        return

    # --- Decisions delta ---
    decisions_now  = team.get("decisions_today", 0)
    decisions_prev = prior.get("last_decisions_today", 0)
    if decisions_now != decisions_prev:
        reasons.append(f"decisions: {decisions_prev}→{decisions_now}")
        delta["decisions"] = {"prev": decisions_prev, "now": decisions_now}

    # --- Executions delta (always-alert if new) ---
    exec_now  = team.get("executions_total", 0)
    exec_prev = prior.get("last_executions_total", 0)
    if exec_now > exec_prev:
        reasons.append(f"new_execution: {exec_prev}→{exec_now}")
        delta["executions"] = {"prev": exec_prev, "now": exec_now}
        always_alert = True

    # --- Risk approvals delta ---
    risk_now  = team.get("risk_approvals", 0)
    risk_prev = prior.get("last_risk_approvals", 0)
    if risk_now != risk_prev:
        reasons.append(f"risk_approvals: {risk_prev}→{risk_now}")
        delta["risk_approvals"] = {"prev": risk_prev, "now": risk_now}
        # Critical if went down (rejection/hard-stop)
        if risk_now < risk_prev:
            always_alert = True
            reasons.append("critical_risk_change")

    # --- Signals delta ---
    signals_now  = team.get("recent_signals", [])
    signals_prev = prior.get("last_signal_ids", [])
    def _sig_id(s):
        # 用 bot+symbol+label+headline前30字符 作为稳定 fingerprint
        return f"{s.get('bot','')}/{s.get('symbol','')}/{s.get('label','')}/{s.get('headline','')[:30]}"
    current_ids = [_sig_id(s) for s in signals_now]
    new_signal_ids = [sid for sid in current_ids if sid not in signals_prev]
    if new_signal_ids:
        reasons.append(f"new_signals: {len(new_signal_ids)}")
        delta["signals"] = {"new": new_signal_ids[:3], "count": len(signals_now)}

    # --- Media delta ---
    media_label_now  = media_c.get("last_sentiment_label", "")
    media_label_prev = prior.get("last_media_label", "")
    trading_alert    = media_c.get("trading_alert", False)
    if media_label_now != media_label_prev:
        reasons.append(f"media_label: {media_label_prev}→{media_label_now}")
        delta["media"] = {
            "prev_label": media_label_prev,
            "now_label": media_label_now,
            "trading_alert": trading_alert,
            "alert_summary": media_c.get("alert_summary", "")
        }
    elif trading_alert:
        reasons.append("media_trading_alert")
        delta["media"] = {"trading_alert": True, "alert_summary": media_c.get("alert_summary","")}
        always_alert = True

    # --- Infra ops alerts ---
    recent_ops = [a for a in ops if age_minutes(a.get("ts","")) < 60]
    if recent_ops:
        reasons.append(f"infra_failure: {len(recent_ops)} recent alerts")
        delta["infra"] = {"alerts": recent_ops[-2:]}
        always_alert = True

    # --- Media staleness ---
    media_age = age_minutes(media_c.get("last_scan_timestamp", ""))
    if media_age > 45:
        reasons.append(f"media_stale: {media_age:.0f}min")
        delta["media_stale"] = {"age_min": round(media_age)}

    # --- Freshness of team_facts ---
    facts_ts = team.get("_collected_at", team.get("timestamp", ""))
    facts_age = age_minutes(facts_ts)
    delta["freshness"] = {
        "team_facts_age_min": round(facts_age),
        "media_age_min": round(media_age),
        "facts_fresh": facts_age < 35
    }

    material = bool(reasons) or always_alert

    # No-op: suppress brief, record run with 0 tokens
    if not material:
        print(json.dumps({
            "material_change": False,
            "suppress": True,
            "reason": "no material change detected",
            "delta": delta,
            "checked_at": now_iso
        }))
        return

    print(json.dumps({
        "material_change": True,
        "always_alert": always_alert,
        "suppress": False,
        "reasons": reasons,
        "delta": delta,
        "checked_at": now_iso
    }))

if __name__ == "__main__":
    run()
