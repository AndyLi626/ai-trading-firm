#!/usr/bin/env python3
"""
token_meter.py — Call-level and run-level token accounting for all bots.
Import this module to record LLM usage, detect no-op runs, and estimate tokens.

Usage:
    from token_meter import record_call, record_run, estimate_tokens, facts_changed
"""
import os, sys, json, time, logging
from datetime import datetime, timezone

# Paths
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WORKSPACE, "tools"))
FACTS_DIR = "/tmp/oc_facts"
FALLBACK_LOG = os.path.join(FACTS_DIR, "token_meter_fallback.jsonl")

os.makedirs(FACTS_DIR, exist_ok=True)

log = logging.getLogger("token_meter")

# ── GCP client (graceful degradation) ─────────────────────────────────────────
try:
    import gcp_client as _gcp
    _GCP_OK = True
except Exception as _e:
    _GCP_OK = False
    log.warning(f"token_meter: GCP unavailable ({_e}), using fallback log")


def _to_gcp(table: str, rows: list):
    """Write rows to GCP; on failure append to fallback JSONL."""
    if _GCP_OK:
        try:
            resp = _gcp.insert_rows(table, rows)
            errs = resp.get("insertErrors", [])
            if errs:
                log.warning(f"token_meter GCP insertErrors on {table}: {errs}")
                _write_fallback(table, rows)
            return resp
        except Exception as e:
            log.warning(f"token_meter GCP write failed ({e}), using fallback")
            _write_fallback(table, rows)
    else:
        _write_fallback(table, rows)
    return {}


def _write_fallback(table: str, rows: list):
    try:
        with open(FALLBACK_LOG, "a") as f:
            for r in rows:
                f.write(json.dumps({"table": table, "row": r}) + "\n")
    except Exception as e:
        log.error(f"token_meter fallback write failed: {e}")


# ── Utilities ──────────────────────────────────────────────────────────────────
def estimate_tokens(text) -> int:
    """~4 chars per token approximation."""
    return max(1, len(str(text)) // 4)


def _ts(dt) -> str:
    """Convert datetime or ISO string to BigQuery TIMESTAMP string."""
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f UTC")
    return str(dt)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f UTC")


# ── Call-level event ───────────────────────────────────────────────────────────
def record_call(
    run_id: str,
    bot: str,
    channel: str,
    task_type: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    started_at,
    ended_at,
    status: str = "ok",
    usage_source: str = "exact",
    error: str = None,
    record_source: str = "runtime",
    is_test: bool = False,
) -> dict:
    """Record a single LLM API call to token_usage_calls."""
    total_tokens = (input_tokens or 0) + (output_tokens or 0)
    # duration_ms from timestamps if possible
    try:
        s = started_at if isinstance(started_at, datetime) else datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        e = ended_at   if isinstance(ended_at,   datetime) else datetime.fromisoformat(str(ended_at).replace("Z", "+00:00"))
        duration_ms = int((e - s).total_seconds() * 1000)
    except Exception:
        duration_ms = 0

    row = {
        "run_id":        run_id,
        "bot":           bot,
        "channel":       channel or "",
        "task_type":     task_type or "",
        "model":         model or "",
        "usage_source":  usage_source,
        "input_tokens":  input_tokens or 0,
        "output_tokens": output_tokens or 0,
        "total_tokens":  total_tokens,
        "started_at":    _ts(started_at),
        "ended_at":      _ts(ended_at),
        "duration_ms":   duration_ms,
        "status":        status,
        "error":         error or "",
        "record_source": record_source,
        "is_test":       is_test,
    }
    return _to_gcp("token_usage_calls", [row])


# ── Run-level rollup ───────────────────────────────────────────────────────────
def record_run(
    run_id: str,
    bot: str,
    task_type: str,
    llm_calls: int,
    total_input: int,
    total_output: int,
    duration_sec: float,
    status: str = "ok",
) -> dict:
    """Record a bot run summary to token_usage_runs."""
    total_tokens = (total_input or 0) + (total_output or 0)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = {
        "run_id":              run_id,
        "bot":                 bot,
        "task_type":           task_type or "",
        "llm_calls":           llm_calls or 0,
        "total_input_tokens":  total_input or 0,
        "total_output_tokens": total_output or 0,
        "total_tokens":        total_tokens,
        "duration_sec":        round(duration_sec or 0, 3),
        "status":              status,
        "date":                today,
    }
    return _to_gcp("token_usage_runs", [row])


# ── Change detection ───────────────────────────────────────────────────────────
def facts_changed(
    old_facts_path: str,
    new_facts_path: str,
    key_fields: list = None,
) -> bool:
    """
    Return True if facts materially changed between two JSON files.
    Compares key numeric/label fields. If key_fields is None, compares full content.
    Returns True (treat as changed) if either file is missing.
    """
    try:
        if not os.path.exists(old_facts_path) or not os.path.exists(new_facts_path):
            return True
        with open(old_facts_path) as f:
            old = json.load(f)
        with open(new_facts_path) as f:
            new = json.load(f)
    except Exception as e:
        log.warning(f"facts_changed: could not load files ({e}), treating as changed")
        return True

    if key_fields:
        for field in key_fields:
            oval = old.get(field)
            nval = new.get(field)
            if oval != nval:
                return True
        return False
    else:
        # Full comparison excluding timestamp-like keys
        skip = {"timestamp", "ts", "updated_at", "collected_at"}
        old_cmp = {k: v for k, v in old.items() if k not in skip}
        new_cmp = {k: v for k, v in new.items() if k not in skip}
        return old_cmp != new_cmp


# ── Self-test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("token_meter import OK")
    print(f"  estimate_tokens('hello world') = {estimate_tokens('hello world')}")
    # facts_changed with temp files
    import tempfile, json as _json
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as a:
        _json.dump({"price": 100}, a); a_path = a.name
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as b:
        _json.dump({"price": 101}, b); b_path = b.name
    print(f"  facts_changed (different): {facts_changed(a_path, b_path)}")
    print(f"  facts_changed (same):      {facts_changed(a_path, a_path)}")
    os.unlink(a_path); os.unlink(b_path)
    print("All checks passed.")
