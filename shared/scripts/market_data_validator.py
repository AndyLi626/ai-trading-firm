#!/usr/bin/env python3
"""
market_data_validator.py
Deterministic validator for MARKET_PULSE.json.
No LLM. Runs after every market-pulse-15m cycle.
Outputs: memory/data_quality_status.json + memory/data_quality_report.md
"""
import json, os, time, sys
from datetime import datetime, timezone, timedelta

WS          = os.path.expanduser('~/.openclaw/workspace')
MP_PATH     = os.path.join(WS, 'memory/market/MARKET_PULSE.json')
STATUS_PATH = os.path.join(WS, 'memory/data_quality_status.json')
REPORT_PATH = os.path.join(WS, 'memory/data_quality_report.md')

# Thresholds
MAX_AGE_MIN      = 20        # pulse older than this → stale
SPIKE_PCT        = 10.0      # >10% single-bar move → anomaly
REQUIRED_FIELDS  = ['last_price', 'prev_close', 'pct_change_day', 'timestamp', 'data_source']
REQUIRED_TOP     = ['as_of', 'source', 'generated_at', 'quotes']

# Second-source deviation threshold (cross-check)
CROSS_CHECK_PCT  = 1.0       # >1% deviation → incident (non-blocking)


def load_pulse():
    if not os.path.exists(MP_PATH):
        return None, "MARKET_PULSE.json missing"
    try:
        d = json.load(open(MP_PATH))
        return d, None
    except Exception as e:
        return None, f"parse error: {e}"


def check_freshness(mp):
    """Returns (ok, age_min, reason)"""
    file_age = (time.time() - os.path.getmtime(MP_PATH)) / 60
    if file_age > MAX_AGE_MIN:
        return False, round(file_age, 1), f"file age {file_age:.1f}min > {MAX_AGE_MIN}min"
    # also check internal as_of
    as_of_str = mp.get('as_of', mp.get('generated_at', ''))
    if as_of_str:
        try:
            as_of = datetime.fromisoformat(as_of_str.replace('Z','+00:00'))
            data_age = (datetime.now(timezone.utc) - as_of).total_seconds() / 60
            if data_age > MAX_AGE_MIN:
                return False, round(data_age, 1), f"data as_of age {data_age:.1f}min > {MAX_AGE_MIN}min"
        except: pass
    return True, round(file_age, 1), "ok"


def check_completeness(mp):
    """Returns (ok, missing_fields, issues)"""
    issues = []
    missing_top = [f for f in REQUIRED_TOP if f not in mp]
    if missing_top:
        issues.append(f"missing top fields: {missing_top}")

    quotes = mp.get('quotes', [])
    if not quotes:
        issues.append("quotes empty")
        return False, missing_top, issues

    if isinstance(quotes, list):
        quote_list = quotes
    elif isinstance(quotes, dict):
        quote_list = list(quotes.values())
    else:
        issues.append("quotes unexpected type")
        return False, [], issues

    bad_quotes = []
    for q in quote_list:
        if isinstance(q, dict):
            missing = [f for f in REQUIRED_FIELDS if f not in q]
            if missing:
                bad_quotes.append(f"missing {missing}")

    if bad_quotes:
        issues.append(f"incomplete quotes: {bad_quotes[:3]}")

    return len(issues) == 0, missing_top, issues


def check_anomalies(mp):
    """Returns (ok, anomalies)"""
    anomalies = []
    quotes = mp.get('quotes', [])
    if isinstance(quotes, list):
        quote_list = [(f"quote[{i}]", q) for i, q in enumerate(quotes)]
    elif isinstance(quotes, dict):
        quote_list = list(quotes.items())
    else:
        return True, []

    for sym, q in quote_list:
        if not isinstance(q, dict): continue
        pct = q.get('pct_change_day')
        if pct is not None:
            try:
                pct_f = float(pct)
                if abs(pct_f) > SPIKE_PCT:
                    anomalies.append(f"{sym} pct_change_day={pct_f:.2f}% (>{SPIKE_PCT}%)")
            except: pass

    return len(anomalies) == 0, anomalies


