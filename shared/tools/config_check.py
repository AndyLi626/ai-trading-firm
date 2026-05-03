"""ConfigCheck guardrail.

Validation rules:
1. Unknown top-level keys are rejected.
2. Missing soul file references are rejected.
3. Model IDs outside the registry are rejected.
4. Agent IDs outside the allowlist are rejected.

validate(patch_dict) -> {"result": "PASS"|"REJECT", "reason": str}
"""

import os

KNOWN_TOP_KEYS = {
    # core
    "meta", "wizard", "auth", "models", "agents", "gateway",
    "compaction", "heartbeat", "timeoutSeconds", "typingIntervalSeconds",
    "typingMode", "workspace", "defaults", "list",
    # actual openclaw.json top-level keys (synced 2026-03-02)
    "tools", "bindings", "messages", "channels", "plugins",
    "skills", "commands", "session", "cron", "hooks",
}

ALLOWED_AGENT_IDS = {
    "main", "manager", "research", "media", "risk", "audit", "infra"
}

ALLOWED_MODELS = {
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-haiku-4-5",
    "qwen/qwen-plus",
    "qwen/qwen-turbo",
    "qwen/qwen-max",
    "google/gemini-2.0-flash",
    "google/gemini-2.0-flash-lite",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-pro",
}


def validate(patch_dict: dict) -> dict:
    """
    Validate a config patch dict.
    Returns {"result": "PASS"|"REJECT", "reason": str}
    """
    if not isinstance(patch_dict, dict):
        return {"result": "REJECT", "reason": "patch_dict must be a dict"}

    # Rule 1: unknown top-level keys
    for key in patch_dict:
        if key not in KNOWN_TOP_KEYS:
            return {
                "result": "REJECT",
                "reason": f"Unknown top-level key: '{key}'. Allowed keys: {sorted(KNOWN_TOP_KEYS)}"
            }

    # Rule 4 + Rule 2 + Rule 3: validate agents list
    if "agents" in patch_dict:
        agents_val = patch_dict["agents"]
        # agents can be a dict with "list" key or a list directly
        agents_list = []
        if isinstance(agents_val, list):
            agents_list = agents_val
        elif isinstance(agents_val, dict):
            agents_list = agents_val.get("list", [])

        for agent in agents_list:
            if not isinstance(agent, dict):
                return {"result": "REJECT", "reason": f"Agent entry must be a dict, got: {type(agent)}"}

            # Rule 5: unknown agent-level keys (compaction, default, etc. not allowed in list entries)
            ALLOWED_AGENT_KEYS = {"id", "name", "workspace", "model", "identity", "tools", "soul",
                                  "_phase", "_readonly", "_hourly_cap_tokens"}
            unknown_keys = [k for k in agent.keys() if k not in ALLOWED_AGENT_KEYS]
            if unknown_keys:
                return {"result": "REJECT",
                        "reason": f"Unknown key(s) in agent entry: {unknown_keys}. "
                                  f"Allowed: {sorted(ALLOWED_AGENT_KEYS)}"}

            # Rule 4: agentId allowlist
            agent_id = agent.get("id")
            if agent_id and agent_id not in ALLOWED_AGENT_IDS:
                return {
                    "result": "REJECT",
                    "reason": f"Unknown agentId: '{agent_id}'. Allowed: {sorted(ALLOWED_AGENT_IDS)}"
                }

            # Rule 2: soul path existence
            soul_path = agent.get("soul") or agent.get("identity", {}).get("soul") if isinstance(agent.get("identity"), dict) else agent.get("soul")
            if soul_path and isinstance(soul_path, str):
                expanded = os.path.expanduser(soul_path)
                if not os.path.exists(expanded):
                    return {
                        "result": "REJECT",
                        "reason": f"Soul file not found: '{soul_path}' (expanded: '{expanded}')"
                    }

            # Rule 3: model id validation
            model_val = agent.get("model")
            if model_val:
                if isinstance(model_val, dict):
                    primary = model_val.get("primary")
                    if primary and primary not in ALLOWED_MODELS:
                        return {
                            "result": "REJECT",
                            "reason": f"Unknown model id: '{primary}'. Allowed: {sorted(ALLOWED_MODELS)}"
                        }
                elif isinstance(model_val, str):
                    if model_val not in ALLOWED_MODELS:
                        return {
                            "result": "REJECT",
                            "reason": f"Unknown model id: '{model_val}'. Allowed: {sorted(ALLOWED_MODELS)}"
                        }

    return {"result": "PASS", "reason": "All checks passed"}


if __name__ == "__main__":
    import json
    import sys

    # Run built-in tests
    tests = [
        {
            "name": "Test 1: unknown_field -> REJECT",
            "input": {"unknown_field": "x"},
            "expected": "REJECT"
        },
        {
            "name": "Test 2: soul path not found -> REJECT",
            "input": {"agents": [{"id": "main", "soul": "/nonexistent/file.md"}]},
            "expected": "REJECT"
        },
        {
            "name": "Test 3: valid agent + model -> PASS",
            "input": {"agents": [{"id": "main", "model": {"primary": "anthropic/claude-sonnet-4-6"}}]},
            "expected": "PASS"
        },
    ]

    all_passed = True
    for t in tests:
        result = validate(t["input"])
        status = "OK" if result["result"] == t["expected"] else "FAIL"
        if result["result"] != t["expected"]:
            all_passed = False
        print(f"{status} {t['name']}")
        print(f"   Input:    {json.dumps(t['input'])}")
        print(f"   Expected: {t['expected']}")
        print(f"   Got:      {result['result']} - {result['reason']}")
        print()

    sys.exit(0 if all_passed else 1)
