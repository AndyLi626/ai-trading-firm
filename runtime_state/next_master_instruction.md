# Next Master Instruction

Read this file at the start of every session. Treat it as the authoritative state.

## Current Phase: INFRA SETUP — Agent scaffolding complete

## System Shape (as of 2026-03-01)

Agents registered in OpenClaw:
- main (InfraBot) — platform builder, current Telegram endpoint
- manager (ManagerBot) — Director, needs Telegram bot token to become Boss interface
- research (ResearchBot) — proactive research and strategy
- media (MediaBot) — news and intelligence
- risk (RiskBot) — independent risk review
- audit (AuditBot) — compliance and decision logging

Execution: NOT an agent — deterministic only, no AI in execution path.

## Immediate Blockers

1. ManagerBot needs a Telegram bot token (Boss must create via BotFather)
2. GCP database not yet configured
3. Repos not yet installed (worldmonitor, get-shit-done)

## Boss Intent

Build an OpenClaw-hosted AI trading company team where:
- Boss talks ONLY to ManagerBot
- All other bots coordinate internally
- System is proactive, self-learning, and human-like
- No hand-built features — integrate existing repos/skills

## InfraBot Standing Orders

- Never hand-implement what a repo/skill can do
- Keep ManagerBot as the sole Boss interface
- Maintain this file as the authoritative runtime state
- Report every 5 minutes during active build sessions
