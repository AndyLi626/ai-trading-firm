#!/usr/bin/env python3
"""repo_skills_scan.py — Scan installed skills vs cron references vs registry."""
import glob
import json
import os
import re
from datetime import datetime, timezone

WORKSPACE = os.environ.get("WORKSPACE", os.path.expanduser("~/.openclaw/workspace"))
CRON_JOBS = os.environ.get("CRON_JOBS_FILE",
    os.path.expanduser("~/.openclaw/cron/jobs.json"))
REGISTRY_PATH = os.path.join(WORKSPACE, "shared/knowledge/BOT_SKILLS_REGISTRY.md")

def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def find_installed_skills():
    skills = []
    pattern = os.path.expanduser("~/.openclaw/workspace*/skills/")
    for skills_dir in glob.glob(pattern):
        ws = os.path.basename(os.path.dirname(skills_dir))
        if not os.path.isdir(skills_dir):
            continue
        for name in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, name)
            if os.path.isdir(skill_path):
                skills.append({"skill_name": name, "workspace": ws,
                               "path": skill_path, "in_cron_prompt": False})
    # Also find SKILL.md files
    for skill_md in glob.glob(os.path.expanduser("~/.openclaw/workspace*/**/SKILL.md"),
                               recursive=True):
        name = os.path.basename(os.path.dirname(skill_md))
        ws = skill_md.split(os.sep)
        ws_part = next((p for p in ws if p.startswith("workspace")), "unknown")
        already = any(s["skill_name"] == name for s in skills)
        if not already:
            skills.append({"skill_name": name, "workspace": ws_part,
                           "path": os.path.dirname(skill_md),
                           "in_cron_prompt": False, "via_skill_md": True})
    return skills

def get_cron_prompts():
    if not os.path.exists(CRON_JOBS):
        return ""
    with open(CRON_JOBS) as f:
        data = json.load(f)
    prompts = []
    for job in data.get("jobs", []):
        p = job.get("payload", {})
        msg = p.get("message", "") if isinstance(p, dict) else ""
        prompts.append(msg)
    return "\n".join(prompts)

def get_registry_skills():
    if not os.path.exists(REGISTRY_PATH):
        return []
    skills = []
    with open(REGISTRY_PATH) as f:
        for line in f:
            m = re.search(r"`([a-z][a-z0-9_-]+)`", line)
            if m:
                skills.append(m.group(1))
    return list(set(skills))

def find_candidates():
    """README.md files in repos not already installed as skills."""
    candidates = []
    for readme in glob.glob(os.path.expanduser("~/.openclaw/workspace*/repos/**/README.md"),
                            recursive=True):
        repo_name = os.path.basename(os.path.dirname(readme))
        candidates.append({"repo_name": repo_name, "readme": readme})
    return candidates

def main():
    installed = find_installed_skills()
    cron_text = get_cron_prompts()
    registry = get_registry_skills()

    # Mark in_cron_prompt
    for skill in installed:
        if skill["skill_name"] in cron_text:
            skill["in_cron_prompt"] = True

    installed_names = {s["skill_name"] for s in installed}
    gaps = [r for r in registry if r not in installed_names]
    unused = [s["skill_name"] for s in installed if not s["in_cron_prompt"]]
    candidates = find_candidates()

    output = {
        "date": today_str(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "installed_skills": installed,
        "gaps": gaps,
        "unused": unused,
        "candidates": candidates,
    }

    out_dir = os.path.join(WORKSPACE, "memory", "autonomy", today_str())
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "repo_skills_scan.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Scan complete: {len(installed)} installed, {len(gaps)} gaps, "
          f"{len(unused)} unused, {len(candidates)} candidates")
    print(f"Output: {out_path}")

if __name__ == "__main__":
    main()
