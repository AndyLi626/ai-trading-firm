# Firm-Wide Risk Limits

## Position Limits
- Max notional per order: $10,000
- Max single position: 10% of portfolio
- Max sector concentration: 30%
- Max drawdown before halt: 10% of portfolio

## Approval Chain
1. StrategyBot generates DraftOrder
2. RiskBot MUST review before execution
3. RiskBot veto = STOP, only Boss can override
4. ExecutionService only accepts risk_approved=True orders

## Venue Rules
- Paper only (live disabled)
- Alpaca paper: equities
- Coinbase: crypto (pending SDK setup)

## Token Budget (per session)
- ManagerBot: unlimited (director)
- StrategyBot: 200k tokens/session
- MediaBot: 100k tokens/session
- RiskBot: 100k tokens/session
- AuditBot: 50k tokens/session
