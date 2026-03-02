#!/usr/bin/env python3
"""
run_with_budget.py — Budget enforcer wrapper for bot cron runs.

Usage (两种调用均支持):
  # 模式 A：precheck only（输出 JSON，不执行命令）
  python3 run_with_budget.py <bot_id> <estimated_tokens>

  # 模式 B：推荐——分隔符后接命令（budget 通过才执行）
  python3 run_with_budget.py <bot_id> <estimated_tokens> -- python3 script.py [args...]

  # 模式 C：兼容旧格式（第3个参数是整数则视为 tokens，其余为命令）
  python3 run_with_budget.py <bot_id> <estimated_tokens> python3 script.py [args...]

  注意：<estimated_tokens> 必须是整数；python3/命令不能作为第3个参数。

Output JSON: {allowed, action, budget_mode, today_total, degrade_hints}
Exit code: 0=allowed/executed, 1=hard_stop/budget_blocked
"""
import os, sys, json, uuid, subprocess
from datetime import datetime, timezone

WORKSPACE = "/home/lishopping913/.openclaw/workspace"
sys.path.insert(0, os.path.join(WORKSPACE, "shared", "tools"))

HARVEST_SCRIPT = os.path.join(WORKSPACE, "shared", "scripts", "harvest_openclaw_usage.py")


def _run_harvest_quick():
    try:
        result = subprocess.run(
            [sys.executable, HARVEST_SCRIPT, "--hours", "2"],
            capture_output=True, text=True, timeout=30
        )
        for line in reversed(result.stdout.strip().splitlines()):
            try:
                return json.loads(line)
            except Exception:
                continue
    except Exception:
        pass
    return {}


def _write_audit_event(bot: str, task_type: str, status: str, estimated_tokens: int, is_test: bool = False):
    try:
        import gcp_client as g
        run_id = str(uuid.uuid4())
        today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        g.insert_rows("token_usage_runs", [{
            "run_id":              run_id,
            "bot":                 bot,
            "task_type":           task_type,
            "llm_calls":           0,
            "total_input_tokens":  0,
            "total_output_tokens": 0,
            "total_tokens":        estimated_tokens,
            "duration_sec":        0,
            "status":              status,
            "date":                today,
            "usage_source":        "estimated",
            "record_source":       "budget_guard",
            "is_test":             is_test,
        }])
    except Exception as e:
        print(f"[run_with_budget] audit write failed: {e}", file=sys.stderr)


def _parse_args():
    """
    解析参数，支持三种调用格式，fail-fast 并给出清晰错误。
    返回 (bot_id, estimated_tokens, command_list_or_None)
    """
    args = sys.argv[1:]
    USAGE = (
        "Usage:\n"
        "  run_with_budget.py <bot> <tokens>                       # precheck only\n"
        "  run_with_budget.py <bot> <tokens> -- cmd [args...]      # 推荐\n"
        "  run_with_budget.py <bot> <tokens> cmd [args...]         # 兼容旧格式\n"
        "  <tokens> 必须是整数，例如 200，不能是 'python3'"
    )
    if len(args) < 2:
        print(json.dumps({"error": USAGE}), file=sys.stderr)
        sys.exit(1)

    bot_id = args[0]

    # 第2个参数必须是整数
    try:
        estimated_tokens = int(args[1])
    except ValueError:
        print(json.dumps({
            "error": f"estimated_tokens 必须是整数，收到: {args[1]!r}",
            "hint":  USAGE
        }), file=sys.stderr)
        sys.exit(1)

    # 解析命令部分
    rest = args[2:]
    if not rest:
        return bot_id, estimated_tokens, None          # precheck only

    if rest[0] == '--':
        cmd = rest[1:] if len(rest) > 1 else None      # 模式 B
    else:
        cmd = rest                                      # 模式 C（兼容旧格式）

    return bot_id, estimated_tokens, cmd or None


def main():
    bot_id, estimated_tokens, command = _parse_args()
    task_type = ' '.join(command) if command else 'precheck'

    # Step 1: quick harvest for fresh data
    _run_harvest_quick()

    # Invalidate budget cache so we get fresh data
    cache_file = "/tmp/oc_facts/budget_state.json"
    if os.path.exists(cache_file):
        os.remove(cache_file)

    # Step 2: check budget
    try:
        import budget_guard as bg
        result = bg.check_budget(bot_id, estimated_tokens)
    except Exception as e:
        print(json.dumps({"error": str(e), "allowed": True, "action": "ok"}))
        sys.exit(0)

    # Fetch today_total for output
    today_total = 0
    try:
        import gcp_client as g
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows  = g.query(f"SELECT SUM(total_tokens) AS t FROM `ai-org-mvp-001.trading_firm.token_usage_runs` WHERE bot='{bot_id}' AND date='{today}'")
        today_total = int((rows[0].get("t") or 0) if rows else 0)
    except Exception:
        pass

    action = result.get("action", "ok")
    output = {
        "allowed":      result.get("allowed", True),
        "action":       action,
        "budget_mode":  action,
        "today_total":  today_total,
        "reason":       result.get("reason", ""),
        "degrade_hints": result.get("degrade_hints", {}),
    }

    # Step 3: write audit event for stop/degrade
    if action == "stop":
        _write_audit_event(bot_id, task_type, "budget_stop", estimated_tokens)
    elif action == "degrade":
        _write_audit_event(bot_id, task_type, "budget_degrade", estimated_tokens)

    print(json.dumps(output))

    # Step 4: 如果 allowed 且有命令，执行命令
    if result.get("allowed", True) and command:
        try:
            ret = subprocess.run(command)
            sys.exit(ret.returncode)
        except FileNotFoundError as e:
            print(json.dumps({"error": f"命令不存在: {e}"}), file=sys.stderr)
            sys.exit(1)
    else:
        sys.exit(0 if result.get("allowed", True) else 1)


if __name__ == "__main__":
    main()
