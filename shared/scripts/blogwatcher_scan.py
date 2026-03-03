#!/usr/bin/env python3
"""
blogwatcher_scan.py — MediaBot RSS feed scanner
Runs blogwatcher scan, captures new articles, writes to memory/blog_feed_latest.json
Deterministic — no LLM.
"""
import subprocess, json, os, time
from datetime import datetime, timezone

WS_MEDIA = os.path.expanduser('~/.openclaw/workspace-media')
WS_MAIN  = os.path.expanduser('~/.openclaw/workspace')
OUT_PATH = os.path.join(WS_MEDIA, 'memory', 'blog_feed_latest.json')
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

def run_scan():
    r = subprocess.run(['blogwatcher', 'scan'], capture_output=True, text=True, timeout=30)
    return r.stdout, r.returncode

def get_unread():
    r = subprocess.run(['blogwatcher', 'articles', '--unread'],
                       capture_output=True, text=True, timeout=15)
    return r.stdout

def parse_articles(raw):
    """Parse blogwatcher articles output into list of dicts."""
    articles = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('No '):
            continue
        articles.append({'text': line})
    return articles

def main():
    now = datetime.now(timezone.utc).isoformat()
    scan_out, rc = run_scan()

    # Count new articles from scan output
    import re
    new_total_match = re.search(r'Found (\d+) new article', scan_out)
    new_count = int(new_total_match.group(1)) if new_total_match else 0

    unread_raw = get_unread()
    articles   = parse_articles(unread_raw)

    result = {
        'as_of_utc':   now,
        'new_articles': new_count,
        'feeds':        ['TechCrunch','Hacker News Best','The Verge Tech'],
        'scan_summary': scan_out.strip()[-500:],
        'unread_count': len(articles),
        'source':       'blogwatcher v0.0.2',
    }

    with open(OUT_PATH, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"blogwatcher_scan: new={new_count} unread={len(articles)} as_of={now[:19]}")
    return result

if __name__ == '__main__':
    main()
