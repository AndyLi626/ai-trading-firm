#!/usr/bin/env python3
"""test_archivist.py — Archivist Ledger 6-test suite"""
import sys, os, json, subprocess, unittest

WS = os.path.expanduser("~/.openclaw/workspace")
LEDGER = os.path.join(WS, "ledger")

def run(script, *args, stdin=None):
    cmd = [sys.executable, os.path.join(WS, "shared/scripts", script)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, input=stdin)

class TestArchivist(unittest.TestCase):

    def test_1_snapshot_runs_and_creates_files(self):
        r = run("snapshot_capabilities.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout.strip())
        self.assertEqual(d["status"], "ok")
        self.assertGreater(d["items"], 10)
        for f in ["STATUS_MATRIX.md", "CAPABILITIES.md"]:
            self.assertTrue(os.path.exists(os.path.join(LEDGER, f)), f"Missing {f}")

    def test_2_status_matrix_nonempty(self):
        p = os.path.join(LEDGER, "STATUS_MATRIX.md")
        self.assertTrue(os.path.exists(p))
        content = open(p).read()
        self.assertIn("VERIFIED", content)
        self.assertIn("WIRED", content)
        self.assertIn("| J01 |", content)

    def test_3_preflight_already_done(self):
        r = run("ledger_preflight.py",
                "market_pulse anomaly_detector watchlist dedup rate_limit emergency_trigger")
        self.assertEqual(r.returncode, 0, r.stderr)
        line = [l for l in r.stdout.split("\n") if l.startswith("JSON:")]; d = json.loads(line[-1][5:]) if line else {}
        self.assertEqual(d["verdict"], "ALREADY_DONE")
        self.assertGreater(len(d["verified"]), 0)

    def test_4_preflight_governance_conflict(self):
        r = run("ledger_preflight.py",
                "new job with delivery=announce and sessions_send")
        line = [l for l in r.stdout.split("\n") if l.startswith("JSON:")]; d = json.loads(line[-1][5:]) if line else {}
        self.assertEqual(d["verdict"], "GOVERNANCE_CONFLICT")
        self.assertGreater(len(d["violations"]), 0)

    def test_5_preflight_new_work(self):
        r = run("ledger_preflight.py",
                "build a new blockchain oracle data feed with zkproof validation")
        line = [l for l in r.stdout.split("\n") if l.startswith("JSON:")]; d = json.loads(line[-1][5:]) if line else {}
        self.assertIn(d["verdict"], ["NEW_WORK", "PARTIAL"])

    def test_6_infra_scan_writes_drift_report(self):
        r = run("infra_scan.py")
        self.assertEqual(r.returncode, 0, r.stderr[:200])
        drift = os.path.join(LEDGER, "DRIFT_REPORT.md")
        self.assertTrue(os.path.exists(drift), "DRIFT_REPORT.md not created")
        content = open(drift).read()
        self.assertIn("Drift Report", content)
        self.assertGreater(len(content), 50)

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = loader.loadTestsFromTestCase(TestArchivist)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    total  = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"\n{'='*50}\n  {passed}/{total} tests passed")
    if passed == total: print("  ✅ ALL ARCHIVIST TESTS PASS")
    else:
        for f in result.failures + result.errors:
            print(f"  ❌ {f[0]}: {str(f[1])[:120]}")
    sys.exit(0 if passed == total else 1)
