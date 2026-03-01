# LEARNING_CRON_PROMPT.md — Reusable Learning Prompt Snippets

These are prompt fragments to inject into cron jobs to ensure bots actively learn.

## InfraBot: Weekly Skill Discovery
Add to infra cron periodically:
```
Also: check https://clawhub.com via web_search for any new skills tagged 'trading', 'finance', or 'market'. 
If found, append to shared/knowledge/BOT_SKILLS_REGISTRY.md under "Repo Discovery Queue".
```

## StrategyBot: Repo Discovery  
Add to strategy-scan periodically:
```
Also: web_search GitHub for "algorithmic trading python 2026" — note any repos with >100 stars 
not already in BOT_SKILLS_REGISTRY.md. Append to registry if found.
```

## MediaBot: Feed Discovery
Add to media-intel-scan periodically:
```
Also: check if market_news.py Brave results include any recurring high-quality sources. 
Log notable sources to shared/knowledge/BOT_SKILLS_REGISTRY.md.
```

## All Bots: Usage Enforcement
Every cron prompt should reference at least one:
- A specific tool/function to call
- A specific file to read or write  
- A specific GCP table to log to

"Use it or lose it" — skills not referenced in cron prompts get flagged for removal.
