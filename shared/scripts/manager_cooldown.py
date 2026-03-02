#!/usr/bin/env python3
import json
import sys
import time
from datetime import datetime
import os


def main():
    # Read input from stdin
    try:
        input_data = json.loads(sys.stdin.read())
        report_type = input_data.get('report_type')
        metrics_hash = input_data.get('metrics_hash')
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON input"}))
        sys.exit(1)
    
    # Read bot_cache.json
    try:
        with open(os.path.expanduser('~/.openclaw/workspace/memory/bot_cache.json'), 'r') as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {"manager": {}}
    except json.JSONDecodeError:
        cache = {"manager": {}}
    
    manager = cache.get('manager', {})
    
    # Check if same report type within 30 minutes
    last_report_type = manager.get('last_report_type')
    last_report_ts = manager.get('last_report_ts')
    
    if last_report_type == report_type and last_report_ts:
        try:
            last_ts = datetime.fromisoformat(last_report_ts.replace('Z', '+00:00'))
            now = datetime.now(last_ts.tzinfo)
            age_seconds = (now - last_ts).total_seconds()
            
            if age_seconds < 1800:  # 30 minutes
                next_allowed = (last_ts + timedelta(seconds=1800)).isoformat()
                result = {
                    "cooldown": True,
                    "reason": "same report within 30min",
                    "next_allowed": next_allowed
                }
                print(json.dumps(result))
                sys.exit(1)
        except ValueError:
            pass
    
    # Check for no change in key metrics
    last_metrics_hash = manager.get('last_metrics_hash')
    if last_metrics_hash == metrics_hash and last_metrics_hash is not None:
        result = {
            "cooldown": True,
            "reason": "no delta"
        }
        print(json.dumps(result))
        sys.exit(1)
    
    # Update cache with new report info
    manager['last_report_type'] = report_type
    manager['last_report_ts'] = datetime.now().isoformat()
    manager['last_metrics_hash'] = metrics_hash
    
    # Write back to cache
    cache['manager'] = manager
    try:
        with open(os.path.expanduser('~/.openclaw/workspace/memory/bot_cache.json'), 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(json.dumps({"error": f"Failed to update cache: {e}"}))
        sys.exit(1)
    
    # Success
    print(json.dumps({"cooldown": False}))
    sys.exit(0)


if __name__ == "__main__":
    main()