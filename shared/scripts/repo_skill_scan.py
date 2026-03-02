#!/usr/bin/env python3
"""
repo_skill_scan.py
Scans for new repos / skills / research ideas for the trading firm.
Route A: web_search via Brave API (online)
Route B: local doc/ledger mining (offline fallback)
Output: memory/new_skill_repo_opportunities.md
"""
import json, os, sys, urllib.request, urllib.error, gzip, time
from datetime import datetime, timezone

WS      = os.path.expanduser('~/.openclaw/workspace')
OUT     = os.path.join(WS, 'memory/new_skill_repo_opportunities.md')
KEY_F   = os.path.expanduser('~/.openclaw/secrets/brave_api_key.txt')

def brave_search(query, count=5):
    key = open(KEY_F).read().strip()
    url = f'https://api.search.brave.com/res/v1/web/search?q={urllib.request.quote(query)}&count={count}'
    req = urllib.request.Request(url, headers={
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'X-Subscription-Token': key,
    })
    with urllib.request.urlopen(req, timeout=10) as r:
        body = r.read()
        if r.info().get('Content-Encoding') == 'gzip':
            body = gzip.decompress(body)
        return json.loads(body).get('web', {}).get('results', [])

def route_a():
    """Online scan via Brave Search."""
    queries = [
        ('repo',    'site:github.com algorithmic trading python 2024 2025 stars:>100'),
        ('skill',   'site:clawhub.com OR site:github.com openclaw skill trading finance'),
        ('research','arxiv.org OR ssrn.com quantitative trading machine learning 2025'),
    ]
    results = {}
    for tag, q in queries:
        try:
            hits = brave_search(q, count=5)
            results[tag] = hits[:3]
            time.sleep(0.5)
        except Exception as e:
            results[tag] = [{'title': f'search error: {e}', 'url': ''}]
    return results, 'online'

def route_b():
    """Offline: mine local docs/ledger for underutilised assets."""
    results = {'repo': [], 'skill': [], 'research': []}

    # Installed repos
    repos_dir = os.path.expanduser('~/.openclaw/workspace-research/repos')
    if os.path.isdir(repos_dir):
        for repo in os.listdir(repos_dir)[:5]:
            results['repo'].append({
                'title': f'[LOCAL] {repo} — already installed, under-utilised?',
                'url': f'file://{repos_dir}/{repo}',
                'description': 'Installed but not yet wired into strategy pipeline'
            })

    # Available skills from ARCH_LOCK
    al_path = os.path.join(WS, 'ledger/ARCH_LOCK.json')
    if os.path.exists(al_path):
        al = json.load(open(al_path))
        for entry in al.get('entries', [])[:3]:
            if 'skill' in entry.get('path', '').lower():
                results['skill'].append({
                    'title': f"[LOCAL] {entry['path']} — existing skill",
                    'url': entry['path'],
                    'description': entry.get('checksum', '')[:30]
                })

    # Research ideas from ADRs
    adr_dir = os.path.join(WS, 'ledger/ADRs')
    if os.path.isdir(adr_dir):
        for f in sorted(os.listdir(adr_dir))[-3:]:
            results['research'].append({
                'title': f'[LOCAL ADR] {f}',
                'url': os.path.join(adr_dir, f),
                'description': 'Review for potential strategy implications'
            })

    return results, 'offline'

def write_report(results, mode, now_s):
    lines = [
        f'# New Skill / Repo Opportunities',
        f'',
        f'**as_of**: {now_s[:19]} UTC  ',
        f'**mode**: `{mode}` (Route {"A — online Brave Search" if mode=="online" else "B — offline local mining"})  ',
        f'',
    ]

    for tag, items in results.items():
        label = {'repo': '## 1. Repo', 'skill': '## 2. Skill', 'research': '## 3. Research Idea'}[tag]
        lines.append(label)
        lines.append('')
        if not items:
            lines.append('_No results_')
        for i, item in enumerate(items[:3], 1):
            title = item.get('title', '?')[:80]
            url   = item.get('url', '')[:100]
            desc  = item.get('description', item.get('extra_snippets', [''])[0] if isinstance(item.get('extra_snippets'), list) else '')
            desc  = str(desc)[:120] if desc else ''
            lines.append(f'### {i}. {title}')
            if url: lines.append(f'URL: <{url}>')
            if desc: lines.append(f'> {desc}')
            lines.append('')

    with open(OUT, 'w') as f:
        f.write('\n'.join(lines))

def run():
    now_s = datetime.now(timezone.utc).isoformat()
    try:
        results, mode = route_a()
        print(f'Route A (online): success')
    except Exception as e:
        print(f'Route A failed ({e}), falling back to Route B')
        results, mode = route_b()

    write_report(results, mode, now_s)
    print(f'Written: {OUT}')
    return mode, results

if __name__ == '__main__':
    mode, results = run()
    for tag, items in results.items():
        print(f'  {tag}: {len(items)} results')
