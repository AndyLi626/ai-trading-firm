#!/usr/bin/env python3
"""
test_autonomy_framework.py — 标准自主 job 框架单元测试 (7 tests)
"""
import sys, os, json, subprocess, unittest
from datetime import datetime, timezone

WS = os.path.expanduser("~/.openclaw/workspace")
CRON_JOBS = os.path.expanduser("~/.openclaw/cron/jobs.json")
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
AUTO_DIR = os.path.join(WS, "memory/autonomy", TODAY)


def run(script, *args):
    cmd = [sys.executable, os.path.join(WS, "shared/scripts", script)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


class TestAutonomyFramework(unittest.TestCase):

    # T1: autonomy_init_day creates 3 files
    def test_1_init_creates_files(self):
        r = run("autonomy_init_day.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        for f in ["AUTONOMY_QUEUE.json", "AUTONOMY_OUTPUTS.md", "AUTONOMY_PROPOSALS.md"]:
            self.assertTrue(os.path.exists(os.path.join(AUTO_DIR, f)), f"{f} not found")

    # T2: AUTONOMY_QUEUE.json is valid JSON with required keys
    def test_2_queue_valid_json(self):
        qf = os.path.join(AUTO_DIR, "AUTONOMY_QUEUE.json")
        self.assertTrue(os.path.exists(qf), "AUTONOMY_QUEUE.json not found")
        d = json.load(open(qf))
        for key in ["date", "status", "queue", "completed", "summary"]:
            self.assertIn(key, d, f"Missing key: {key}")

    # T3: repo_skills_scan produces valid output
    def test_3_repo_skills_scan(self):
        r = run("repo_skills_scan.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = os.path.join(AUTO_DIR, "repo_skills_scan.json")
        self.assertTrue(os.path.exists(out))
        d = json.load(open(out))
        for key in ["installed_skills", "gaps", "unused"]:
            self.assertIn(key, d)

    # T4: infra_scan produces proposals JSON
    def test_4_infra_scan(self):
        r = run("infra_scan.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = os.path.join(AUTO_DIR, "infra_proposals.json")
        self.assertTrue(os.path.exists(out))
        d = json.load(open(out))
        self.assertIn("proposals", d)
        self.assertIn("summary", d)

    # T5: autonomy_orchestrator runs and outputs summary
    def test_5_orchestrator_runs(self):
        r = run("autonomy_orchestrator.py")
        self.assertEqual(r.returncode, 0, r.stderr)
        last_line = r.stdout.strip().split("\n")[-1]
        d = json.loads(last_line)
        self.assertIn("total", d)
        self.assertIn("completed", d)

    # T6: All 3 proposal files have 12 required fields
    def test_6_proposals_12_fields(self):
        required = ["job_name", "owner_bot", "purpose", "trigger", "inputs", "outputs",
                    "delivery", "budget_policy", "governance", "safety", "tests", "acceptance"]
        for name in ["prop-autonomy-orchestrator", "prop-repo-skills-scan", "prop-infra-12h-scan"]:
            fp = os.path.join(WS, "memory/proposals", f"{name}.md")
            self.assertTrue(os.path.exists(fp), f"{name}.md not found")
            text = open(fp).read()
            for field in required:
                self.assertIn(field, text, f"Field '{field}' missing in {name}.md")

    # T7: 3 new cron jobs in jobs.json with delivery.mode=none
    def test_7_cron_jobs_delivery_none(self):
        d = json.load(open(CRON_JOBS))
        names = {j["name"]: j for j in d["jobs"]}
        for jname in ["autonomy-orchestrator", "repo-skills-scan", "infra-12h-scan"]:
            self.assertIn(jname, names, f"Job '{jname}' not in jobs.json")
            mode = names[jname].get("delivery", {}).get("mode")
            self.assertEqual(mode, "none", f"'{jname}' delivery.mode={mode}")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestAutonomyFramework)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"\n{'='*50}")
    print(f"  {passed}/{total} tests passed")
    if passed == total:
        print("  ✅ ALL AUTONOMY FRAMEWORK TESTS PASS")
    else:
        for f in result.failures + result.errors:
            print(f"  ❌ {f[0]}: {str(f[1])[:120]}")
    sys.exit(0 if passed == total else 1)
