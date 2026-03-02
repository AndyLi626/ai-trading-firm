#!/usr/bin/env python3
"""
test_token_meter.py — Unit tests for token accounting infrastructure.
No live GCP writes — insert_rows and query are mocked.
"""
import sys, os, json, tempfile, unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Ensure shared/tools is importable
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "tools"))
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "scripts"))
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "knowledge"))

# Patch gcp_client before importing token_meter / budget_guard
_mock_gcp = MagicMock()
_mock_gcp.insert_rows.return_value = {"insertErrors": []}
_mock_gcp.query.return_value = []
sys.modules["gcp_client"] = _mock_gcp


class TestEstimateTokens(unittest.TestCase):
    def setUp(self):
        import token_meter
        self.tm = token_meter

    def test_basic(self):
        self.assertGreater(self.tm.estimate_tokens("hello world"), 0)

    def test_approximation(self):
        # ~4 chars per token
        text = "a" * 400
        self.assertEqual(self.tm.estimate_tokens(text), 100)

    def test_min_one(self):
        self.assertEqual(self.tm.estimate_tokens(""), 1)

    def test_non_string(self):
        self.assertGreater(self.tm.estimate_tokens({"key": "value"}), 0)


class TestRecordCall(unittest.TestCase):
    def setUp(self):
        _mock_gcp.reset_mock()
        _mock_gcp.insert_rows.return_value = {"insertErrors": []}
        import token_meter
        self.tm = token_meter

    def test_writes_correct_fields(self):
        now = datetime.now(timezone.utc)
        self.tm.record_call(
            run_id="run-001", bot="research", channel="webchat",
            task_type="market_analysis", model="claude-sonnet-4-6",
            input_tokens=100, output_tokens=50,
            started_at=now, ended_at=now,
            status="ok", usage_source="exact",
        )
        _mock_gcp.insert_rows.assert_called_once()
        table, rows = _mock_gcp.insert_rows.call_args[0]
        self.assertEqual(table, "token_usage_calls")
        row = rows[0]
        self.assertEqual(row["run_id"], "run-001")
        self.assertEqual(row["bot"], "research")
        self.assertEqual(row["input_tokens"], 100)
        self.assertEqual(row["output_tokens"], 50)
        self.assertEqual(row["total_tokens"], 150)
        self.assertIn("duration_ms", row)

    def test_estimated_source(self):
        now = datetime.now(timezone.utc)
        self.tm.record_call(
            run_id="run-002", bot="media", channel="cron",
            task_type="sentiment", model="gemini-flash",
            input_tokens=200, output_tokens=80,
            started_at=now, ended_at=now,
            usage_source="estimated",
        )
        _, rows = _mock_gcp.insert_rows.call_args[0]
        self.assertEqual(rows[0]["usage_source"], "estimated")


class TestRecordRun(unittest.TestCase):
    def setUp(self):
        _mock_gcp.reset_mock()
        _mock_gcp.insert_rows.return_value = {"insertErrors": []}
        import token_meter
        self.tm = token_meter

    def test_total_tokens_computed(self):
        self.tm.record_run(
            run_id="run-003", bot="risk", task_type="daily_check",
            llm_calls=3, total_input=1000, total_output=400,
            duration_sec=12.5, status="ok",
        )
        _mock_gcp.insert_rows.assert_called_once()
        _, rows = _mock_gcp.insert_rows.call_args[0]
        row = rows[0]
        self.assertEqual(row["total_tokens"], 1400)
        self.assertEqual(row["llm_calls"], 3)
        self.assertIn("date", row)

    def test_no_op_status(self):
        self.tm.record_run(
            run_id="run-004", bot="main", task_type="collect",
            llm_calls=0, total_input=0, total_output=0,
            duration_sec=1.0, status="no_op",
        )
        _, rows = _mock_gcp.insert_rows.call_args[0]
        self.assertEqual(rows[0]["status"], "no_op")
        self.assertEqual(rows[0]["total_tokens"], 0)


