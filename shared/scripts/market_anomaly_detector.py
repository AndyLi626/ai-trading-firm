#!/usr/bin/env python3
"""
market_anomaly_detector.py — 确定性异动检测，无 LLM。
读 market_pulse 数据 → 比对阈值 → 写 anomaly_events.json → 调 emergency_trigger
"""
import sys, os, json, uuid, subprocess, time
from datetime import datetime, timezone, timedelta
import os

WS       = os.path.expanduser("~/.openclaw/workspace")
FACTS    = "/tmp/oc_facts"
os.makedirs(FACTS, exist_ok=True)

WATCHLIST_FILE  = os.path.join(WS, "shared/config/watchlist.json")
PULSE_FILE      = os.path.join(FACTS, "MARKET_PULSE.json")
EVENTS_FILE     = os.path.join(FACTS, "anomaly_events.json")
DEDUP_FILE      = os.path.join(FACTS, "anomaly_dedup.json")
TRIGGER_SCRIPT  = os.path.join(WS, "shared/scripts/emergency_trigger.py")

now_utc = datetime.now(timezone.utc)


def load_json(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def save_json(path, data):
    json.dump(data, open(path, "w"), indent=2)


def is_market_open(cfg):
    t = now_utc.strftime("%H:%M")
    return cfg["market_hours_utc"]["open"] <= t <= cfg["market_hours_utc"]["close"]


def symbol_type(sym, cfg):
    if sym in cfg.get("crypto", []) or sym.endswith("-USD"):
        return "crypto"
    return "stock_etf"


def get_thresholds(sym, cfg, spy_cascade=False):
    t = cfg["thresholds"]
    stype = symbol_type(sym, cfg)
    base = t[stype]
    factor = t["spy_qqq_cascade_factor"] if spy_cascade else 1.0
    return base["pct_5m"] * factor, base["pct_15m"] * factor


def check_dedup(sym, dedup, dedup_min):
    """Returns True if symbol is still within dedup window."""
    last = dedup.get(sym)
    if not last:
        return False
    last_dt = datetime.fromisoformat(last)
    return (now_utc - last_dt).total_seconds() < dedup_min * 60


def check_hourly_cap(events_today, cap):
    cutoff = now_utc - timedelta(hours=1)
    recent = [e for e in events_today
              if datetime.fromisoformat(e["detected_at"]) > cutoff]
    return len(recent) >= cap, len(recent)


def detect_spy_cascade(pulse, cfg):
    """SPY or QQQ moving >1% triggers cascade (lower individual thresholds)."""
    for anchor in ["SPY", "QQQ"]:
        q = pulse.get("quotes", {}).get(anchor, {})
        if abs(q.get("pct_change_day", 0) or 0) >= 1.0:
            return True
    return False


def main():
    cfg   = load_json(WATCHLIST_FILE, {})
    pulse = load_json(PULSE_FILE, {})
    dedup = load_json(DEDUP_FILE, {})

    # Load existing today's events
    all_events = load_json(EVENTS_FILE, [])
    today_str  = now_utc.strftime("%Y-%m-%d")
    events_today = [e for e in all_events if e.get("detected_at", "").startswith(today_str)]

    thresholds = cfg.get("thresholds", {})
    dedup_min  = thresholds.get("dedup_minutes", 10)
    hourly_cap = thresholds.get("hourly_cap", 20)

    if not pulse.get("realtime_data"):
        print(json.dumps({"status": "no_data", "reason": "realtime_data=false"}))
        return

    spy_cascade = detect_spy_cascade(pulse, cfg)
    quotes      = pulse.get("quotes", {})

    all_symbols = (cfg.get("crypto", []) + cfg.get("us_proxy", []) +
                   cfg.get("stocks", []) + cfg.get("commodities_etf", []) +
                   cfg.get("volatility", []))

    new_events = []

    for sym in all_symbols:
        q = quotes.get(sym)
        if not q:
            continue

        # Skip US stocks outside market hours (crypto always runs)
        if symbol_type(sym, cfg) == "stock_etf" and not is_market_open(cfg):
            continue

        pct_day = abs(q.get("pct_change_day") or 0)
        thr_5m, thr_15m = get_thresholds(sym, cfg, spy_cascade)

        # Trigger on day pct (5m data would need intraday bars, use day as proxy)
        triggered = pct_day >= thr_5m
        if not triggered:
            continue

        # Dedup check
        if check_dedup(sym, dedup, dedup_min):
            continue

        # Hourly cap check
        capped, recent_count = check_hourly_cap(events_today + new_events, hourly_cap)
        if capped:
            print(json.dumps({"status": "hourly_cap_reached",
                              "cap": hourly_cap, "recent": recent_count}))
            # Write audit
            alerts = load_json(f"{FACTS}/ops_alerts.json", [])
            alerts.append({"type": "anomaly_hourly_cap", "ts": now_utc.isoformat(),
                           "recent_count": recent_count})
            save_json(f"{FACTS}/ops_alerts.json", alerts)
            break

        event = {
            "event_id":    str(uuid.uuid4()),
            "symbol":      sym,
            "pct_change_day": round(pct_day, 4),
            "last_price":  q.get("last_price"),
            "trigger_reason": f"pct_day={pct_day:.2f}% >= thr={thr_5m:.2f}%"
                               + (" [spy_cascade]" if spy_cascade else ""),
            "chain_id":    str(uuid.uuid4()),
            "trigger":     "price_move",
            "detected_at": now_utc.isoformat(),
        }
        new_events.append(event)
        dedup[sym] = now_utc.isoformat()

    # Write dedup state
    save_json(DEDUP_FILE, dedup)

    # Append new events
    all_events.extend(new_events)
    save_json(EVENTS_FILE, all_events)

    # Write today's summary to autonomy dir
    auto_dir = os.path.join(WS, "memory/autonomy", today_str)
    os.makedirs(auto_dir, exist_ok=True)
    save_json(os.path.join(auto_dir, "anomaly_events.json"), {
        "date": today_str,
        "generated_at": now_utc.isoformat(),
        "spy_cascade_active": spy_cascade,
        "new_events_this_run": len(new_events),
        "events_today": len(events_today) + len(new_events),
        "events": [e for e in all_events if e.get("detected_at","").startswith(today_str)]
    })

    # Trigger emergency scan for new events
    triggered_symbols = []
    for ev in new_events:
        try:
            result = subprocess.run(
                [sys.executable, TRIGGER_SCRIPT, ev["symbol"],
                 "--reason", ev["trigger_reason"]],
                capture_output=True, text=True, timeout=10
            )
            r = json.loads(result.stdout.strip())
            if r.get("accepted"):
                triggered_symbols.append(ev["symbol"])
        except Exception as e:
            pass  # degrade silently

    summary = {
        "status": "ok",
        "new_events": len(new_events),
        "triggered_scans": triggered_symbols,
        "spy_cascade": spy_cascade,
        "events_today": len(events_today) + len(new_events),
        "ts": now_utc.isoformat()
    }

try:
    import sys as _sys; _sys.path.insert(0, os.path.join(os.path.expanduser('~/.openclaw/workspace'), 'shared/tools'))
    from run_registry import registry_set as _rs
    _rs('anomaly_detector', 'ok', f"events={summary.get('events_triggered',0)}")
except Exception:
    pass
print(json.dumps(summary))


if __name__ == "__main__":
    main()