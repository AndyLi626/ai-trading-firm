#!/bin/bash
python3 $(cd "$(dirname "$0")/../.."; pwd)/shared/scripts/run_with_budget.py media 2000 \
  python3 $(cd "$(dirname "$0")/../.."; pwd)/shared/scripts/emergency_scan.py 2>/dev/null
