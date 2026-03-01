# STATE.md — Current Project State
_Updated: 2026-03-01_

## Phase
Testing & Optimization (post v0.1)

## Status
- Pipeline: ✅ 5/5 test suites passing
- All 6 agents: ✅ operational
- Cron jobs: ✅ 5/5 running (strategy-scan timeout fixed to 180s)
- GCP BigQuery: ✅ all 7 tables live, data flowing
- Execution: ✅ Alpaca paper, $100k, live orders working
- GitHub: ✅ private repo synced (AndyLi626/ai-trading-firm)

## Completed This Session
- Test suite created: tests/ (gateway, models, gcp, execution, pipeline, run_all.py)
- strategy-scan timeout: 90s→180s, task simplified
- agent default timeout: 120s→240s
- compaction.mode confirmed: safeguard (aggressive is invalid)
- INCIDENT_LOG updated with incidents 005+006

## Next Steps
1. Wire crypto execution (Alpaca crypto: BTCUSD/ETHUSD/SOLUSD)
2. Add options strategy layer
3. Lean backtesting pipeline → live strategy generation
4. ManagerBot true coordination via sessions_send
5. Fix token_usage table (only 32 rows per 50 cycles)

## Blockers
- AlphaVantage: 5 req/min free tier (space out calls)
- Binance testnet: IP restricted
- Kalshi/data-analyst skills: not yet installed

## Key Numbers
- Paper account: $100k cash, PA37P8G6EG6D
- Cycle cost: ~$0.016/cycle (50% savings vs all-Sonnet)
- Total spend to date: ~$0.30
