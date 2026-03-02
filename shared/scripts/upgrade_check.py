#!/usr/bin/env python3
"""
upgrade_check.py — Weekly OpenClaw version check (Phase 6 automation)
Creates proposal file when new version found → Manual upgrade after Boss approval

Run: python3 upgrade_check.py
"""
import subprocess, json, os, re
from datetime import datetime, timezone
from pathlib import Path

WS      = Path(os.path.expanduser("~/.openclaw/workspace"))
now_utc = datetime.now(timezone.utc)


def get_installed_version() -> str:
    r = subprocess.run(["openclaw", "--version"], capture_output=True, text=True)
    return r.stdout.strip()


def get_latest_npm_version() -> str:
    r = subprocess.run(
        ["npm", "view", "openclaw", "version"],
        capture_output=True, text=True, timeout=15
    )
    return r.stdout.strip()


def get_gateway_version() -> str:
    r = subprocess.run(
        ["systemctl", "--user", "show", "openclaw-gateway.service",
         "--property=Description"],
        capture_output=True, text=True
    )
    m = re.search(r"v([\d.]+)", r.stdout)
    return m.group(1) if m else "unknown"


def main():
    current  = get_installed_version()
    gateway  = get_gateway_version()
    latest   = get_latest_npm_version()

    consistent = (current == gateway)
    needs_upgrade = (latest != current)

    result = {
        "checked_at":      now_utc.isoformat(),
        "current_cli":     current,
        "current_gateway": gateway,
        "latest_npm":      latest,
        "versions_consistent": consistent,
        "upgrade_available":   needs_upgrade,
    }

    print(json.dumps(result, indent=2))

    if needs_upgrade:
 # proposal
        prop_dir = WS / "memory" / "proposals"
        prop_dir.mkdir(parents=True, exist_ok=True)
        prop_file = prop_dir / f"upgrade_{latest}_{now_utc.strftime('%Y%m%d')}.md"
        prop_file.write_text(
            f"# Upgrade Proposal: openclaw {current} → {latest}\n\n"
            f"**create**: {now_utc.strftime('%Y-%m-%d %H:%M')} UTC\n"
            f"**status**: PENDING_BOSS_APPROVAL\n\n"
            f"# #  result\n"
            f"- current_cli: {current}\n"
            f"- current_gateway: {gateway}\n"
            f"- latest_npm: {latest}\n"
            f"- versions_consistent: {consistent}\n\n"
            f"## Next steps\n"
            f"Boss approval  ADR-008 Phase 1→5  Run\n\n"
            f"## Preflight commands\n"
            f"```bash\n"
            f"python3 shared/scripts/e2e_smoke.py --dry-run\n"
            f"python3 shared/scripts/arch_lock.py check\n"
            f"```\n"
        )
        print(f"\n📋 Proposal: {prop_file}")

    if not consistent:
        print(f"\n⚠️  Version mismatch: CLI={current} Gateway={gateway}")


if __name__ == "__main__":
    main()