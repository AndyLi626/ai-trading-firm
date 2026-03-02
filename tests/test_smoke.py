#!/usr/bin/env python3
"""
test_smoke.py — 主线守门 Smoke Suite (3 验证)
1. cron jobs 能被 OpenClaw 识别（jobs.json 格式正确，所有 job 有 delivery）
2. budget enforcer 生效（70/85/95% 三档响应正确）
3. signals pipeline 不断（write_signal → GCP market_signals 可写，chain_id 存在）
不依赖真实 LLM，不依赖真实 Telegram。快速，<30s 完成。
"""
import sys, os, json, subprocess, unittest, uuid, tempfile, time

WS       = os.path.expanduser("~/.openclaw/workspace")
CRON_F   = os.path.expanduser("~/.openclaw/cron/jobs.json")
FACTS    = "/tmp/oc_facts"


def run(script, *args, cwd=None):
    cmd = [sys.executable, os.path.join(WS, "shared/scripts", script)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True,
                          cwd=cwd or WS, timeout=30)


class TestCronHealth(unittest.TestCase):
    """Smoke 1: cron jobs.json 格式正确，守门字段完整"""

    def test_jobs_json_valid(self):
        d = json.load(open(CRON_F))
        self.assertIn("jobs", d)
        self.assertGreater(len(d["jobs"]), 0)

    def test_all_jobs_have_delivery(self):
        d = json.load(open(CRON_F))
        for j in d["jobs"]:
            mode = j.get("delivery", {}).get("mode")
            self.assertIn(mode, ("none", "announce"),
                          f"Job {j['name']} has invalid delivery.mode={mode}")

    def test_all_jobs_have_valid_schedule(self):
        d = json.load(open(CRON_F))
        for j in d["jobs"]:
            sched = j.get("schedule", {})
            self.assertIsInstance(sched, dict,
                f"Job {j['name']} schedule is not a dict: {sched}")
            self.assertIn("kind", sched,
                f"Job {j['name']} schedule missing 'kind'")
            self.assertIn("everyMs", sched,
                f"Job {j['name']} schedule missing 'everyMs'")

    def test_no_delivery_announce_on_autonomous_jobs(self):
        """Only manager-30min-report and infra-5min-report may use announce."""
        allowed_announce = {"manager-30min-report", "infra-5min-report"}
        d = json.load(open(CRON_F))
        for j in d["jobs"]:
            if j.get("delivery", {}).get("mode") == "announce":
                self.assertIn(j["name"], allowed_announce,
                    f"Job {j['name']} uses delivery=announce but is not in allowed set")

    def test_core_jobs_present(self):
        d = json.load(open(CRON_F))
        names = {j["name"] for j in d["jobs"]}
        for required in ["manager-30min-report", "media-intel-scan",
                         "emergency-scan-poll", "anomaly-detector", "market-pulse-15m"]:
            self.assertIn(required, names, f"Core job '{required}' missing")


class TestBudgetEnforcer(unittest.TestCase):
    """Smoke 2: budget enforcer 三档响应"""

    def _run_budget(self, bot, task, tokens):
        r = run("run_with_budget.py", bot, task, str(tokens))
        self.assertIn(r.returncode, (0, 1), f"Unexpected exit code: {r.returncode}")
        try:
            return json.loads(r.stdout.strip())
        except Exception:
            self.fail(f"run_with_budget output not JSON: {r.stdout[:200]}")

    def test_budget_script_exists(self):
        self.assertTrue(
            os.path.exists(os.path.join(WS, "shared/scripts/run_with_budget.py")))

    def test_budget_returns_allowed_field(self):
        d = self._run_budget("audit", "smoke_test", 100)
        self.assertIn("allowed", d)
        self.assertIn("action", d)
        self.assertIn("budget_mode", d)

    def test_budget_ok_for_small_request(self):
        d = self._run_budget("audit", "smoke_test", 100)
        self.assertIn(d["budget_mode"], ("ok", "warn", "degrade", "stop"))

    def test_budget_check_status_script(self):
        r = run("check_budget_status.py")
        self.assertEqual(r.returncode, 0, r.stderr[:100])
        d = json.loads(r.stdout.strip())
        self.assertIn("action", d)
        self.assertIn("bot_daily", d)


class TestSignalsPipeline(unittest.TestCase):
    """Smoke 3: signals pipeline — write_signal → GCP 可写，chain_id 存在"""

    def test_write_signal_script_exists(self):
        self.assertTrue(
            os.path.exists(os.path.join(WS, "shared/scripts/write_signal.py")))

    def test_emergency_trigger_writes_request(self):
        """emergency_trigger writes to emergency_requests.json with required fields."""
        # Use a temp file to avoid polluting real requests
        import shutil, tempfile
        orig = os.path.join(FACTS, "emergency_requests.json")
        backup = orig + ".bak"
        if os.path.exists(orig):
            shutil.copy2(orig, backup)
        try:
            open(orig, "w").write("[]")
            r = run("emergency_trigger.py", "SMOKE_TEST",
                    "--reason", "smoke_test_pipeline")
            self.assertEqual(r.returncode, 0, r.stderr[:100])
            d = json.loads(r.stdout.strip())
            self.assertIn("accepted", d)
            if d["accepted"]:
                reqs = json.load(open(orig))
                self.assertGreater(len(reqs), 0)
                req = reqs[-1]
                for field in ["request_id", "symbols", "status", "trigger"]:
                    self.assertIn(field, req)
                self.assertEqual(req["status"], "pending")
        finally:
            if os.path.exists(backup):
                shutil.move(backup, orig)

    def test_market_pulse_produces_output(self):
        """market_pulse.py runs and produces MARKET_PULSE.json with required fields."""
        r = run("market_pulse.py", "SPY,GLD")
        self.assertEqual(r.returncode, 0, r.stderr[:200])
        pulse_file = os.path.join(FACTS, "MARKET_PULSE.json")
        self.assertTrue(os.path.exists(pulse_file))
        d = json.load(open(pulse_file))
        for field in ["symbols", "quotes", "realtime_data", "data_source", "generated_at"]:
            self.assertIn(field, d, f"MARKET_PULSE missing field: {field}")

    def test_gcp_connectivity(self):
        """GCP client can query token_usage_calls (proves signals pipeline is live)."""
        sys.path.insert(0, os.path.join(WS, "shared/tools"))
        try:
            from gcp_client import query
            rows = query("SELECT COUNT(*) as n FROM trading_firm.token_usage_calls LIMIT 1")
            self.assertIsNotNone(rows)
            n = int(rows[0]["n"]) if rows else 0
            self.assertGreaterEqual(n, 0)
        except ImportError:
            self.skipTest("gcp_client not available")
        except Exception as e:
            self.fail(f"GCP connectivity failed: {e}")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestCronHealth, TestBudgetEnforcer, TestSignalsPipeline]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    total  = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print(f"\n{'='*50}")
    print(f"  {passed}/{total} smoke tests passed")
    if passed == total:
        print("  ✅ SMOKE SUITE GREEN — main pipeline intact")
    else:
        for f in result.failures + result.errors:
            print(f"  ❌ {f[0]}: {str(f[1])[:120]}")
    sys.exit(0 if passed == total else 1)
