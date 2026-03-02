# ADR-009 — No Gateway Restart During Active Session

****: Approved
**Date**: 2026-03-02
**Background**: Repeated Gateway restart 3 times causing session disconnect + synthetic error

## Cause
Gateway = session manager. Restart terminates all active WebSocket connections → Forces current conversation session to terminate → Result truncated → synthetic error

##
1. **During active conversation session `systemctl restart openclaw-gateway` strictly prohibited**
2. **`openclaw gateway restart` strictly prohibited** (same effect)
3. config :
 - `openclaw gateway reload` (hot-reload, ) — Use when supported
 - : (Boss )
 - : Wait for next natural restart

## Result
- → Result
- Gateway restart counter runaway ( counter=220+)

## Safe Config Change Procedure
1. `python3 shared/tools/config_check.py` verified
2. Write changes directly to file (openclaw.json)
3. **restart ** — Gateway auto-detects file changes or, Boss
4. Request Boss to restart if immediate effect needed