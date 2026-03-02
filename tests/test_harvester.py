#!/usr/bin/env python3
"""
test_harvester.py — Unit tests for harvest_openclaw_usage.py and check_budget_status.py
No live GCP writes — uses mock insert_rows.
"""
import os, sys, json, tempfile, unittest
from unittest.mock import patch, MagicMock

WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
SCRIPTS_DIR = os.path.join(WORKSPACE, "shared", "scripts")
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "tools"))
sys.path.insert(0, SCRIPTS_DIR)


# ── Mock JSONL data ────────────────────────────────────────────────────────────
LLM_RUN_1 = json.dumps({
    "ts": 1772387239016,
    "jobId": "6d86a43e-69eb-475b-ba44-bd6b1a74b8f5",
    "action": "finished",
    "status": "ok",
    "summary": "Media scan complete.",
    "delivered": False,
    "sessionId": "session-abc-001",
    "runAtMs": 1772387226065,
    "durationMs": 12947,
    "model": "claude-sonnet-4-6",
    "usage": {"input_tokens": 5000, "output_tokens": 800, "total_tokens": 5800},
})

LLM_RUN_2 = json.dumps({
    "ts": 1772388000000,
    "jobId": "97885e6c-e9c3-451c-b57f-1ac269fe0914",
    "action": "finished",
    "status": "ok",
    "summary": "Strategy scan complete.",
    "delivered": False,
    "sessionId": "session-def-002",
    "runAtMs": 1772387900000,
    "durationMs": 100000,
    "model": "claude-sonnet-4-6",
    "usage": {"input_tokens": 19, "output_tokens": 8179, "total_tokens": 23599},
})

SCRIPT_RUN = json.dumps({
    "ts": 1772387300000,
    "jobId": "f2c30e3d-3154-453b-ab2b-f6f521a6a9ce",
    "action": "finished",
    "status": "ok",
    "summary": "HEARTBEAT_OK",
    "delivered": False,
    "sessionId": "session-ghi-003",
    "runAtMs": 1772387295000,
    "durationMs": 5000,
    "model": "claude-sonnet-4-6",
    "usage": {"input_tokens": 4, "output_tokens": 130, "total_tokens": 0},
})

TEST_RUN = json.dumps({
    "ts": 1772387400000,
    "jobId": "6d86a43e-69eb-475b-ba44-bd6b1a74b8f5",
    "action": "finished",
    "status": "ok",
    "summary": "TEST- run complete.",
    "delivered": False,
    "sessionId": "session-TEST-999",
    "runAtMs": 1772387395000,
    "durationMs": 3000,
    "model": "claude-sonnet-4-6",
    "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
})

MOCK_JOBS = {
    "6d86a43e-69eb-475b-ba44-bd6b1a74b8f5": {"bot": "media",    "task_type": "media_scan",    "name": "media-intel-scan"},
    "97885e6c-e9c3-451c-b57f-1ac269fe0914": {"bot": "research",  "task_type": "market_scan",   "name": "strategy-scan"},
    "f2c30e3d-3154-453b-ab2b-f6f521a6a9ce": {"bot": "main",      "task_type": "infra_audit",   "name": "infra-5min-report"},
}


class TestHarvestParseEvent(unittest.TestCase):
    """Test _parse_event logic directly."""

    def setUp(self):
        import harvest_openclaw_usage as h
        self.h = h

    def test_llm_run_classified(self):
        row = self.h._parse_event(LLM_RUN_1, MOCK_JOBS)
        self.assertIsNotNone(row)
        self.assertEqual(row["llm_calls"], 1)
        self.assertEqual(row["usage_source"], "exact")
        self.assertEqual(row["total_tokens"], 5800)
        self.assertEqual(row["bot"], "media")
        self.assertEqual(row["task_type"], "media_scan")

    def test_script_run_classified(self):
        row = self.h._parse_event(SCRIPT_RUN, MOCK_JOBS)
        self.assertIsNotNone(row)
        self.assertEqual(row["llm_calls"], 0)
        self.assertEqual(row["usage_source"], "estimated")
        self.assertEqual(row["total_tokens"], 0)

    def test_is_test_detection(self):
        # session contains TEST
        row_test_session = self.h._parse_event(TEST_RUN, MOCK_JOBS)
        self.assertTrue(row_test_session["is_test"])

        # summary contains TEST-
        ev = json.loads(LLM_RUN_1)
        ev["summary"] = "TEST- something"
        ev["sessionId"] = "normal-session-001"
        row_test_summary = self.h._parse_event(json.dumps(ev), MOCK_JOBS)
        self.assertTrue(row_test_summary["is_test"])

        # Normal run
        row_normal = self.h._parse_event(LLM_RUN_1, MOCK_JOBS)
        self.assertFalse(row_normal["is_test"])

    def test_started_events_skipped(self):
        ev = json.loads(LLM_RUN_1)
        ev["action"] = "started"
        row = self.h._parse_event(json.dumps(ev), MOCK_JOBS)
        self.assertIsNone(row)

    def test_error_events_kept(self):
        ev = json.loads(LLM_RUN_1)
        ev["status"] = "error"
        row = self.h._parse_event(json.dumps(ev), MOCK_JOBS)
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "error")


