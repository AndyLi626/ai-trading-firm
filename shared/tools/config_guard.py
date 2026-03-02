#!/usr/bin/env python3
"""config_guard.py — Guarded config change pipeline. Usage: python3 config_guard.py <propose|review|apply|list> [args]"""
import json, os, re, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
import os

WORKSPACE = Path(os.path.expanduser('~/.openclaw/workspace'))
LIVE_CONFIG = Path.home() / ".openclaw/openclaw.json"
BACKUPS_DIR = Path.home() / ".openclaw/backups"
PROPOSALS_DIR = WORKSPACE / "shared/config_proposals"
CHANGE_LOG = WORKSPACE / "shared/knowledge/CHANGE_LOG.md"

ALLOWLIST_PATTERNS = [
    re.compile(r'^agents\.list\[\w+\]\.model\.primary$'),
    re.compile(r'^agents\.list\[\w+\]\.identity\.name$'),
    re.compile(r'^agents\.list\[\w+\]\.identity\.emoji$'),
    re.compile(r'^agents\.defaults\.timeoutSeconds$'),
    re.compile(r'^agents\.defaults\.contextTokens$'),
    re.compile(r'^cron\[\w+\]\.schedule$'),
]

FORBIDDEN_KEYS = {"agentToAgent", "sessions_send", "tools"}
FORBIDDEN_PREFIXES = ("tools.",)

# Role ACL: bots allowed to propose config changes
PROPOSER_ALLOWLIST = {"manager", "managerbot", "infra", "infrabot", "audit", "auditbot"}
NO_WRITE_BOTS = {"media", "mediabot", "research", "researchbot", "risk", "riskbot"}

def ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def is_allowed_path(path: str) -> bool:
    if any(path.startswith(p) for p in FORBIDDEN_PREFIXES):
        return False
    return any(pat.match(path) for pat in ALLOWLIST_PATTERNS)

def validate_patch(patch: dict) -> tuple[bool, str]:
    for key in patch:
        # Check for forbidden schema keys
        parts = re.split(r'[.\[]', key)
        if any(p.rstrip(']') in FORBIDDEN_KEYS for p in parts):
            return False, f"REJECTED: forbidden schema key in '{key}'"
        if not is_allowed_path(key):
            return False, f"REJECTED: path '{key}' not in allowlist"
    return True, "OK"

def cmd_propose(bot_id: str, patch_json: str) -> int:
    if bot_id.lower() in NO_WRITE_BOTS:
        print(f"REJECTED: bot '{bot_id}' has no write access to config (role=no-write)")
        return 1
    try:
        patch = json.loads(patch_json)
    except json.JSONDecodeError as e:
        print(f"REJECTED: invalid JSON — {e}")
        return 1

    ok, msg = validate_patch(patch)
    if not ok:
        print(msg)
        return 1

    filename = f"{ts()}_{bot_id}.json"
    proposal = {"bot_id": bot_id, "patch": patch, "submitted_at": ts(), "status": "pending"}
    out_path = PROPOSALS_DIR / "pending" / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(proposal, indent=2))
    print(f"PROPOSED: {out_path}")
    return 0

def cmd_review(proposal_file: str) -> int:
    p = Path(proposal_file)
    if not p.exists():
        print(f"ERROR: file not found: {p}")
        return 1

    proposal = json.loads(p.read_text())
    ok, msg = validate_patch(proposal.get("patch", {}))
    status = "approved" if ok else "rejected"
    proposal["status"] = status
    proposal["reviewed_at"] = ts()
    proposal["review_note"] = msg

    dest = PROPOSALS_DIR / "reviewed" / p.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(proposal, indent=2))
    # Move original to reviewed
    if p.parent != dest.parent:
        p.unlink(missing_ok=True)
    print(f"{status.upper()}: {dest}")
    return 0 if ok else 1

def cmd_apply(proposal_file: str, config_path: Path = None, dry_run: bool = False) -> int:
    p = Path(proposal_file)
    if not p.exists():
        print(f"ERROR: file not found: {p}")
        return 1

    proposal = json.loads(p.read_text())

    # Must be in reviewed/approved
    if proposal.get("status") != "approved":
        print(f"REJECTED: proposal status is '{proposal.get('status')}', must be 'approved'")
        return 1

    cfg_path = config_path or LIVE_CONFIG
    if not cfg_path.exists():
        print(f"ERROR: config not found: {cfg_path}")
        return 1

    # Backup
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUPS_DIR / f"openclaw_{ts()}.json"
    shutil.copy2(cfg_path, backup_path)
    print(f"BACKUP: {backup_path}")

    # Apply patch (flat key merge into nested structure)
    config = json.loads(cfg_path.read_text())
    patch = proposal["patch"]
    _apply_flat_patch(config, patch)
    cfg_path.write_text(json.dumps(config, indent=2))

    # Validate — skip only when dry_run=True
    if not dry_run:
        result = subprocess.run(["openclaw", "gateway", "status"], capture_output=True, timeout=15)
        if result.returncode != 0:
            print(f"VALIDATION FAILED: restoring backup")
            shutil.copy2(backup_path, cfg_path)
            _log_change(proposal, "RESTORED", str(backup_path))
            return 1

    # Move to applied
    applied_dest = PROPOSALS_DIR / "applied" / p.name
    applied_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, applied_dest)
    if p.exists():
        p.unlink(missing_ok=True)

    _log_change(proposal, "APPLIED", str(cfg_path))
    print(f"APPLIED: {applied_dest}")
    return 0

def _apply_flat_patch(config: dict, patch: dict):
    """Apply dot-notation flat patch keys into nested dict."""
    for flat_key, value in patch.items():
        # Convert agents.list[bot].model.primary → nested path
        keys = re.split(r'\.|\[(\w+)\]', flat_key)
        keys = [k for k in keys if k]
        obj = config
        for k in keys[:-1]:
            if k not in obj:
                obj[k] = {}
            obj = obj[k]
        obj[keys[-1]] = value

def _log_change(proposal: dict, result: str, detail: str):
    entry = (f"\n## {ts()} | bot={proposal.get('bot_id')} | "
             f"result={result}\n"
             f"- patch: {json.dumps(proposal.get('patch'))}\n"
             f"- detail: {detail}\n")
    CHANGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(CHANGE_LOG, "a") as f:
        f.write(entry)

def cmd_list() -> int:
    pending = list((PROPOSALS_DIR / "pending").glob("*.json"))
    if not pending: print("No pending proposals."); return 0
    for p in sorted(pending):
        prop = json.loads(p.read_text())
        print(f"  {p.name}  bot={prop.get('bot_id')}  submitted={prop.get('submitted_at')}")
    return 0

def main():
    args = sys.argv[1:]
    if not args: print("Usage: config_guard.py <propose|review|apply|list> [args]"); return 1
    action = args[0]
    if action == "propose":
        if len(args) < 3: print("Usage: propose <bot_id> <json_patch>"); return 1
        return cmd_propose(args[1], args[2])
    elif action == "review":
        if len(args) < 2: print("Usage: review <proposal_file>"); return 1
        return cmd_review(args[1])
    elif action == "apply":
        if len(args) < 2: print("Usage: apply <proposal_file>"); return 1
        return cmd_apply(args[1])
    elif action == "list": return cmd_list()
    else: print(f"Unknown action: {action}"); return 1

if __name__ == "__main__":
    sys.exit(main())