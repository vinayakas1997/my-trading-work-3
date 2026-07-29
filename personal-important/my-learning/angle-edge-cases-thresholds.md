# Angle Edge Cases & Thresholds

How to read the borderline outputs from each angle — the numbers that aren't clear wins or losses.

---

## 1. p-values (Granger Causality, Correlation, ML Model OOS)

| Range | Label | What It Means |
|-------|-------|--------------|
| < 0.01 | Highly significant | Effect is almost certainly real. Trade with confidence. |
| 0.01 – 0.05 | Significant | Standard threshold. Effect is likely real. |
| **0.05 – 0.10** | **Marginally significant** | **Edge case.** Not conclusive. Flag it, monitor it, don't bet on it alone. |
| > 0.10 | Not significant | No evidence of effect. Ignore for now. |

**Example reads:**
- `p=0.065` → "Weak evidence news moves price. Worth watching next month."
- `p=0.18` → "No evidence. News doesn't matter for this stock at this lag."
- `p=0.003` → "Highly significant. Granger causality confirmed."

---

## 2. Sharpe Ratio (Backtesting, Regime Analysis, Portfolio Analysis)

| Range | Label | What It Means |
|-------|-------|--------------|
| < 0 | Negative | Strategy loses money. |
| 0 – 0.5 | Poor | Barely above risk-free. Basically noise. |
| **0.5 – 1.0** | **Decent** | **Edge case zone.** Worth trading but needs monitoring. |
| 1.0 – 2.0 | Good | Real edge. Solid strategy. |
| > 2.0 | Suspicious | Likely overfit or data-mined. Investigate carefully. |

**Key nuance:** A Sharpe of 0.8 in a bull regime may drop to 0.2 in a bear regime. Always check per-regime Sharpe from `regime_analysis`.

---

## 3. Information Coefficient — IC (ML Pipeline, Decay Monitoring, Factor Backtesting)

| Range | Label | What It Means |
|-------|-------|--------------|
| < 0.02 | None | No predictive power. |
| **0.02 – 0.05** | **Weak** | **Edge case.** Barely useful. Combine with other signals. |
| 0.05 – 0.10 | Modest | Tradeable with good execution and risk management. |
| > 0.10 | Strong | Rare for single stocks. Valuable alpha source. |

**OOS IC (Out-of-Sample) is what matters.** In-sample IC is always inflated.

---

## 4. Deflated Sharpe Ratio — DSR (Deflated Sharpe Ratio, Validation & Overfitting)

| Range | Label | What It Means |
|-------|-------|--------------|
| < 0.50 | Likely luck | Your Sharpe is probably random after adjusting for trials. |
| **0.50 – 0.90** | **Uncertain** | **Edge case zone.** Could be skill, could be luck. Needs more data. |
| 0.90 – 0.95 | Promising | Likely genuine, but not conclusive. |
| > 0.95 | Genuine skill | Deflated Sharpe confirms real edge. |

**Key nuance:** DSR depends heavily on `n_trials`. A Sharpe of 1.2 with 5 trials → DSR=0.94. Same Sharpe with 50 trials → DSR=0.72. Check the sensitivity table output.

---

## 5. Overfitting Verdict (Walk-Forward Gap)

| Sharpe Gap (IS − OOS) | Verdict | What It Means |
|----------------------|---------|--------------|
| ≤ 0.3 | LOW risk | Strategy generalizes well. |
| **0.3 – 0.5** | **MODERATE risk** | **Edge case.** Some overfitting. Use with caution. |
| > 0.5 | HIGH risk | Overfit. Look for simpler strategy. |

---

## 6. Health Status (Decay Monitoring)

| Health Score | Status | What It Means |
|-------------|--------|--------------|
| ≥ 3 | HEALTHY | Signal is working. |
| **0 to 3** | **WARNING** | **Edge case.** Signal weakening. Start looking for replacements. |
| -5 to 0 | DECAYED | Signal is no longer reliable. |
| < -5 | CRITICAL | Signal is dead. Stop using it. |

**Key nuance:** The trend matters more than the snapshot. HEALTHY → WARNING → DECAYED sequence is the signal to act, not the absolute score.

---

## 7. News Sentiment Z-Score (News First Analysis)

| Z-Score | Deviation | What It Means |
|---------|-----------|--------------|
| < 1.0 | Normal | Typical news day. Nothing unusual. |
| **1.0 – 2.0** | **Elevated** | **Edge case.** News is somewhat abnormal. Worth checking headlines. |
| 2.0 – 3.0 | High | Unusual news activity. Pay attention. |
| > 3.0 | Extreme | Major event. Likely large price impact. |

---

## 8. Drawdown Attribution (Drawdown Deep-Dive)

| News-Driven % | What It Means |
|--------------|--------------|
| < 30% | Market beta or unexplained. Not news-driven. |
| **30% – 60%** | **Edge case.** Mixed causes. Check specific events. |
| > 60% | Clearly news-driven. Specific headlines caused the loss. |

---

## 9. Cluster Silhouette Score (Shadow Trading)

| Score | What It Means |
|-------|--------------|
| < 0.25 | No real clusters. Patterns are random. |
| **0.25 – 0.50** | **Edge case.** Weak structure. Clusters might be useful. |
| 0.50 – 0.70 | Good separation. Patterns are real. |
| > 0.70 | Strong clusters. Clear behavioral regimes. |

---

## 10. Half-Life Mean Reversion (Pairs Cointegration)

| Half-Life | What It Means |
|-----------|--------------|
| < 2 days | Too fast. Spread reverts before you can execute. |
| **2 – 20 days** | **Tradeable edge case zone.** Fast enough to capture, slow enough to execute. |
| 20 – 60 days | Slow mean reversion. Capital-intensive. |
| > 60 days | Effectively random walk. Not tradeable as mean reversion. |

---

## Quick Reference Card

```
p-value:   <0.01 (strong) | 0.01-0.05 (sig) | 0.05-0.10 (edge) | >0.10 (noise)
Sharpe:    >2.0 (suspect) | 1.0-2.0 (good) | 0.5-1.0 (edge) | <0.5 (poor)
OOS IC:    >0.10 (strong) | 0.05-0.10 (modest) | 0.02-0.05 (edge) | <0.02 (none)
DSR:       >0.95 (skill) | 0.90-0.95 (promising) | 0.50-0.90 (edge) | <0.50 (luck)
WF gap:    <0.3 (low) | 0.3-0.5 (edge) | >0.5 (high)
Health:    >=3 (healthy) | 0-3 (edge) | <0 (decayed)
News z:    <1 (normal) | 1-2 (edge) | >2 (notable)
Silhouette: >0.5 (good) | 0.25-0.5 (edge) | <0.25 (random)
Half-life: 2-20 days (tradeable edge)
```

The real skill is not in reading the green or red zones — it's knowing what to do when you're in the edge case zone.