class TestHarvestFull(unittest.TestCase):
    """End-to-end harvest test with mock GCP."""

    def setUp(self):
        import harvest_openclaw_usage as h
        self.h = h

    def _make_jsonl(self, tmpdir, filename, lines):
        path = os.path.join(tmpdir, filename)
        with open(path, "w") as f:
            for l in lines:
                f.write(l + "\n")
        return path

    def test_harvest_classifies_correctly(self):
        inserted = []

        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, "6d86a43e-69eb-475b-ba44-bd6b1a74b8f5.jsonl",
                             [LLM_RUN_1])
            self._make_jsonl(tmpdir, "97885e6c-e9c3-451c-b57f-1ac269fe0914.jsonl",
                             [LLM_RUN_2])
            self._make_jsonl(tmpdir, "f2c30e3d-3154-453b-ab2b-f6f521a6a9ce.jsonl",
                             [SCRIPT_RUN])

            state_file = os.path.join(tmpdir, "state.json")

            with patch.object(self.h, "RUNS_DIR", tmpdir), \
                 patch.object(self.h, "STATE_FILE", state_file), \
                 patch.object(self.h, "_load_jobs", return_value=MOCK_JOBS), \
                 patch.object(self.h, "_existing_run_ids", return_value=set()), \
                 patch.object(self.h, "_insert_rows", side_effect=lambda rows, dry_run: inserted.extend(rows)):

                result = self.h.harvest(full=True, dry_run=False)

        self.assertEqual(result["llm_runs"], 2)
        self.assertEqual(result["script_runs"], 1)
        self.assertEqual(result["harvested"], 3)
        self.assertEqual(result["skipped_dupes"], 0)

    def test_dedup_skips_existing(self):
        inserted = []
        existing = {"session-abc-001"}  # LLM_RUN_1's sessionId

        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, "6d86a43e-69eb-475b-ba44-bd6b1a74b8f5.jsonl",
                             [LLM_RUN_1, LLM_RUN_2.replace("session-def-002", "session-abc-001")])

            state_file = os.path.join(tmpdir, "state.json")

            with patch.object(self.h, "RUNS_DIR", tmpdir), \
                 patch.object(self.h, "STATE_FILE", state_file), \
                 patch.object(self.h, "_load_jobs", return_value=MOCK_JOBS), \
                 patch.object(self.h, "_existing_run_ids", return_value=existing), \
                 patch.object(self.h, "_insert_rows", side_effect=lambda rows, dry_run: inserted.extend(rows)):

                result = self.h.harvest(full=True, dry_run=False)

        # Both have session-abc-001 → both should be skipped
        self.assertEqual(result["skipped_dupes"], 2)
        self.assertEqual(result["harvested"], 0)

    def test_dry_run_no_inserts(self):
        insert_calls = []

        with tempfile.TemporaryDirectory() as tmpdir:
            self._make_jsonl(tmpdir, "6d86a43e-69eb-475b-ba44-bd6b1a74b8f5.jsonl",
                             [LLM_RUN_1])
            state_file = os.path.join(tmpdir, "state.json")

            with patch.object(self.h, "RUNS_DIR", tmpdir), \
                 patch.object(self.h, "STATE_FILE", state_file), \
                 patch.object(self.h, "_load_jobs", return_value=MOCK_JOBS), \
                 patch.object(self.h, "_existing_run_ids", return_value=set()), \
                 patch.object(self.h, "_write_fallback") as mock_fb, \
                 patch("builtins.print"):

                result = self.h.harvest(full=True, dry_run=True)

            mock_fb.assert_not_called()
        # dry_run: harvested=1 (counted) but no actual writes
        self.assertEqual(result["harvested"], 1)


class TestCheckBudgetStatus(unittest.TestCase):
    """Test check_budget_status.py runs without crash and returns valid JSON."""

    def test_runs_without_crash(self):
        import check_budget_status as cbs

        mock_harvest = {"harvested": 0, "errors": 0}
        mock_usage   = [{"bot": "manager", "total_tokens": 5000, "date": "2026-03-02"}]
        mock_guard   = {"action": "ok", "allowed": True, "reason": "test"}

        with patch.object(cbs, "_run_harvest_quick", return_value=mock_harvest), \
             patch.object(cbs, "_query_today_per_bot", return_value={"manager": 5000}), \
             patch("budget_guard.check_budget", return_value=mock_guard), \
             patch("builtins.print"):

            result = cbs.main()

        self.assertIn("message_level", result)
        self.assertIn("run_level", result)
        self.assertIn("bot_daily", result)
        self.assertIn("global", result)
        self.assertIn("action", result)
        self.assertIn("manager", result["bot_daily"])
        self.assertEqual(result["action"], "ok")
        self.assertIsNotNone(result["global"]["system_today_total"])


if __name__ == "__main__":
    print("=" * 60)
    print("Running harvester tests...")
    print("=" * 60)
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestHarvestParseEvent))
    suite.addTests(loader.loadTestsFromTestCase(TestHarvestFull))
    suite.addTests(loader.loadTestsFromTestCase(TestCheckBudgetStatus))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
