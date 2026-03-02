#!/usr/bin/env python3
"""
data_gate.py — Data Provenance Gate
Usage: python3 data_gate.py [--max-age-seconds N]
Exit 0: gate PASS (prints JSON with run_id, as_of, source, age_seconds)
Exit 1: gate FAIL (prints DATA_UNVERIFIED JSON with reason)
"""
import sys, os, json, argparse
from datetime import datetime, timezone

ARTIFACT_PATH = "/tmp/oc_facts/MARKET_PULSE.json"
DEFAULT_MAX_AGE = 300  # 5 minutes


def fail(reason: str, detail: str = ""):
    out = {"gate": "FAIL", "status": "DATA_UNVERIFIED", "reason": reason}
    if detail:
        out["detail"] = detail
    print(json.dumps(out))
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE)
    args = parser.parse_args()
    max_age = args.max_age_seconds

    # 1. Artifact must exist
    if not os.path.exists(ARTIFACT_PATH):
        fail("artifact_missing", f"No file at {ARTIFACT_PATH}")

    # 2. Load artifact
    try:
        with open(ARTIFACT_PATH) as f:
            data = json.load(f)
    except Exception as e:
        fail("artifact_corrupt", str(e))

    # 3. run_id must exist
    if not data.get("run_id"):
        fail("run_id_missing")

    # 4. source must exist and be non-empty
    if not data.get("source"):
        fail("source_missing")

    # 5. synthetic must be false
    if data.get("synthetic") is True:
        fail("synthetic_data_prohibited")

    # 6. freshness check
    as_of_str = data.get("as_of") or data.get("generated_at")
    if not as_of_str:
        fail("artifact_stale", "No as_of timestamp in artifact")

    try:
        as_of = datetime.fromisoformat(as_of_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age_seconds = (now - as_of).total_seconds()
    except Exception as e:
        fail("artifact_stale", f"Cannot parse as_of: {e}")

    if age_seconds > max_age:
        fail("artifact_stale", f"age={age_seconds:.0f}s > max={max_age}s")

    # All checks passed
    result = {
        "gate": "PASS",
        "run_id": data["run_id"],
        "as_of": as_of_str,
        "source": data["source"],
        "age_seconds": round(age_seconds, 1),
        "symbols": data.get("symbols", []),
        "confidence": data.get("confidence"),
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
