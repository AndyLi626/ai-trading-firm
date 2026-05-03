#!/usr/bin/env python3
"""
harvest_openclaw_usage.py — Read cron/runs/*.jsonl and write LLM usage to GCP token_usage_runs.

Usage:
  python3 harvest_openclaw_usage.py           # harvest since last run
  python3 harvest_openclaw_usage.py --full    # re-harvest everything (dedup by run_id)
  python3 harvest_openclaw_usage.py --dry-run # print what would be written
  python3 harvest_openclaw_usage.py --hours 2 # limit to last N hours

Output JSON: {"harvested": N, "skipped_dupes": N, "llm_runs": N, "script_runs": N, "errors": N}
"""
import os, sys, json, uuid, argparse, glob, time
from datetime import datetime, timezone

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
RUNS_DIR = os.path.expanduser('~/.openclaw/cron/runs')
JOBS_FILE = os.path.expanduser('~/.openclaw/cron/jobs.json')
STATE_FILE = "/tmp/oc_facts/harvest_state.json"
FALLBACK_LOG = "/tmp/oc_facts/harvest_fallback.jsonl"

sys.path.insert(0, os.path.join(WORKSPACE, "shared", "tools"))
os.makedirs("/tmp/oc_facts", exist_ok=True)

# ── Task type mapping (job name → task_type) ──────────────────────────────────
TASK_TYPE_MAP = {
    "strategy-scan":        "market_scan",
    "manager-30min-report": "manager_report",
    "media-intel-scan":     "media_scan",
    "infra-5min-report":    "infra_audit",
    "audit-daily":          "audit_report",
}

# ── Load jobs config ───────────────────────────────────────────────────────────
def _load_jobs() -> dict:
    """Returns {jobId: {"bot": agentId, "task_type": ..., "name": ...}}"""
    mapping = {}
    try:
        with open(JOBS_FILE) as f:
            jobs = json.load(f).get("jobs", [])
        for j in jobs:
            jid  = j.get("id", "")
            name = j.get("name", "")
            mapping[jid] = {
                "bot":       j.get("agentId", "unknown"),
                "task_type": TASK_TYPE_MAP.get(name, name.replace("-", "_")),
                "name":      name,
            }
    except Exception as e:
        print(f"[harvest] WARNING: could not load jobs.json: {e}", file=sys.stderr)
    return mapping

# ── State persistence ──────────────────────────────────────────────────────────
def _load_state() -> dict:
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE) as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _save_state(state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        print(f"[harvest] WARNING: could not save state: {e}", file=sys.stderr)

# ── GCP helpers ────────────────────────────────────────────────────────────────
_gcp = None
_GCP_OK = False

def _init_gcp():
    global _gcp, _GCP_OK
    try:
        import gcp_client
        _gcp = gcp_client
        _GCP_OK = True
    except Exception as e:
        print(f"[harvest] GCP unavailable ({e}), will use fallback", file=sys.stderr)

def _existing_run_ids(run_ids: list) -> set:
    """Query GCP for already-harvested run_ids."""
    if not _GCP_OK or not run_ids:
        return set()
    try:
        ids_str = ", ".join(f"'{rid}'" for rid in run_ids)
        sql = f"""
            SELECT run_id FROM `example-gcp-project.trading_firm.token_usage_runs`
            WHERE run_id IN ({ids_str})
        """
        rows = _gcp.query(sql)
        return {r.get("run_id") for r in rows if r.get("run_id")}
    except Exception as e:
        print(f"[harvest] WARNING: dedup query failed ({e})", file=sys.stderr)
        return set()

def _insert_rows(rows: list, dry_run: bool):
    if dry_run:
        for r in rows:
            print(f"  [DRY-RUN] {json.dumps(r)}")
        return
    if _GCP_OK:
        try:
            resp = _gcp.insert_rows("token_usage_runs", rows)
            errs = resp.get("insertErrors", [])
            if errs:
                print(f"[harvest] GCP insertErrors: {errs}", file=sys.stderr)
                _write_fallback(rows)
        except Exception as e:
            print(f"[harvest] GCP insert failed ({e}), using fallback", file=sys.stderr)
            _write_fallback(rows)
    else:
        _write_fallback(rows)

def _write_fallback(rows: list):
    try:
        with open(FALLBACK_LOG, "a") as f:
            for r in rows:
                f.write(json.dumps({"table": "token_usage_runs", "row": r}) + "\n")
    except Exception as e:
        print(f"[harvest] fallback write failed: {e}", file=sys.stderr)

# ── Parse a single JSONL event ─────────────────────────────────────────────────
def _parse_event(line: str, jobs: dict) -> dict | None:
    """Parse one jsonl line. Returns row dict or None if should skip."""
    try:
        ev = json.loads(line.strip())
    except Exception:
        return None

    if ev.get("action") != "finished":
        return None

    ts_ms     = ev.get("ts", 0)
    job_id    = ev.get("jobId", "")
    session_id = ev.get("sessionId") or str(uuid.uuid4())
    status    = ev.get("status", "ok")
    summary   = ev.get("summary", "")
    usage     = ev.get("usage") or {}
    model     = ev.get("model", "")
    duration_ms = ev.get("durationMs", 0)

    job_info  = jobs.get(job_id, {"bot": "unknown", "task_type": "unknown", "name": job_id})
    bot       = job_info["bot"]
    task_type = job_info["task_type"]

    # Classification
    total_tokens  = int(usage.get("total_tokens", 0) or 0)
    input_tokens  = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)

    is_llm = total_tokens > 0
    usage_source = "exact" if is_llm else "estimated"
    llm_calls    = 1 if is_llm else 0

    # is_test detection
    is_test = (
        "TEST" in session_id or
        "TEST-" in summary or
        "test" in session_id.lower()
    )

    # Date from ts_ms
    try:
        dt   = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        date = dt.strftime("%Y-%m-%d")
    except Exception:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return {
        "run_id":              session_id,
        "bot":                 bot,
        "task_type":           task_type,
        "llm_calls":           llm_calls,
        "total_input_tokens":  input_tokens,
        "total_output_tokens": output_tokens,
        "total_tokens":        total_tokens,
        "duration_sec":        round(duration_ms / 1000, 3),
        "status":              status,
        "date":                date,
        "usage_source":        usage_source,
        "record_source":       "runtime",
        "is_test":             is_test,
        "_ts_ms":              ts_ms,   # internal, not sent to GCP
        "_job_id":             job_id,  # internal
    }

