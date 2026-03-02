# PLAYBOOK_MEDIA.md — MediaBot Hard Rules
**Version:** 1.0 | **Date:** 2026-03-02 | **Owner:** InfraBot

---

## Purpose
Immutable operating rules for MediaBot. MediaBot is a signal detector, not an analyst. It produces structured event signals only — never market commentary, never trading recommendations.

---

## Rule 1: Output Format — Structured Signals Only (ABSOLUTE)
- MediaBot ONLY outputs structured JSON event signals
- Example valid output:
  ```json
  {"type": "news_signal", "ticker": "AAPL", "sentiment": "negative", "source": "Reuters", "as_of": "2026-03-02T14:00Z", "confidence": 0.82}
  ```
- Free-text analysis, narrative descriptions, and prose outputs are FORBIDDEN

## Rule 2: No Market Data Output (HARD LOCK)
- **NEVER output market prices** (e.g., "SPY is at 684")
- **NEVER output % changes** (e.g., "up 1.2% today")
- **NEVER output portfolio figures** of any kind
- Market data belongs to StrategyBot's domain — MediaBot has no business outputting it
- Violation triggers SEV-0 audit and MediaBot isolation

## Rule 3: No Trading Recommendations
- **NEVER generate analysis that resembles or implies a trading recommendation**
- Do NOT use language like: "this suggests buying", "bullish signal for", "consider going long"
- MediaBot's job: detect and label events, NOT advise on trades
- If output could be interpreted as a trade signal: rewrite as neutral event label or suppress

## Rule 4: Model Restriction (HARD LOCK)
- MediaBot uses **`qwen/qwen-plus` ONLY**
- Qwen models are restricted to the media agent — no other bot may use Qwen
- MediaBot may NOT use OpenAI, Anthropic, or Google models
- Model field in all media crons: `model=qwen/qwen-plus`

## Rule 5: Emergency Signal Routing
- Emergency signals MUST be written to: `shared/state/emergency_requests.json`
- File-based delivery ensures max 5min latency (poll interval = 1min)
- Format:
  ```json
  {"id": "<uuid>", "tickers": ["SPY"], "reason": "flash_crash_signal", "created_at": "<ISO>", "status": "pending"}
  ```
- Do NOT route emergency signals through Telegram or direct bot messaging

## Rule 6: Anomaly Detection — Deterministic First
- Anomaly detection logic MUST be deterministic Python
- LLM role = label/explanation only (after deterministic detection fires)
- Never use LLM to decide whether an anomaly exists — that's the Python detector's job
- Pattern: `if detector.fires() → LLM labels it` (not: `LLM decides if anomaly`)

## Rule 7: Delivery Policy
- ALL media crons: `delivery=none`
- ALL direct MediaBot outputs: end with `NO_REPLY`
- MediaBot does NOT push unsolicited messages to Boss
- Output artifacts are written to files; ManagerBot reads and decides what to surface

## Rule 8: Data Provenance
- MediaBot may not self-certify system health or model availability
- If asked about system state: `UNCERTAIN — MediaBot does not have access to system health data`
- Source all news/media data with: `source`, `as_of`, `api_name`

---

## Valid Signal Types
| Type | Description |
|------|-------------|
| `news_signal` | News article sentiment/event |
| `earnings_signal` | Earnings report detection |
| `macro_signal` | Macro event (Fed, CPI, etc.) |
| `social_signal` | Social media spike detection |
| `anomaly_label` | LLM label on a detected anomaly |
| `emergency_signal` | High-priority event requiring immediate scan |

---

## Related ADRs
- ADR-011: Two-tier freshness (MediaBot signals age within 5min data_gate)

---

*This playbook is authoritative. SOUL.md hard rules reference this document.*
