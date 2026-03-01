# Weekly Signal Feedback Loop — Calibration Plan

**Owner:** StrategyBot  
**Updated:** 2026-03-01  
**Trigger:** Weekly, every Sunday 09:00 UTC

---

## 1. When to Run Calibration

| Condition | Action |
|-----------|--------|
| ≥ 30 fills with `win_t5` populated | ✅ Full calibration — update thresholds |
| 15–29 fills | ⚠️ Partial — update priors only, hold thresholds |
| < 15 fills | ❌ Skip — log and wait |

Emergency re-calibration if 10+ fill anomaly streak detected mid-week.

---

## 2. Required Data

Query `trading_firm.signal_outcomes` where:
- `win_t5 IS NOT NULL`
- `recorded_at >= CURRENT_DATE - 30` (rolling 30-day window)

Features: `dip_pct`, `confidence`, `volume_ratio`, `vix_at_entry`  
Label: `win_t5` (BOOL → 1/0)

---

## 3. Calibration Method: Logistic Regression on win_t5

```python
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

features = ['dip_pct', 'confidence', 'volume_ratio', 'vix_at_entry']
X = df[features].fillna(df[features].median())
y = df['win_t5'].astype(int)

scaler = StandardScaler()
model = LogisticRegression(C=1.0, max_iter=500)
model.fit(scaler.fit_transform(X), y)
```

Accept model update only if 5-fold cross-validated **AUC ≥ 0.55**.

---

## 4. Outputs

Write to `strategy/calibration_results_latest.json`:
```json
{
  "run_date": "<ISO>",
  "fills_used": <int>,
  "auc_cv": <float>,
  "feature_coefficients": {...},
  "win_rate_observed": <float>,
  "recommended_confidence_floor": <float>,
  "threshold_change": "increased|decreased|unchanged",
  "notes": "..."
}
```

**Threshold update rule:** If recommended floor differs from current by > 0.02 AND AUC ≥ 0.55 → update `config.json`. Otherwise hold and flag ManagerBot.

---

## 5. Signal Feedback Loop Startup Conditions

Loop is **active** when ALL of the following are true:

1. ≥ 1 fill recorded in `signal_outcomes` with `win_t5 IS NOT NULL`
2. t5-price population job is running (ExecutionService writes t5 price 5 min post-fill)
3. `signal_feedback_schema.json` validated and present
4. First calibration scheduled for after ≥ 30 fills

**Observation-only mode:** < 30 fills (collect data, no threshold changes)  
**Active calibration mode:** ≥ 30 fills (full loop enabled)

---

## 6. Escalation

| Scenario | Action |
|----------|--------|
| Win rate < 40% over 20+ fills | Halt new trades, escalate to ManagerBot |
| AUC < 0.52 for 3 consecutive weeks | Flag feature set for review |
| volume_ratio / vix_at_entry >50% null | Alert InfraBot — data pipeline issue |