# ── Main harvest ───────────────────────────────────────────────────────────────
def harvest(full: bool = False, dry_run: bool = False, hours: float = None) -> dict:
    _init_gcp()
    jobs  = _load_jobs()
    state = {} if full else _load_state()

    # Time cutoff
    cutoff_ms = 0
    if hours is not None:
        cutoff_ms = (time.time() - hours * 3600) * 1000
    elif not full:
        # Use earliest last_harvested_ts across all jobs
        if state:
            cutoff_ms = min(state.get(jid, {}).get("last_ts", 0) for jid in state) if state else 0

    all_rows   = []
    events_map = {}  # run_id -> raw event dict (for record_call)
    errors     = 0

    # Collect candidate rows from all jsonl files
    for jsonl_path in glob.glob(os.path.join(RUNS_DIR, "*.jsonl")):
        job_id = os.path.basename(jsonl_path).replace(".jsonl", "")
        job_cutoff = cutoff_ms
        if not full and not hours:
            job_cutoff = state.get(job_id, {}).get("last_ts", 0)

        try:
            with open(jsonl_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = _parse_event(line, jobs)
                    if row is None:
                        continue
                    if row["_ts_ms"] <= job_cutoff and not full:
                        continue
                    all_rows.append(row)
                    try:
                        ev = json.loads(line.strip())
                        ev["runAtMs"] = ev.get("ts", 0)
                        events_map[row["run_id"]] = ev
                    except Exception:
                        pass
        except Exception as e:
            print(f"[harvest] ERROR reading {jsonl_path}: {e}", file=sys.stderr)
            errors += 1

    if not all_rows:
        print("[harvest] No new events to process.")
        result = {"harvested": 0, "skipped_dupes": 0, "llm_runs": 0, "script_runs": 0, "errors": errors}
        print(json.dumps(result))
        return result

    # Dedup: check existing run_ids in GCP
    candidate_ids = [r["run_id"] for r in all_rows]
    existing_ids  = _existing_run_ids(candidate_ids) if not dry_run else set()

    harvested   = 0
    skipped     = 0
    llm_runs    = 0
    script_runs = 0
    new_state   = dict(state)

    batch = []
    for row in all_rows:
        run_id  = row["run_id"]
        job_id  = row["_job_id"]
        ts_ms   = row["_ts_ms"]

        if run_id in existing_ids and not dry_run:
            skipped += 1
            continue

        # Clean internal fields before sending to GCP
        gcp_row = {k: v for k, v in row.items() if not k.startswith("_")}
        batch.append(gcp_row)

        if dry_run:
            print(f"  [DRY-RUN] bot={gcp_row['bot']} task={gcp_row['task_type']} "
                  f"tokens={gcp_row['total_tokens']} date={gcp_row['date']} "
                  f"run_id={run_id[:8]}... llm={gcp_row['llm_calls']==1}")

        harvested += 1
        if gcp_row["llm_calls"] == 1:
            llm_runs += 1
        else:
            script_runs += 1

        # Update state
        prev = new_state.get(job_id, {})
        if ts_ms > prev.get("last_ts", 0):
            new_state[job_id] = {"last_ts": ts_ms}

    # Insert in batches of 50
    if batch and not dry_run:
        for i in range(0, len(batch), 50):
            chunk = batch[i:i+50]
            _insert_rows(chunk, dry_run=False)
            _record_calls_for_batch(chunk, events_map, dry_run=False)

    if not dry_run:
        _save_state(new_state)

    result = {
        "harvested":    harvested,
        "skipped_dupes": skipped,
        "llm_runs":     llm_runs,
        "script_runs":  script_runs,
        "errors":       errors,
    }
    print(json.dumps(result))
    return result


def replay_fallback() -> dict:
    """Read harvest_fallback.jsonl and insert token_usage_runs rows into GCP (dedup by run_id)."""
    _init_gcp()
    import time as _time

    if not os.path.exists(FALLBACK_LOG):
        result = {"replayed": 0, "skipped": 0, "errors": 0}
        print(json.dumps(result))
        return result

    # Load all lines
    rows = []
    errors = 0
    with open(FALLBACK_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("table") == "token_usage_runs":
                    rows.append(obj["row"])
            except Exception:
                errors += 1

    if not rows:
        result = {"replayed": 0, "skipped": 0, "errors": errors}
        print(json.dumps(result))
        return result

    # Dedup: check existing run_ids
    candidate_ids = [r.get("run_id", "") for r in rows]
    existing_ids  = _existing_run_ids(candidate_ids)

    to_insert = [r for r in rows if r.get("run_id") not in existing_ids]
    skipped   = len(rows) - len(to_insert)

    replayed = 0
    if to_insert:
        for i in range(0, len(to_insert), 50):
            chunk = to_insert[i:i+50]
            if _GCP_OK:
                try:
                    resp = _gcp.insert_rows("token_usage_runs", chunk)
                    errs = resp.get("insertErrors", [])
                    if errs:
                        errors += len(errs)
                        print(f"[replay] GCP insertErrors: {errs}", file=sys.stderr)
                    else:
                        replayed += len(chunk)
                except Exception as e:
                    print(f"[replay] insert failed: {e}", file=sys.stderr)
                    errors += len(chunk)
            else:
                print("[replay] GCP unavailable", file=sys.stderr)
                errors += len(chunk)

    # Rename fallback on success
    if errors == 0:
        ts_str = str(int(_time.time()))
        replayed_path = FALLBACK_LOG.replace(".jsonl", f"_replayed_{ts_str}.jsonl")
        os.rename(FALLBACK_LOG, replayed_path)
        print(f"[replay] Renamed fallback to {replayed_path}", file=sys.stderr)

    result = {"replayed": replayed, "skipped": skipped, "errors": errors}
    print(json.dumps(result))
    return result


def _record_calls_for_batch(rows: list, events_map: dict, dry_run: bool):
    """For each LLM run in batch, write a record to token_usage_calls."""
    if dry_run:
        return
    try:
        from token_meter import record_call
    except Exception as e:
        print(f"[harvest] WARNING: could not import token_meter ({e})", file=sys.stderr)
        return

    for row in rows:
        if row.get("total_tokens", 0) <= 0:
            continue
        run_id    = row.get("run_id", "")
        ev        = events_map.get(run_id, {})
        ts_ms     = ev.get("runAtMs") or ev.get("ts", 0)
        duration_ms = ev.get("durationMs", int(row.get("duration_sec", 0) * 1000))
        model     = ev.get("model", "")
        usage     = ev.get("usage") or {}
        usage_source = "exact" if usage else "estimated"
        try:
            from datetime import datetime, timezone
            started_dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            ended_dt   = datetime.fromtimestamp((ts_ms + duration_ms) / 1000, tz=timezone.utc)
            started_iso = started_dt.strftime("%Y-%m-%d %H:%M:%S.%f UTC")
            ended_iso   = ended_dt.strftime("%Y-%m-%d %H:%M:%S.%f UTC")
        except Exception:
            started_iso = ended_iso = ""

        try:
            record_call(
                run_id=run_id,
                bot=row.get("bot", ""),
                channel="cron",
                task_type=row.get("task_type", ""),
                model=model,
                input_tokens=row.get("total_input_tokens", 0),
                output_tokens=row.get("total_output_tokens", 0),
                started_at=started_iso,
                ended_at=ended_iso,
                status=row.get("status", "ok"),
                usage_source=usage_source,
            )
        except Exception as e:
            print(f"[harvest] record_call failed for {run_id}: {e}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full",           action="store_true", help="Re-harvest all (dedup by run_id)")
    parser.add_argument("--dry-run",        action="store_true", help="Print without writing")
    parser.add_argument("--hours",          type=float, default=None, help="Only last N hours")
    parser.add_argument("--replay-fallback",action="store_true", help="Replay harvest_fallback.jsonl into GCP")
    args = parser.parse_args()

    if args.replay_fallback:
        replay_fallback()
    else:
        harvest(full=args.full, dry_run=args.dry_run, hours=args.hours)
