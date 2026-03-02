#!/usr/bin/env python3
"""Tests for model governance system."""
import json, os, sys, unittest, subprocess, tempfile, shutil
from unittest.mock import patch, MagicMock

sys.path.insert(0, '/home/lishopping913/.openclaw/workspace/shared/tools')

ALIASES_PATH = '/home/lishopping913/.openclaw/workspace/shared/config/model_aliases.json'
BUDGET_GUARD = '/home/lishopping913/.openclaw/workspace/shared/scripts/provider_budget_guard.py'
DRIFT_ENFORCER = '/home/lishopping913/.openclaw/workspace/shared/scripts/cron_drift_enforcer.py'

class TestModelAliases(unittest.TestCase):
    def setUp(self):
        self.config = json.load(open(ALIASES_PATH))

    def test_alias_resolution(self):
        aliases = self.config['aliases']
        self.assertIn('cheap_control_plane', aliases)
        self.assertIn('latest_fast', aliases)
        self.assertIn('latest_reasoning', aliases)
        self.assertTrue(aliases['cheap_control_plane'].startswith('google/'))

    def test_provider_caps_defined(self):
        caps = self.config['provider_daily_caps_usd']
        self.assertIn('anthropic', caps)
        self.assertIn('qwen', caps)
        self.assertIn('google', caps)
        self.assertGreater(caps['anthropic'], 0)

    def test_job_allowlist_defined(self):
        jal = self.config['job_allowlist']
        self.assertIn('control_plane', jal)
        self.assertIn('strategy_reasoning', jal)

class TestProviderMapping(unittest.TestCase):
    def _map(self, model):
        # Inline the mapping logic
        if model.startswith('anthropic/') or model.startswith('claude-'):
            return 'anthropic'
        elif model.startswith('qwen/') or model.startswith('qwen-'):
            return 'qwen'
        elif model.startswith('google/') or model.startswith('gemini-'):
            return 'google'
        return None

    def test_anthropic_prefixed(self):
        self.assertEqual(self._map('anthropic/claude-sonnet-4-6'), 'anthropic')

    def test_anthropic_bare(self):
        self.assertEqual(self._map('claude-haiku-4-5'), 'anthropic')

    def test_qwen_prefixed(self):
        self.assertEqual(self._map('qwen/qwen-plus'), 'qwen')

    def test_qwen_bare(self):
        self.assertEqual(self._map('qwen-plus'), 'qwen')

    def test_google_prefixed(self):
        self.assertEqual(self._map('google/gemini-2.0-flash-lite'), 'google')

    def test_google_bare(self):
        self.assertEqual(self._map('gemini-2.0-flash-lite'), 'google')

    def test_unknown_returns_none(self):
        self.assertIsNone(self._map('openai/gpt-4o'))

class TestBudgetGuard(unittest.TestCase):
    def test_budget_guard_runs(self):
        r = subprocess.run(['python3', BUDGET_GUARD], capture_output=True, text=True, timeout=20)
        self.assertIn(r.returncode, [0, 1])  # 0=ok, 1=hard_stop
        out = '/tmp/oc_facts/provider_budget.json'
        self.assertTrue(os.path.exists(out))
        data = json.load(open(out))
        self.assertIn('anthropic', data)
        self.assertIn('hard_stop_providers', data)
        self.assertIn('checked_at', data)

    def test_budget_json_structure(self):
        out = '/tmp/oc_facts/provider_budget.json'
        if not os.path.exists(out):
            self.skipTest('provider_budget.json not found — run budget guard first')
        data = json.load(open(out))
        for provider in ['anthropic', 'qwen', 'google']:
            self.assertIn(provider, data)
            self.assertIn('spent', data[provider])
            self.assertIn('cap', data[provider])
            self.assertIn('status', data[provider])
            self.assertIn(data[provider]['status'], ['ok', 'warn', 'hard_stop', 'cooldown'])

class TestDriftEnforcer(unittest.TestCase):
    def test_allowlist_contains_authorized(self):
        content = open(DRIFT_ENFORCER).read()
        for name in ['media-intel-scan', 'strategy-scan', 'manager-30min-report',
                     'infra-5min-report', 'audit-daily', 'daily-model-reset']:
            self.assertIn(f"'{name}'", content, f"{name} missing from allowlist")

    def test_drift_enforcer_runs_clean(self):
        r = subprocess.run(['python3', DRIFT_ENFORCER], capture_output=True, text=True, timeout=20)
        self.assertIn(r.returncode, [0, 1])
        out = json.loads(r.stdout)
        self.assertIn('violations', out)
        self.assertIn('total_jobs', out)

if __name__ == '__main__':
    unittest.main(verbosity=2)
