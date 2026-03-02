#!/usr/bin/env python3
"""Archivist query. Usage: python3 archivist_query.py <keyword>"""
import sys, os
import os

LEDGER = os.path.expanduser('~/.openclaw/workspace/ledger')
SOURCES = ['CAPABILITIES.md','STATUS_MATRIX.md','ARCHITECTURE.md']

keyword = ' '.join(sys.argv[1:]).lower() if len(sys.argv) > 1 else ''
if not keyword:
    print("Usage: archivist_query.py <keyword>"); sys.exit(1)

results = []
for fname in SOURCES:
    path = os.path.join(LEDGER, fname)
    if not os.path.exists(path): continue
    for i, line in enumerate(open(path)):
        if keyword in line.lower():
            results.append({'file': fname, 'line': i+1, 'text': line.strip()[:120]})

if results:
    print(f"Found {len(results)} matches for '{keyword}':")
    for r in results: print(f"  [{r['file']}:{r['line']}] {r['text']}")
    sys.exit(0)
else:
    print(f"No matches for '{keyword}'")
    sys.exit(1)