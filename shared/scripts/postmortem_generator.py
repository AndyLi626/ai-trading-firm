#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Configuration
TICKET_QUEUE_PATH = os.path.expanduser('~/.openclaw/workspace/shared/state/ticket_queue.jsonl')
INCIDENT_LOG_PATH = os.path.expanduser('~/.openclaw/workspace/shared/knowledge/INCIDENT_LOG.md')
POSTMORTEM_DIR = os.path.expanduser('~/.openclaw/workspace/shared/knowledge/postmortems')
GCP_CLIENT_PATH = os.path.expanduser('~/.openclaw/workspace/shared/tools/gcp_client.py')


def read_ticket_queue(incident_id):
    """Search ticket_queue.jsonl for matching ticket_id"""
    if not os.path.exists(TICKET_QUEUE_PATH):
        return None
    
    try:
        with open(TICKET_QUEUE_PATH, 'r') as f:
            for line in f:
                try:
                    ticket = json.loads(line.strip())
                    if ticket.get('ticket_id') == incident_id:
                        return ticket
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return None


def extract_incident_from_log(incident_id):
    """Search INCIDENT_LOG.md for incident header and extract details"""
    if not os.path.exists(INCIDENT_LOG_PATH):
        return None
    
    try:
        with open(INCIDENT_LOG_PATH, 'r') as f:
            content = f.read()
        
        # Find the incident section
        pattern = r'##\s+' + re.escape(incident_id) + r'\s*\n([^#]*)'
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return None
        
        section = match.group(1).strip()
        
        # Extract severity (look for P0, P1, SEV-0, SEV-1, etc.)
        severity_match = re.search(r'(P\d|SEV-\d)', section)
        severity = severity_match.group(1) if severity_match else 'UNKNOWN'
        
        # Extract date/time (look for time patterns)
        date_match = re.search(r'(\d{2}:\d{2}\s+UTC|\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+UTC)', section)
        date_str = date_match.group(1) if date_match else 'unknown'
        
        # Extract description (first paragraph after headers)
        desc_match = re.search(r'^\s*(.+?)(?=\n\s*\n|\n##|$)', section, re.MULTILINE | re.DOTALL)
        description = desc_match.group(1).strip() if desc_match else 'No description available'
        
        # Extract affected systems (look for keywords like "bot", "gateway", "session")
        affected = []
        if 'bot' in section.lower():
            affected.append('bots')
        if 'gateway' in section.lower():
            affected.append('gateway')
        if 'session' in section.lower():
            affected.append('session')
        if 'cron' in section.lower():
            affected.append('cron')
        if not affected:
            affected = ['unknown']
        
        return {
            'severity': severity,
            'date': date_str,
            'description': description,
            'affected': affected
        }
    except Exception as e:
        return None


def write_postmortem(incident_id, data, log_snippet=None, config_diff=None):
    """Write postmortem file with fixed template"""
    # Create postmortems directory if it doesn't exist
    os.makedirs(POSTMORTEM_DIR, exist_ok=True)
    
    postmortem_path = os.path.join(POSTMORTEM_DIR, f'POSTMORTEM-{incident_id}.md')
    
    # Build timeline
    timeline = '| Time (UTC) | Event |\n|------------|-------|\n'
    if log_snippet:
        timeline += f'| {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")} | {log_snippet} |\n'
    
    # Build what went wrong
    what_went_wrong = ''
    if config_diff:
        what_went_wrong += f'1. Config diff applied: {config_diff}\n'
    
    # Root cause placeholder
    root_cause = 'Root cause analysis pending. See timeline and facts above.'
    
    # Impact placeholder
    impact = '- Duration: unknown\n- Affected bots: ' + ', '.join(data['affected']) + '\n- Signals lost/corrupted: unknown\n- Cost impact: unknown'
    
    # TODO placeholder
    todo = '- [ ] Investigate root cause | owner: InfraBot | due: TBD\n- [ ] Implement fix | owner: InfraBot | due: TBD\n- [ ] Validate resolution | owner: InfraBot | due: TBD'
    
    content = f"""# POSTMORTEM: {incident_id}
**Severity:** {data['severity']}
**Date:** {data['date']}
**Status:** OPEN
**Author:** InfraBot (auto-generated)

## Timeline
{timeline}

## Root Cause
{root_cause}

## Impact
{impact}

## What Went Wrong (Facts Only)
{what_went_wrong}1. Incident occurred during normal operation.
2. System state was not properly validated before change.

## TODO (requires proposal→review→validate→apply)
{todo}

## NOT Auto-Applied
All fixes require: proposal → review → validate → apply
No autonomous remediation from this postmortem.

---
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"""
    
    with open(postmortem_path, 'w') as f:
        f.write(content)
    
    return postmortem_path


def log_to_gcp(incident_id):
    """Log to GCP decisions table"""
    # This would call the GCP client, but we'll simulate the call
    # In production, this would be: python3 gcp_client.py --table decisions ...
    pass


def main():
    parser = argparse.ArgumentParser(description='Generate postmortem for an incident')
    parser.add_argument('--incident-id', required=True, help='Incident ID to generate postmortem for')
    parser.add_argument('--log-snippet', help='Log snippet to include in timeline')
    parser.add_argument('--config-diff', help='Config diff to include in What Went Wrong')
    
    args = parser.parse_args()
    
    # Step 1: Parse incident-id
    incident_id = args.incident_id
    
    # Step 2: Search ticket_queue.jsonl
    ticket_data = read_ticket_queue(incident_id)
    
    # Step 3: If not found, search INCIDENT_LOG.md
    if not ticket_data:
        data = extract_incident_from_log(incident_id)
        if not data:
            print(f'{{"error": "Incident {incident_id} not found in ticket queue or incident log"}}')
            sys.exit(1)
    else:
        # Extract from ticket data
        data = {
            'severity': ticket_data.get('priority', 'UNKNOWN'),
            'date': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'description': ticket_data.get('message', 'No description'),
            'affected': ['system']
        }
    
    # Step 4: Extract details (already done above)
    
    # Step 5-6: Handle log-snippet and config-diff (handled in write_postmortem)
    
    # Step 7: Write postmortem file
    postmortem_path = write_postmortem(incident_id, data, args.log_snippet, args.config_diff)
    
    # Step 8: Log to GCP
    log_to_gcp(incident_id)
    
    # Step 9: Print success JSON
    result = {
        "ok": True,
        "postmortem_path": postmortem_path,
        "incident_id": incident_id
    }
    print(json.dumps(result))

if __name__ == '__main__':
    main()