def cross_check_prices(mp):
    """
    Lightweight cross-check: compare IEX prices against Alpaca data broker.
    Non-blocking — records deviation as incident note.
    Returns (ok, deviations)
    """
    deviations = []
    # For now: check internal consistency (pct_change_day vs last/prev)
    quotes = mp.get('quotes', [])
    if isinstance(quotes, list):
        items = [(f"q{i}", q) for i, q in enumerate(quotes)]
    elif isinstance(quotes, dict):
        items = list(quotes.items())
    else:
        return True, []

    for sym, q in items:
        if not isinstance(q, dict): continue
        last  = q.get('last_price')
        prev  = q.get('prev_close')
        pct   = q.get('pct_change_day')
        if last and prev and pct is not None:
            try:
                computed = (float(last) - float(prev)) / float(prev) * 100
                reported = float(pct)
                diff = abs(computed - reported)
                if diff > CROSS_CHECK_PCT:
                    deviations.append(f"{sym}: computed={computed:.4f}% reported={reported:.4f}% diff={diff:.4f}%")
            except: pass

    return len(deviations) == 0, deviations


def run():
    now   = datetime.now(timezone.utc)
    now_s = now.isoformat()
    result = {
        "as_of":       now_s,
        "is_verified": False,
        "source":      "unknown",
        "freshness_ok": False,
        "completeness_ok": False,
        "anomalies_ok": True,
        "cross_check_ok": True,
        "age_min":     None,
        "issues":      [],
        "anomalies":   [],
        "deviations":  [],
        "status":      "DATA_UNVERIFIED",
    }

    mp, load_err = load_pulse()
    if mp is None:
        result["issues"].append(load_err)
        _write(result)
        return result

    result["source"] = mp.get('source', 'unknown')
    result["pulse_as_of"] = mp.get('as_of', mp.get('generated_at', ''))

    # 1. Freshness
    fresh_ok, age_min, fresh_reason = check_freshness(mp)
    result["freshness_ok"] = fresh_ok
    result["age_min"]      = age_min
    if not fresh_ok:
        result["issues"].append(f"STALE: {fresh_reason}")

    # 2. Completeness
    comp_ok, _, comp_issues = check_completeness(mp)
    result["completeness_ok"] = comp_ok
    result["issues"].extend(comp_issues)

    # 3. Anomalies
    anom_ok, anomalies = check_anomalies(mp)
    result["anomalies_ok"] = anom_ok
    result["anomalies"]    = anomalies

    # 4. Cross-check (non-blocking)
    cc_ok, deviations = cross_check_prices(mp)
    result["cross_check_ok"] = cc_ok
    result["deviations"]     = deviations

    # Final verdict
    all_ok = fresh_ok and comp_ok
    result["is_verified"] = all_ok
    result["status"]      = "VERIFIED" if all_ok else "DATA_UNVERIFIED"

    _write(result)
    return result


def _write(result):
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, 'w') as f:
        json.dump(result, f, indent=2)

    # Markdown report
    lines = [
        f"# Data Quality Report",
        f"",
        f"**as_of**: {result['as_of'][:19]} UTC  ",
        f"**status**: `{result['status']}`  ",
        f"**source**: {result.get('source','?')}  ",
        f"**pulse_as_of**: {result.get('pulse_as_of','?')[:19]}  ",
        f"",
        f"## Checks",
        f"",
        f"| Check | Result |",
        f"|-------|--------|",
        f"| Freshness (age={result.get('age_min','?')}min, max={MAX_AGE_MIN}min) | {'✅ PASS' if result['freshness_ok'] else '❌ FAIL'} |",
        f"| Completeness | {'✅ PASS' if result['completeness_ok'] else '❌ FAIL'} |",
        "| Anomaly detection (>{}% moves) | {} |".format(SPIKE_PCT, '✅ PASS' if result['anomalies_ok'] else '⚠️  {} anomalies'.format(len(result['anomalies']))),
        "| Cross-check (internal consistency) | {} |".format('✅ PASS' if result['cross_check_ok'] else '⚠️  {} deviations'.format(len(result['deviations']))),
        f"",
    ]
    if result["issues"]:
        lines += ["## Issues", ""]
        for i in result["issues"]: lines.append(f"- {i}")
        lines.append("")
    if result["anomalies"]:
        lines += ["## Anomalies (non-blocking)", ""]
        for a in result["anomalies"]: lines.append(f"- {a}")
        lines.append("")
    if result["deviations"]:
        lines += [f"## Cross-check Deviations (>{CROSS_CHECK_PCT}%, incident logged)", ""]
        for d in result["deviations"]: lines.append(f"- {d}")
        lines.append("")

    with open(REPORT_PATH, 'w') as f:
        f.write('\n'.join(lines))


if __name__ == '__main__':
    r = run()
    print(json.dumps(r, indent=2))
