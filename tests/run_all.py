#!/usr/bin/env python3
"""
Master test runner - runs all tests in order and reports results.

Usage:
  python tests/run_all.py           # run all
  python tests/run_all.py gateway   # run single suite
  python tests/run_all.py --fast    # skip slow tests

The historical runtime workspace is ~/.openclaw/workspace. Set
OPENCLAW_WORKSPACE to override it when running from another checkout.
"""
import os
import subprocess
import sys
import time


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
WORKSPACE = os.environ.get("OPENCLAW_WORKSPACE", DEFAULT_WORKSPACE)

SUITES = [
    ("gateway", "test_gateway.py", "Gateway and system health", False),
    ("models", "test_models.py", "AI model endpoints", False),
    ("gcp", "test_gcp.py", "GCP BigQuery tables", False),
    ("execution", "test_execution.py", "ExecutionService and Alpaca", False),
    ("media", "test_media.py", "MediaBot pipeline", False),
    ("crypto", "test_crypto.py", "Crypto execution", False),
    ("options", "test_options.py", "Options execution during market hours", True),
    ("market_data", "test_market_data.py", "Market data APIs", True),
    ("pipeline", "test_pipeline.py", "Full E2E pipeline", False),
    ("audit", "test_audit.py", "AuditBot and shared components", False),
    ("risk", "test_risk.py", "RiskBot and risk limits", False),
    ("infra", "test_infra.py", "InfraBot and workspace health", False),
    ("manager", "test_manager.py", "ManagerBot and orchestration", False),
    ("strategy", "test_strategy.py", "StrategyBot and market scripts", False),
    (
        "failure_chains",
        "test_failure_chains.py",
        "Failure-chain scenarios: stale, failure, signal, cache",
        False,
    ),
    (
        "token_meter",
        "test_token_meter.py",
        "Token accounting infrastructure",
        False,
    ),
    (
        "harvester",
        "test_harvester.py",
        "Runtime usage harvester and budget status",
        False,
    ),
]


def _ensure_workspace() -> None:
    if os.path.isdir(WORKSPACE):
        return

    print("=" * 60)
    print("  AI TRADING FIRM - TEST SUITE")
    print("=" * 60)
    print(f"Required runtime workspace not found: {WORKSPACE}")
    print(
        "Set OPENCLAW_WORKSPACE to a prepared runtime checkout, or use the "
        "fresh-clone checks documented in README.md."
    )
    sys.exit(2)


def main() -> int:
    _ensure_workspace()

    args = sys.argv[1:]
    fast_mode = "--fast" in args
    filter_name = next((a for a in args if not a.startswith("--")), None)

    results = []
    start_all = time.time()

    print("=" * 60)
    print("  AI TRADING FIRM - TEST SUITE")
    print(f"  {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
    print("=" * 60)

    for suite_id, filename, description, is_slow in SUITES:
        if filter_name and filter_name != suite_id:
            continue
        if fast_mode and is_slow:
            print(f"\nSKIP [{suite_id}] {description} (--fast)")
            continue

        print(f"\n{'-' * 60}")
        print(f">> [{suite_id.upper()}] {description}")
        print(f"{'-' * 60}")

        start = time.time()
        try:
            result = subprocess.run(
                [sys.executable, os.path.join(TESTS_DIR, filename)],
                timeout=120,
                cwd=WORKSPACE,
            )
            elapsed = time.time() - start
            passed = result.returncode == 0
            results.append((suite_id, passed, elapsed))
            status = "PASSED" if passed else "FAILED"
            print(f"\n{status} [{suite_id}] in {elapsed:.1f}s")
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            results.append((suite_id, False, elapsed))
            print(f"\nTIMEOUT [{suite_id}] after {elapsed:.1f}s")
        except Exception as exc:
            results.append((suite_id, False, 0))
            print(f"\nERROR [{suite_id}]: {exc}")

    total_elapsed = time.time() - start_all
    passed = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]

    print(f"\n{'=' * 60}")
    print(
        f"  RESULTS: {len(passed)}/{len(results)} suites passed "
        f"({total_elapsed:.1f}s total)"
    )
    print(f"{'=' * 60}")
    for suite_id, ok, elapsed in results:
        icon = "OK" if ok else "FAIL"
        print(f"  {icon:<4} {suite_id:<15} {elapsed:.1f}s")

    if failed:
        print(f"\n  FAILED: {[r[0] for r in failed]}")
        print("  Fix failing suites before deploying changes.\n")
        return 1

    print("\n  All suites passed.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
