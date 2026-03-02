#!/usr/bin/env python3
"""
Master test runner — runs all tests in order, reports results
Usage:
  python3 tests/run_all.py           # run all
  python3 tests/run_all.py gateway   # run single suite
  python3 tests/run_all.py --fast    # skip slow tests (market data)
"""
import sys, os, subprocess, time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

SUITES = [
    ("gateway",     "test_gateway.py",     "Gateway & system health",      False),
    ("models",      "test_models.py",      "AI model endpoints",           False),
    ("gcp",         "test_gcp.py",         "GCP BigQuery tables",          False),
    ("execution",   "test_execution.py",   "ExecutionService + Alpaca",    False),
    ("media",       "test_media.py",       "MediaBot pipeline",            False),
    ("crypto",      "test_crypto.py",      "Crypto execution",             False),
    ("options",     "test_options.py",     "Options execution (mkt hrs)",  True),   # slow=True since market hours only
    ("market_data", "test_market_data.py", "Market data APIs (slow)",      True),  # slow=True
    ("pipeline",    "test_pipeline.py",    "Full E2E pipeline",            False),
    # Agent & governance coverage
    ("audit",       "test_audit.py",       "AuditBot & shared components", False),
    ("risk",        "test_risk.py",        "RiskBot & risk limits",        False),
    ("infra",       "test_infra.py",       "InfraBot & workspace health",  False),
    ("manager",     "test_manager.py",     "ManagerBot & orchestration",   False),
    ("strategy",    "test_strategy.py",    "StrategyBot & market scripts", False),
    ("failure_chains", "test_failure_chains.py", "Failure-chain scenarios (stale/fail/signal/cache)", False),
    ("token_meter",    "test_token_meter.py",    "Token accounting infrastructure",                   False),
    ("harvester",      "test_harvester.py",      "Runtime usage harvester + budget status",            False),
]

args = sys.argv[1:]
fast_mode = "--fast" in args
filter_name = next((a for a in args if not a.startswith("--")), None)

results = []
start_all = time.time()

print("=" * 60)
print("  AI TRADING FIRM — TEST SUITE")
print(f"  {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}")
print("=" * 60)

for suite_id, filename, description, is_slow in SUITES:
    if filter_name and filter_name != suite_id:
        continue
    if fast_mode and is_slow:
        print(f"\n⏭  SKIP [{suite_id}] {description} (--fast)")
        continue

    print(f"\n{'─'*60}")
    print(f"▶  [{suite_id.upper()}] {description}")
    print(f"{'─'*60}")

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, os.path.join(TESTS_DIR, filename)],
            timeout=120,
            cwd=os.path.expanduser('~/.openclaw/workspace')
        )
        elapsed = time.time() - start
        passed = result.returncode == 0
        results.append((suite_id, passed, elapsed))
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"\n{status} [{suite_id}] in {elapsed:.1f}s")
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        results.append((suite_id, False, elapsed))
        print(f"\n⏱  TIMEOUT [{suite_id}] after {elapsed:.1f}s")
    except Exception as e:
        results.append((suite_id, False, 0))
        print(f"\n💥 ERROR [{suite_id}]: {e}")

# Summary
total_elapsed = time.time() - start_all
passed = [r for r in results if r[1]]
failed = [r for r in results if not r[1]]

print(f"\n{'='*60}")
print(f"  RESULTS: {len(passed)}/{len(results)} suites passed  ({total_elapsed:.1f}s total)")
print(f"{'='*60}")
for sid, ok, elapsed in results:
    icon = "✅" if ok else "❌"
    print(f"  {icon} {sid:<15} {elapsed:.1f}s")

if failed:
    print(f"\n  FAILED: {[r[0] for r in failed]}")
    print("  Fix failing suites before deploying changes.\n")
    sys.exit(1)
else:
    print("\n  All suites passed. System ready. ✅\n")
    sys.exit(0)
