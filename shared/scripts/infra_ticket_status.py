#!/usr/bin/env python3
"""
infra_ticket_status.py — Ticket queue summary tool.
Usage:
  python3 infra_ticket_status.py           # full summary
  python3 infra_ticket_status.py summary   # compact one-liner per ticket
  python3 infra_ticket_status.py <TICKET_ID>  # single ticket detail
Reads: shared/state/ticket_queue.jsonl (latest-event-per-id model)
"""
import json, os, sys
from datetime import datetime, timezone

WS      = os.path.expanduser('~/.openclaw/workspace')
TQ_PATH = os.path.join(WS, 'shared/state/ticket_queue.jsonl')

RESOLVED_ACTIONS = {'resolve'}
RESOLVED_STATUSES = {'RESOLVED', 'CLOSED', 'CANCELLED'}


def load_tickets():
    """Return dict of tid -> latest event (authoritative state)."""
    all_events = {}
    with open(TQ_PATH) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                t = json.loads(line)
            except: continue
            tid = t.get('ticket_id') or t.get('id')
            if not tid: continue
            if tid not in all_events:
                all_events[tid] = []
            all_events[tid].append(t)

    # Build authoritative state: latest resolve wins; else latest event
    states = {}
    for tid, events in all_events.items():
        # Check if ever resolved
        resolved_ev = next(
            (e for e in reversed(events) if e.get('action') == 'resolve'),
            None
        )
        create_ev = next(
            (e for e in events if e.get('action') == 'create'),
            None
        )
        if resolved_ev:
            state = dict(resolved_ev)
            state['_create'] = create_ev or {}
            state['_events'] = events
        elif create_ev:
            # Find latest progress/ack event
            latest = events[-1]
            state = dict(create_ev)
            state['status'] = latest.get('status') or create_ev.get('status', 'OPEN')
            state['_latest_event'] = latest
            state['_events'] = events
        else:
            # No create event — likely internal system ticket, skip
            continue
        states[tid] = state
    return states


def is_open(state):
    status = state.get('status', '')
    action = state.get('action', '')
    return status not in RESOLVED_STATUSES and action not in RESOLVED_ACTIONS


def summary(states):
    open_tix    = {tid: s for tid, s in states.items() if is_open(s)}
    closed_tix  = {tid: s for tid, s in states.items() if not is_open(s)}

    now = datetime.now(timezone.utc).isoformat()[:19]
    print(f"Ticket Summary — as_of: {now} UTC")
    print(f"Total: {len(states)}  Open: {len(open_tix)}  Resolved: {len(closed_tix)}")
    print()

    if open_tix:
        print("=== OPEN ===")
        for tid, s in sorted(open_tix.items()):
            create = s.get('_create', s)
            title  = create.get('title', create.get('message', '?'))[:60]
            pri    = create.get('priority', '?')
            print(f"  [{pri:6s}] {tid:36s} {title}")
    else:
        print("=== OPEN === (none)")

    print()
    print("=== RESOLVED (recent) ===")
    for tid, s in sorted(closed_tix.items(),
                         key=lambda x: x[1].get('resolved_at', x[1].get('_ts', '')),
                         reverse=True)[:10]:
        res_at = str(s.get('resolved_at', s.get('_ts', '?')))[:19]
        owner  = s.get('owner', 'unknown')
        print(f"  [RESOLVED] {tid:36s}  resolved_at={res_at}  owner={owner}")

    return {'open_count': len(open_tix), 'resolved_count': len(closed_tix)}


def ticket_detail(states, tid):
    # fuzzy match
    matches = [k for k in states if tid.upper() in k.upper()]
    if not matches:
        print(f"Ticket not found: {tid}")
        return
    for match in matches:
        s = states[match]
        print(f"\n=== {match} ===")
        create = s.get('_create', s)
        print(f"  status:      {s.get('status','?')}")
        print(f"  priority:    {create.get('priority','?')}")
        print(f"  created_at:  {create.get('created_at', create.get('_ts','?'))[:19]}")
        if not is_open(s):
            print(f"  resolved_at: {s.get('resolved_at','?')[:19]}")
            print(f"  owner:       {s.get('owner','?')}")
            print(f"  root_cause:  {s.get('root_cause','?')[:120]}")
            print(f"  fix_summary: {s.get('fix_summary','?')[:120]}")
            ev = s.get('acceptance_evidence_paths', {})
            if ev:
                print("  evidence:")
                for k, v in ev.items():
                    print(f"    {k}: {v}")
        events = s.get('_events', [])
        print(f"  events ({len(events)}):")
        for e in events[-5:]:
            print(f"    {e.get('action'):10s} {str(e.get('_ts',''))[:19]}  status={e.get('status','')}  {str(e.get('error','') or e.get('comment','') or '')[:60]}")


def main():
    states = load_tickets()
    arg = sys.argv[1] if len(sys.argv) > 1 else 'summary'

    if arg in ('summary', 'all'):
        result = summary(states)
        if arg == 'summary':
            # Also emit JSON for machine consumption
            print()
            print(json.dumps({
                'open_count':     result['open_count'],
                'resolved_count': result['resolved_count'],
                'open_ids': [tid for tid, s in states.items() if is_open(s)],
            }, indent=2))
    else:
        ticket_detail(states, arg)


if __name__ == '__main__':
    main()
