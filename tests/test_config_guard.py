#!/usr/bin/env python3
"""
test_config_guard.py — Unit tests for config_guard.py
All tests use temp files — NEVER touches ~/.openclaw/openclaw.json
"""
import json, os, sys, shutil, tempfile, unittest
from pathlib import Path

# Import config_guard from shared/tools/
sys.path.insert(0, str(Path(__file__).parent.parent / "shared/tools"))
import config_guard

SAMPLE_CONFIG = {
    "agents": {
        "list": {
            "manager": {"model": {"primary": "claude-sonnet-4-6"}, "identity": {"name": "ManagerBot", "emoji": "🧠"}},
            "infra":   {"model": {"primary": "claude-sonnet-4-6"}, "identity": {"name": "InfraBot",   "emoji": "🏗️"}},
        },
        "defaults": {"timeoutSeconds": 30, "contextTokens": 8000}
    },
    "cron": {
        "heartbeat": {"schedule": "*/30 * * * *", "prompt": "check things"}
    }
}


class TestConfigGuard(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.proposals_dir = Path(self.tmpdir) / "proposals"
        for sub in ("pending", "reviewed", "applied"):
            (self.proposals_dir / sub).mkdir(parents=True)
        self.backup_dir = Path(self.tmpdir) / "backups"
        self.backup_dir.mkdir()
        self.tmp_config = Path(self.tmpdir) / "openclaw.json"
        self.tmp_config.write_text(json.dumps(SAMPLE_CONFIG, indent=2))

        # Patch module-level paths
        config_guard.PROPOSALS_DIR = self.proposals_dir
        config_guard.BACKUPS_DIR = self.backup_dir
        config_guard.LIVE_CONFIG = self.tmp_config
        config_guard.CHANGE_LOG = Path(self.tmpdir) / "CHANGE_LOG.md"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    # ── Propose ──────────────────────────────────────────────────────────────

    def test_propose_valid_path(self):
        """Valid allowlisted path → proposal written to pending/"""
        rc = config_guard.cmd_propose("manager", '{"agents.list[manager].model.primary":"gpt-4o"}')
        self.assertEqual(rc, 0)
        pending = list((self.proposals_dir / "pending").glob("*.json"))
        self.assertEqual(len(pending), 1)
        prop = json.loads(pending[0].read_text())
        self.assertEqual(prop["status"], "pending")
        self.assertEqual(prop["patch"]["agents.list[manager].model.primary"], "gpt-4o")

    def test_propose_invalid_path_agentToAgent(self):
        """Path containing agentToAgent → REJECTED"""
        rc = config_guard.cmd_propose("manager", '{"agentToAgent.enabled":true}')
        self.assertEqual(rc, 1)
        pending = list((self.proposals_dir / "pending").glob("*.json"))
        self.assertEqual(len(pending), 0)

    def test_propose_unknown_schema_field(self):
        """Arbitrary unknown path → REJECTED"""
        rc = config_guard.cmd_propose("manager", '{"some.random.field":"value"}')
        self.assertEqual(rc, 1)
        pending = list((self.proposals_dir / "pending").glob("*.json"))
        self.assertEqual(len(pending), 0)

    def test_propose_media_bot_rejected(self):
        """media bot has no write access → REJECTED regardless of path"""
        rc = config_guard.cmd_propose("media", '{"agents.list[manager].model.primary":"gpt-4"}')
        self.assertEqual(rc, 1)
        pending = list((self.proposals_dir / "pending").glob("*.json"))
        self.assertEqual(len(pending), 0)

    def test_propose_tools_allow_rejected(self):
        """tools.allow changes → REJECTED"""
        rc = config_guard.cmd_propose("infra", '{"tools.allow":["*"]}')
        self.assertEqual(rc, 1)

    def test_propose_bracket_format_required(self):
        """agents.list[media].model.primary bracket notation required"""
        # Dot notation without brackets is not in allowlist
        rc = config_guard.cmd_propose("media", '{"agents.list.media.model.primary":"gpt-4"}')
        self.assertEqual(rc, 1)

    # ── Review ───────────────────────────────────────────────────────────────

    def _make_pending(self, bot_id: str, patch: dict) -> Path:
        proposal = {"bot_id": bot_id, "patch": patch,
                    "submitted_at": config_guard.ts(), "status": "pending"}
        p = self.proposals_dir / "pending" / f"test_{bot_id}.json"
        p.write_text(json.dumps(proposal, indent=2))
        return p

    def test_review_valid_proposal_approved(self):
        p = self._make_pending("manager", {"agents.list[manager].model.primary": "gpt-4o"})
        rc = config_guard.cmd_review(str(p))
        self.assertEqual(rc, 0)
        reviewed = list((self.proposals_dir / "reviewed").glob("*.json"))
        self.assertEqual(len(reviewed), 1)
        prop = json.loads(reviewed[0].read_text())
        self.assertEqual(prop["status"], "approved")

    def test_review_invalid_proposal_rejected(self):
        p = self._make_pending("manager", {"agentToAgent.enabled": True})
        rc = config_guard.cmd_review(str(p))
        self.assertEqual(rc, 1)
        reviewed = list((self.proposals_dir / "reviewed").glob("*.json"))
        self.assertEqual(len(reviewed), 1)
        prop = json.loads(reviewed[0].read_text())
        self.assertEqual(prop["status"], "rejected")

    # ── Apply ────────────────────────────────────────────────────────────────

    def _make_approved(self, bot_id: str, patch: dict) -> Path:
        proposal = {"bot_id": bot_id, "patch": patch,
                    "submitted_at": config_guard.ts(), "status": "approved",
                    "reviewed_at": config_guard.ts(), "review_note": "OK"}
        p = self.proposals_dir / "reviewed" / f"test_{bot_id}.json"
        p.write_text(json.dumps(proposal, indent=2))
        return p

    def _make_pending_unreviewed(self, bot_id: str, patch: dict) -> Path:
        proposal = {"bot_id": bot_id, "patch": patch,
                    "submitted_at": config_guard.ts(), "status": "pending"}
        p = self.proposals_dir / "reviewed" / f"test_unreviewed_{bot_id}.json"
        p.write_text(json.dumps(proposal, indent=2))
        return p

    def test_apply_without_approval_rejected(self):
        """Pending (not approved) proposal → REJECTED on apply"""
        p = self._make_pending_unreviewed("infra", {"agents.list[infra].model.primary": "gpt-4"})
        rc = config_guard.cmd_apply(str(p), config_path=self.tmp_config, dry_run=True)
        self.assertEqual(rc, 1)
        # Config untouched
        cfg = json.loads(self.tmp_config.read_text())
        self.assertEqual(cfg["agents"]["list"]["infra"]["model"]["primary"], "claude-sonnet-4-6")

    def test_apply_approved_creates_backup_and_patches(self):
        """Approved proposal → backup created, patch applied"""
        p = self._make_approved("infra", {"agents.list[infra].model.primary": "gpt-4o-mini"})
        rc = config_guard.cmd_apply(str(p), config_path=self.tmp_config, dry_run=True)
        self.assertEqual(rc, 0)
        # Backup exists
        backups = list(self.backup_dir.glob("*.json"))
        self.assertEqual(len(backups), 1)
        # Patch applied
        cfg = json.loads(self.tmp_config.read_text())
        self.assertEqual(cfg["agents"]["list"]["infra"]["model"]["primary"], "gpt-4o-mini")
        # Moved to applied
        applied = list((self.proposals_dir / "applied").glob("*.json"))
        self.assertEqual(len(applied), 1)

    def test_apply_restores_backup_on_validation_failure(self):
        """Simulate validation failure → backup restored"""
        original_content = self.tmp_config.read_text()
        p = self._make_approved("infra", {"agents.list[infra].model.primary": "bad-model"})

        # Monkey-patch gateway check to fail
        original_run = config_guard.subprocess.run
        def fake_run(*args, **kwargs):
            class R: returncode = 1
            return R()
        config_guard.subprocess.run = fake_run

        try:
            rc = config_guard.cmd_apply(str(p), config_path=self.tmp_config, dry_run=False)
        finally:
            config_guard.subprocess.run = original_run

        self.assertEqual(rc, 1)
        # Backup restored — config matches original
        self.assertEqual(self.tmp_config.read_text(), original_content)

    def test_live_config_untouched(self):
        """Live ~/.openclaw/openclaw.json must NOT be touched by any test"""
        live = Path.home() / ".openclaw/openclaw.json"
        if live.exists():
            before = live.stat().st_mtime
            # run a full propose→review→apply cycle on temp config
            p = self._make_approved("infra", {"agents.defaults.timeoutSeconds": 60})
            config_guard.cmd_apply(str(p), config_path=self.tmp_config, dry_run=True)
            after = live.stat().st_mtime
            self.assertEqual(before, after, "Live openclaw.json was touched!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
