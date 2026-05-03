# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

### GCP BigQuery
- SA key: ~/.openclaw/secrets/gcp-service-account.json
- Project: example-gcp-project | Dataset: trading_firm
- Client: shared/tools/gcp_client.py
- Tables: decisions, token_usage, trade_plans, risk_reviews, execution_logs, context_handoffs, bot_states
- Usage: python3 shared/tools/gcp_client.py (or import in scripts)

### Secrets Management
- All tokens in: ~/.openclaw/secrets/ (chmod 700)
- Loader: ~/.openclaw/secrets/load_secrets.py
- Never hardcode tokens in config or code
- To update a token: edit the relevant .txt file in secrets/

### Market Data (via StrategyBot's market_data.py)
- AlphaVantage: live quotes, OHLCV, news sentiment ✅
- FMP: fundamentals, financials ✅  
- OddsAPI: 85 sports/prediction markets ✅
- Coinbase: crypto (key in coinbase_api.json)

### StrategyBot Repos
- Lean (QuantConnect): ~/.openclaw/workspace-research/repos/Lean/
- financial-services-plugins: ~/.openclaw/workspace-research/repos/financial-services-plugins/