class TestFactsChanged(unittest.TestCase):
    def setUp(self):
        import token_meter
        self.tm = token_meter

    def _write(self, data):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(data, f); f.close()
        return f.name

    def test_detects_change(self):
        a = self._write({"price": 100, "label": "Bullish"})
        b = self._write({"price": 105, "label": "Bullish"})
        self.assertTrue(self.tm.facts_changed(a, b))
        os.unlink(a); os.unlink(b)

    def test_no_change(self):
        a = self._write({"price": 100, "label": "Neutral"})
        self.assertFalse(self.tm.facts_changed(a, a))
        os.unlink(a)

    def test_key_fields_no_change(self):
        a = self._write({"price": 100, "volume": 999, "label": "Bullish"})
        b = self._write({"price": 100, "volume": 1000, "label": "Bullish"})
        # volume changed but not in key_fields
        self.assertFalse(self.tm.facts_changed(a, b, key_fields=["price", "label"]))
        os.unlink(a); os.unlink(b)

    def test_missing_file_treated_as_changed(self):
        self.assertTrue(self.tm.facts_changed("/nonexistent/a.json", "/nonexistent/b.json"))


class TestBudgetGuard(unittest.TestCase):
    def setUp(self):
        _mock_gcp.reset_mock()
        _mock_gcp.query.return_value = []
        # Invalidate cache
        cache = "/tmp/oc_facts/budget_state.json"
        if os.path.exists(cache):
            os.unlink(cache)
        import budget_guard
        self.bg = budget_guard

    def test_ok_threshold(self):
        result = self.bg.check_budget("research", 1000)
        self.assertIn("action", result)
        self.assertIn("allowed", result)
        self.assertEqual(result["action"], "ok")

    def test_warn_threshold(self):
        # Patch usage to 72% of 500_000
        with patch.object(self.bg, "_fetch_daily_usage",
                          return_value={"research": int(500_000 * 0.72), "__global__": int(500_000 * 0.72)}):
            result = self.bg.check_budget("research", 1000)
        self.assertEqual(result["action"], "warn")
        self.assertTrue(result["allowed"])

    def test_degrade_threshold(self):
        with patch.object(self.bg, "_fetch_daily_usage",
                          return_value={"research": int(500_000 * 0.87), "__global__": int(500_000 * 0.87)}):
            result = self.bg.check_budget("research", 1000)
        self.assertEqual(result["action"], "degrade")
        self.assertIn("degrade_hints", result)
        self.assertTrue(result["degrade_hints"]["shorten_summary"])

    def test_stop_threshold_low_priority(self):
        with patch.object(self.bg, "_fetch_daily_usage",
                          return_value={"research": int(500_000 * 0.96), "__global__": int(500_000 * 0.96)}):
            result = self.bg.check_budget("research", 1000, task_priority="normal")
        self.assertEqual(result["action"], "stop")
        self.assertFalse(result["allowed"])

    def test_stop_threshold_critical_allowed(self):
        with patch.object(self.bg, "_fetch_daily_usage",
                          return_value={"research": int(500_000 * 0.96), "__global__": int(500_000 * 0.96)}):
            result = self.bg.check_budget("research", 1000, task_priority="critical")
        self.assertEqual(result["action"], "stop")
        self.assertTrue(result["allowed"])

    def test_per_run_hard_cap(self):
        result = self.bg.check_budget("research", 100_000)
        self.assertEqual(result["action"], "stop")
        self.assertFalse(result["allowed"])


class TestDailyUsageReport(unittest.TestCase):
    def test_runs_without_crash(self):
        sys.path.insert(0, os.path.join(WORKSPACE, "shared", "scripts"))
        from daily_usage_report import run_report

        def mock_query(sql):
            if "GROUP BY bot" in sql:
                return [{"bot": "research", "input_tokens": 1000, "output_tokens": 500,
                          "total_tokens": 1500, "run_count": 3}]
            if "GROUP BY task_type" in sql:
                return [{"task_type": "market_analysis", "tokens": 800, "runs": 2}]
            if "no_op" in sql or "minimal" in sql:
                return []
            if "GROUP BY model" in sql:
                return [{"model": "claude-sonnet-4-6", "inp": 1000, "out": 500}]
            return []

        report, summary = run_report(gcp_query_fn=mock_query)
        self.assertIn("date", report)
        self.assertIn("bots", report)
        self.assertIn("global", report)
        self.assertIn("summary", report)
        self.assertGreater(len(summary), 10)
        self.assertIn("research", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
