# Platform Changelog
_Append-only. Each entry: date | commit | change | files_

| Date | Commit | Change | Key Files |
|------|--------|--------|-----------|
| 2026-02-xx | f60d1d0 | v0.4-pre-release rollback point | — |
| 2026-02-xx | a11f09a | v0.5-stable | config_guard, budget |
| 2026-02-xx | 76f11ee | v0.6-stable | token accounting, manager delta |
| 2026-03-02 | 380d1e4 | post-P0: detect_changes, media routing | — |
| 2026-03-02 | a5ed7be | fix: collect_team IndentationError + ManagerBot message tool | collect_team.py |
| 2026-03-02 | ac14654 | autonomy framework: orchestrator/skills_scan/infra_scan | 4 scripts |
| 2026-03-02 | c4f3a72 | token cost summary + model_pricing.json | token_cost_summary.py |
| 2026-03-02 | c2951b6 | P0: market_pulse+anomaly_detector Tier0 | watchlist.json |
| 2026-03-02 | 4ebb10f | P1: strategy_hint+risk_review_lite+Event Loop | 2 scripts |
| 2026-03-02 | `d77631f9` | P1 Archivist: changelog hook + test_gate + bot_cache.archivist | archivist_apply_hook.py, test_gate.py, ARCH_LOCK.json |
| 2026-03-02 | `fc52f3d2` | P0: infra_ticket通道+source_health+Manager投递修复 | infra_ticket.py, source_health.py, jobs.json |
| 2026-03-02 | `c6d3dc3d` | feat: run_registry — job运行事实源 + 5脚本写入钩子 + Manager查询入口 | run_registry.py, market_pulse.py, emergency_scan.py |
