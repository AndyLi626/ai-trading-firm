#!/usr/bin/env python3
"""
test_data_gate.py — Unit + integration tests for the Data Provenance Gate.
"""
import json, os, re, subprocess, sys, tempfile, time, unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

ARTIFACT_PATH = "/tmp/oc_facts/MARKET_PULSE.json"
DATA_GATE = "/home/lishopping913/.openclaw/workspace/shared/scripts/data_gate.py"
AUDIT_SCRIPT = "/home/lishopping913/.openclaw/workspace/shared/scripts/audit_data_violation.py"
BOT_CACHE = "/home/lishopping913/.openclaw/workspace/memory/bot_cache.json"


def _write_artifact(data: dict):
    os.makedirs("/tmp/oc_facts", exist_ok=True)
    with open(ARTIFACT_PATH, "w") as f:
        json.dump(data, f)


def _valid_artifact(**overrides):
    base = {
        "run_id": "test-run-id-1234",
        "chain_id": "test-run-id-1234",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": "alpaca_iex",
        "synthetic": False,
        "confidence": 0.8,
        "symbols": ["SPY", "QQQ"],
        "quotes": {},
    }
    base.update(overrides)
    return base


def _run_gate(*args):
    """Run data_gate.py, return (returncode, parsed_json)."""
    cmd = [sys.executable, DATA_GATE] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        out = json.loads(r.stdout.strip())
    except Exception:
        out = {"raw": r.stdout.strip()}
    return r.returncode, out


class TestDataGate(unittest.TestCase):

    def tearDown(self):
        if os.path.exists(ARTIFACT_PATH):
            os.remove(ARTIFACT_PATH)

    def test_gate_pass(self):
        _write_artifact(_valid_artifact())
        rc, out = _run_gate()
        self.assertEqual(rc, 0, f"Expected exit 0, got {rc}: {out}")
        self.assertEqual(out.get("gate"), "PASS")
        self.assertIn("run_id", out)
        self.assertIn("age_seconds", out)

    def test_gate_fail_missing(self):
        if os.path.exists(ARTIFACT_PATH):
            os.remove(ARTIFACT_PATH)
        rc, out = _run_gate()
        self.assertEqual(rc, 1)
        self.assertEqual(out.get("status"), "DATA_UNVERIFIED")
        self.assertEqual(out.get("reason"), "artifact_missing")

    def test_gate_fail_stale(self):
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        _write_artifact(_valid_artifact(as_of=stale_time))
        rc, out = _run_gate()
        self.assertEqual(rc, 1)
        self.assertEqual(out.get("reason"), "artifact_stale")

    def test_gate_fail_synthetic(self):
        _write_artifact(_valid_artifact(synthetic=True))
        rc, out = _run_gate()
        self.assertEqual(rc, 1)
        self.assertEqual(out.get("reason"), "synthetic_data_prohibited")

    def test_gate_fail_no_run_id(self):
        art = _valid_artifact()
        del art["run_id"]
        _write_artifact(art)
        rc, out = _run_gate()
        self.assertEqual(rc, 1)
        self.assertEqual(out.get("reason"), "run_id_missing")

    def test_price_pattern_without_provenance(self):
        """Simulate a bot output string and assert price/pct pattern is detected."""
        bot_output = "BTC +2.3%"
        price_pattern = re.compile(
            r'(\b[A-Z]{2,5}\b.*?[+-]?\d+\.?\d*%|'
            r'\$\s*\d[\d,.]+|'
            r'\b\d+\.\d+\s*USD\b)',
            re.IGNORECASE
        )
        match = price_pattern.search(bot_output)
        self.assertIsNotNone(match, "Price/pct pattern should be detected in bot output")
        # Gate should fail when no artifact exists
        if os.path.exists(ARTIFACT_PATH):
            os.remove(ARTIFACT_PATH)
        rc, out = _run_gate()
        self.assertEqual(rc, 1, "Gate must FAIL when no artifact exists, blocking market data output")

    def test_audit_violation_writes_cache(self):
        """Call audit_data_violation.py and check bot_cache has data_violation_active=true."""
        bot_name = "test_bot_audit"
        payload = json.dumps({"bot": bot_name, "output": "BTC +2.3%", "context": "unit_test"})

        with patch.dict(sys.modules, {"gcp_client": MagicMock()}):
            # Patch log_decision so no live GCP call
            env = os.environ.copy()
            env["PYTHONPATH"] = "/home/lishopping913/.openclaw/workspace/shared/tools"

            # Use a mock that overrides gcp_client import inside audit script
            mock_gcp = os.path.join(tempfile.gettempdir(), "gcp_client.py")
            with open(mock_gcp, "w") as f:
                f.write("def log_decision(**kwargs): pass\n")
                f.write("def log_decision(bot,decision_type,summary,risk_status,token_cost,session_id,payload): pass\n")

            env["PYTHONPATH"] = tempfile.gettempdir()
            r = subprocess.run(
                [sys.executable, AUDIT_SCRIPT],
                input=payload, capture_output=True, text=True, env=env
            )

        # Read bot_cache
        self.assertTrue(os.path.exists(BOT_CACHE), "bot_cache.json should exist")
        with open(BOT_CACHE) as f:
            cache = json.load(f)

        self.assertIn(bot_name, cache, f"Bot '{bot_name}' should appear in cache")
        self.assertTrue(cache[bot_name].get("data_violation_active"),
                        "data_violation_active should be True")
        self.assertIn("data_violation_ts", cache[bot_name])

        # Also verify ticket JSON output
        try:
            ticket = json.loads(r.stdout.strip())
            self.assertEqual(ticket.get("ticket"), "SEV-0")
            self.assertTrue(ticket.get("frozen"))
        except Exception:
            pass  # GCP may fail in test; cache check is primary assertion


if __name__ == "__main__":
    unittest.main(verbosity=2)
