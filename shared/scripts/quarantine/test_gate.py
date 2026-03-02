#!/usr/bin/env python3
"""
test_gate.py — apply 前守门：运行核心测试套件，写 ledger/TEST_GATE.json
exit 0 = 全绿可 apply; exit 1 = 有失败，拒绝 apply
"""
import sys, os, json, subprocess
from datetime import datetime, timezone

WS     = os.path.expanduser("~/.openclaw/workspace")
LEDGER = os.path.join(WS, "ledger")
GATE_F = os.path.join(LEDGER, "TEST_GATE.json")

SUITES = [
    ("test_failure_chains",    "tests/test_failure_chains.py"),
    ("test_config_guard",      "tests/test_config_guard.py"),
    ("test_autonomy_framework","tests/test_autonomy_framework.py"),
    ("test_archivist",         "tests/test_archivist.py"),
    ("test_smoke",             "tests/test_smoke.py"),
]

now_utc = datetime.now(timezone.utc)

def run_suite(name, path):
    r = subprocess.run(
        [sys.executable, os.path.join(WS, path)],
        capture_output=True, text=True, timeout=60, cwd=WS
    )
    # Parse "X/Y tests passed" from output
    passed = total = 0
    for line in r.stdout.splitlines():
        if "passed" in line and "/" in line:
            try:
                parts = line.strip().split("/")
                passed = int(parts[0].split()[-1])
                total  = int(parts[1].split()[0])
            except Exception:
                pass
    # Fallback: exit_code 0 + no parsed count → treat as 1/1
    if r.returncode == 0 and total == 0:
        passed, total = 1, 1
    return {
        "name":      name,
        "passed":    passed,
        "total":     total,
        "exit_code": r.returncode,
        "green":     r.returncode == 0 and passed == total and total > 0
    }

def main():
    results = []
    for name, path in SUITES:
        r = run_suite(name, path)
        results.append(r)
        icon = "✅" if r["green"] else "❌"
        print(f"  {icon} {name}: {r['passed']}/{r['total']}")

    all_green = all(r["green"] for r in results)
    total_passed = sum(r["passed"] for r in results)
    total_tests  = sum(r["total"]  for r in results)

    gate = {
        "status":       "green" if all_green else "red",
        "all_green":    all_green,
        "total_passed": total_passed,
        "total_tests":  total_tests,
        "suites":       results,
        "checked_at":   now_utc.isoformat(),
        "verdict":      "APPLY_ALLOWED" if all_green else "APPLY_BLOCKED"
    }

    os.makedirs(LEDGER, exist_ok=True)
    json.dump(gate, open(GATE_F, "w"), indent=2)

    print(f"\n{'='*50}")
    print(f"  TEST GATE: {gate['verdict']}")
    print(f"  {total_passed}/{total_tests} total tests passed")
    print(f"  Written: {GATE_F}")

    sys.exit(0 if all_green else 1)

if __name__ == "__main__":
    main()
