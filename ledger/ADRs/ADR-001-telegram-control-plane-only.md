# ADR-001: Telegram is Control-Plane Only
**Date:** 2026-03-02 | **Status:** Accepted

## Context
Bots were sending full file contents, code blobs, and data dumps via Telegram. This caused context overflow, token waste, and security exposure.

## Decision
Telegram = control-plane only. Allowed: start tasks, query status, short directives (≤200 chars), summaries. Forbidden: code blobs, full file contents, heavy spawn payloads, market data dumps.

## Consequences
- sessions_spawn tasks use reference-based goals (file paths + criteria), never inline content
- Large builds go through exec path or subagent with file references
- Any violation is a transport incident (ref: INCIDENT-007)

## Enforcement
SOUL.md "Transport Rules" section in all bot workspaces. InfraBot SOUL.md § Transport Rules.
