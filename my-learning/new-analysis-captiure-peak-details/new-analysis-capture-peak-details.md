# Trend Lifecycle Registry — Peak/Trough Capture with Pattern Matching

Instead of generic factor IC decay, capture a full fingerprint at every peak and trough, build a pattern library, and predict drawdowns with percentage thresholds.

---

## 1. Time Formats

| Format | Use For | Min Data Needed | Min Drop Threshold |
|--------|---------|-----------------|-------------------|
| 15min | Day-trading peaks, session dips | ~2 weeks (1000+ candles) | -2% or 2x ATR |
| 1H | Multi-day swing peaks | ~3 months | -3% or 2x ATR |
| 4H | Weekly trend structure | ~6 months | -4% or 2x ATR |
| 1D | Long-term trend lifecycle | ~2 years | -5% or 2x ATR |

Fixed. These never change.

### Dynamic ATR-Based Thresholds (Recommended)

> Instead of hard-coded percentages, use `Min Drop = 2 * ATR_14 / Close` at the peak. This adapts automatically to volatile regimes (earnings, macro events) and prevents false peak detections during high-volatility noise. For example, if ATR_14 = $3.50 and Close = $180, min drop = 2 * 3.50 / 180 = -3.9%. The hard-coded % above serves as an absolute minimum floor.

---

## 2. Peak / Trough Detection

```
For each time format:
  1. Rolling window lookback = 20 bars
  2. Peak = price > max(previous 20) AND next 3 bars confirm (close < peak_close)
  3. Trough = price < min(previous 20) AND next 3 bars confirm (close > trough_close)
  4. Skip if drop from peak < threshold (max of hard-coded % floor or 2x ATR)
```

### ⚠️ 3-Bar Confirmation Lag — Important

The 3-bar confirmation means you detect the peak 3 bars after it actually occurred. Your exit triggers (trailing stop, RSI-based exit) must execute at **t+3** (detection bar), not retrospectively at **t** (peak bar).

| Format | Lag Time | Impact |
|--------|----------|--------|
| 15min | 45 min | Acceptable for day trades |
| 1H | 3 hours | Minimal for swing trades |
| 4H | 12 hours | Negligible |
| 1D | 3 days | Use ATR thresholds to account for slippage |

In practice, this means the actual drawdown you experience from peak to detection is larger than the drop threshold. Account for this by widening the trailing stop by 1 ATR from the estimated value.

---

## 3. Snapshot at Every Peak (All Indicators — One Flat Row Per Peak)

At every detected peak, compute and store **ALL available indicators** as a single flat feature vector. This serves both KNN matching (immediate) and ML model training (future).

### Columns Captured

| Group | Columns |
|-------|---------|
| **Identity** | peak_id, symbol, time_format, peak_ts, peak_close, peak_high, peak_low, peak_volume |
| **Context** | bar_index, session_label, day_of_week, hour, return_from_prev_trough |
| **Trend** | sma_9, sma_21, sma_50, sma_200, ema_12, ema_26, macd, macd_signal, macd_hist, adx_14 |
| **Momentum** | rsi_14, rsi_7, cci_20, williams_r_14, stoch_k_14, stoch_d_14 |
| **Volatility** | atr_14, bb_upper_20, bb_mid_20, bb_lower_20, bb_width_pct, volatility_20d |
| **Volume** | obv, volume_ratio_20, volume_zscore_20, cmf_20 |
| **Price Action** | daily_return, high_low_spread, close_sma_9_pct, close_sma_50_pct, close_sma_200_pct |
| **Timing / Structure** | runup_bars, internal_dips_count, relaxation_bars |
| **Candle Shape** | upper_wick_pct, body_size_pct |
| **Trend Health** | adx_slope_5, rsi_divergence |
| **Overextension** | dist_to_sma_50_pct, dist_to_sma_200_pct, peak_ratio |
| **Normalized** | All the above also stored as z-scores across the library for KNN |

Every column is computed using **fixed periods that never change** (e.g., RSI_14 always means RSI_14). This guarantees that Peak_A and Peak_B are directly comparable.

---

## 4. Why These 11 Additional Columns

These 11 columns capture the **structure, health, and texture** of the trend — things that raw price candles and standard indicators miss. Each serves a specific purpose in making pattern matching more precise.

### Timing / Structure (3 columns)

These measure the speed and stability of the rally that led to the peak. Two peaks with identical RSI and MACD can behave very differently if one took 5 bars to reach (parabolic) vs 100 bars (steady accumulation).

| # | Column | Formula | Why |
|---|--------|---------|-----|
| 1 | `runup_bars` | Bars from previous trough to this peak | Separates parabolic spikes (5 bars) from steady uptrends (100 bars). Parabolic peaks are far more likely to reverse sharply. |
| 2 | `internal_dips_count` | Count of bars where `close < low_of_prev_bar` during runup | Measures trend stability. Zero dips = straight line up (fragile, prone to snap). Multiple dips = stair-step uptrend (healthy, more sustainable). |
| 3 | `relaxation_bars` | Count of consolidation bars right before the peak signal | Detects "V-top" (0 bars — sharp peak) vs "M-top" or rounding top (15+ bars of distribution before breakdown). Longer consolidation = more overhead supply. |

### Candle Shape (2 columns)

The shape of the specific candle that forms the peak tells you if sellers actively rejected the high. Two peaks at $185 can be very different: one with a tiny wick (sellers absent), another with a long upper wick (sellers aggressively fading the high).

| # | Column | Formula | Why |
|---|--------|---------|-----|
| 4 | `upper_wick_pct` | `(High − max(Open, Close)) / (High − Low)` | Large value (near 1.0) = shooting star / strong rejection at high. Small value (near 0) = price closed near high, no seller resistance yet. |
| 5 | `body_size_pct` | `abs(Close − Open) / (High − Low)` | Small value (near 0) = Doji / indecision at the peak. Trend suddenly lost conviction. Large value = strong directional bar (breakout or exhaustion). |

### Volume Exhaustion (1 column)

Major tops often happen on climactic volume. A peak with normal volume is less concerning than a peak where volume spiked 3x the average.

| # | Column | Formula | Why |
|---|--------|---------|-----|
| 6 | `volume_zscore_20` | `(Volume − Mean_Vol_20) / Std_Vol_20` | High z-score ( > 2.0 ) = blow-off volume top. Low z-score = normal peak without exhaustion. Blow-off tops are more likely to reverse hard. |

### Overextension (2 existing + 1 new)

These don't need separate storage — `close_sma_50_pct` and `close_sma_200_pct` already exist in the schema. The new addition is `peak_ratio`.

| # | Column | Formula | Why |
|---|--------|---------|-----|
| 7 | `dist_to_sma_50_pct` | `(Close − SMA_50) / SMA_50` | Already in schema. Measures short-term overextension. 15% above SMA_50 is much more fragile than 2% above. |
| 8 | `dist_to_sma_200_pct` | `(Close − SMA_200) / SMA_200` | Already in schema. Measures long-term bubble risk. |
| 9 | `peak_ratio` | `peak_close / previous_peak_close` | Near 1.0 (0.99–1.01) = Double Top (strong resistance). < 0.98 = Lower High (bearish). > 1.02 = Higher High / Breakout (trend continuation likely). Double tops are the most reliable reversal pattern. |

### Trend Health (2 columns)

These capture whether the underlying trend is accelerating or dying. Standard indicators at a single point in time miss this — you need to compare current values to recent values.

| # | Column | Formula | Why |
|---|--------|---------|-----|
| 10 | `adx_slope_5` | `ADX_14[t] − ADX_14[t−5]` | Positive = trend accelerating (peak may continue). Negative = trend dying (reversal imminent). ADX > 25 + falling slope is one of the strongest reversal signals. |
| 11 | `rsi_divergence` | `RSI_14 at current peak − RSI_14 at previous peak` | Negative value with price making higher high = **bearish divergence**. The single most reliable non-price reversal signal. RSI alone at 70 says "overbought." RSI divergence at 65 while price is at a new high says "this trend is structurally weak." |

### Summary

Without these columns, the pattern matcher sees two peaks with identical RSI=72, SMA_50=+5%, MACD positive — and treats them as the same. With these columns, it sees:

- Peak A: runup_bars=5, internal_dips=0, relaxation=0, upper_wick=0.8, volume_zscore=3.2, rsi_divergence=-4
- Peak B: runup_bars=80, internal_dips=6, relaxation=4, upper_wick=0.2, volume_zscore=0.5, rsi_divergence=+2

Pattern A says **parabolic blow-off top** (high probability of sharp reversal). Pattern B says **healthy pullback within an uptrend** (low probability of major drawdown). The columns make this distinction possible.

---

## 6. Normalization (Mandatory Before Pattern Matching)

Raw indicator values have different scales and will distort Euclidean distance. Normalize all features to be scale-invariant:

| Group | Raw Value | Normalized Formula |
|-------|-----------|-------------------|
| **Trend (SMA, MACD)** | SMA_9 = $185 | `(SMA_9 - Close) / Close` → % deviation from price |
| **Volatility (ATR, BB)** | ATR_14 = $3.50 | `ATR_14 / Close` → relative volatility |
| **Volume (OBV, Volume)** | Volume = 12M | `Volume / SMA_Volume_20` → volume ratio, or rolling z-score |
| **Momentum (RSI, CCI)** | RSI_14 = 72 | Already bounded (0–100, -100–100) but Min-Max scale to [0,1] |
| **Price (OHLC)** | Close = $180 | `Close / SMA_50` → relative price level |

All normalized values must also be standardized (z-score) across the historical library so no single feature dominates the distance calculation.

---

## 7. Outcome Tracked Per Peak

```
peak_id
peak_price
peak_ts
→ trough_price
→ trough_ts
→ drawdown_pct
→ recovery_time_bars
→ next_peak_price
→ total_swing_pct
```

---

## 8. Pattern Matching (When a New Peak Forms)

1. Take the full indicator snapshot of the new peak (all columns)
2. Compare against all historical peaks using **weighted Euclidean distance** on normalized indicators
3. Return top-5 closest matches with their outcomes

---

## 9. Trade Signal Output

```
PREDICTION:
  Current state: NEW_PEAK detected at $182.40 (1H)
  Confidence: HIGH (3 strong pattern matches)
  Estimated drawdown: -6% to -9% over next 5-12 days
  Suggested action:
    → Set trailing stop at -4% from peak ($175.10)
    → Book full profit if price reaches -3% from peak on RSI < 30
    → Re-entry signal: price recovers above SMA_50 with RSI > 40

PATTERN LIBRARY STATUS:
  47 peaks recorded | 8 unique pattern clusters
  Most reliable: "Overbought with declining volume" (12 matches, 92% triggered drawdown)
  Least reliable: "Low-vol sideways peak" (6 matches, only 33% triggered drawdown)
```

---

## 10. Percentage Exit Rules (How to Trade It)

| Cluster Pattern | Avg Drawdown | Exit Trigger | Capture |
|----------------|-------------|--------------|---------|
| Overbought + declining volume | -8.2% | Trailing stop at -4% | ~50% |
| SMA_50 breakout fade | -12.1% | Stop at -6% | ~50% |
| Low-vol peak | -3.5% | Don't auto-trade, flag only | — |
| Post-earnings gap up | -15.3% | Stop at -7% | ~50% |

If a cluster has < 3 matches or high variance — don't auto-trade. Flag for manual review.

---

## 11. Summary: What This Angle Produces vs Current

| Current (decay_monitoring) | Proposed (trend_lifecycle) |
|---|---|
| "Factor IC dropped to 0.03 → WARNING" | "New peak at $182 — 3 similar patterns suggest -7% drawdown. Exit at -4%." |
| Academic factor health score | Concrete price action with % thresholds |
| No timing info | Specific: "over next 5-12 days" |
| No pattern memory | Full library of historical peaks with outcomes |
| No trade suggestion | "Set trailing stop at $175.10" |

---

## 12. Implementation Plan — `trend_lifecycle` Angle

### File Structure

```
angles/trend_lifecycle/
├── spec.yaml              # Angle metadata
├── compute.py             # Main entry point — orchestrates all steps
├── peaks.py               # Peak/trough detection (custom rolling-window)
├── snapshots.py           # Capture ALL indicators at peak moment (flat feature vector)
├── patterns.py            # Pattern library persistence, normalization, KNN matching
├── lifecycle.py           # Stage classification (uptrend / topping / downtrend / basing)
└── signals.py             # Generate trade signals with confidence + % thresholds
```

### How It Runs

1. **Load pattern library** — reads all historical `type=snapshot` rows via `AngleStorage.read(symbol, "trend_lifecycle")`. Library accumulates naturally across runs (no extra storage code needed).

2. **Detect peaks/troughs** — custom rolling-window (`max(previous 20)` + `next 3 confirm`). Guarantees peak detection at the edge with zero boundary issues.

3. **Capture snapshot** — at every new peak, compute ALL technical indicators (21+ indicators) + session info + price context. Store as a single flat row. This row IS the feature vector.

4. **Normalize & match** — z-score normalize all features across the library. KNN cosine similarity (top-5 matches). Scipy fallback, sklearn optional.

5. **Classify stage** — uptrend / topping / downtrend / basing based on recent peaks/troughs.

6. **Generate signals** — "New peak — 3 similar patterns avg -7% drawdown. Set stop at -4%."

7. **Write results** — Parquet via `AngleStorage`. Types: `snapshot`, `match`, `lifecycle`, `signal`, `summary`.

### Storage Format (Parquet Table)

One table per symbol per angle run. Key columns:

| Column | Type | Description |
|--------|------|-------------|
| type | str | snapshot / match / lifecycle / signal / summary |
| peak_ts | int | Timestamp of peak bar |
| peak_close | float | Price at peak |
| sma_9, sma_21, ... | float | All indicator values at peak |
| rsi_14, rsi_7, ... | float | All momentum values at peak |
| atr_14, bb_width_pct, ... | float | All volatility values at peak |
| runup_bars | int | Candles from previous trough to this peak |
| internal_dips_count | int | Counter-trend bars during runup |
| relaxation_bars | int | Consolidation bars before peak confirmation |
| upper_wick_pct | float | Seller rejection at peak candle |
| body_size_pct | float | Indecision at peak candle (Doji) |
| volume_zscore_20 | float | Volume exhaustion (blow-off top) |
| peak_ratio | float | Double top vs breakout (0.99–1.01 = double top) |
| adx_slope_5 | float | Trend accelerating (+) or dying (-) |
| rsi_divergence | float | Bearish divergence if negative + higher high |
| drawdown_pct | float | Outcome: drawdown after this peak |
| recovery_time_bars | int | Outcome: bars to recover |
| confidence | float | Signal confidence (0-1) |
| signal_type | str | book_profits / hold / re-enter / manual_review |

### Why Store ALL Indicators?

| Use Case | Benefit |
|----------|---------|
| **KNN matching (today)** | Pick any subset of normalized indicators as features. Changes don't require recomputing data. |
| **ML model (tomorrow)** | Use ALL columns as features, `drawdown_pct` as target. Model finds predictive combinations automatically — no manual indicator selection needed. |
| **Backtesting** | Can test different feature sets against the same historical library without recomputing. |
| **Consistency** | Indicators computed once with fixed periods. Every peak is comparable to every other peak forever. |

### Dependencies

- `scipy` — already installed (peak detection + cosine distance fallback)
- `scikit-learn` — optional (NearestNeighbors). Pure scipy fallback provided.

### Changes Outside This Angle

| File | Change |
|------|--------|
| `runner.py` | None — auto-discovers new folder |
| `catalog/angles.yaml` | Optional — add entry for docs |
| `pyproject.toml` | None — scipy already present |
| `AngleStorage` | None — already handles all angles |

---

## 13. Visualization Dashboard — Interactive Trend Lifecycle Inspector

A standalone, single-file HTML report for visually inspecting peak/trough patterns, indicator snapshots, and KNN matches. Zero server dependencies — double-click to open in any browser.

### Layout

```
┌──────────────────────────────────────────────┬──────────────────────────────┐
│                                              │                              │
│          INTERACTIVE PRICE CHART             │     DYNAMIC FEATURE          │
│                                              │        INSPECTOR             │
│  [Candlesticks + SMA_50 + SMA_200]           │                              │
│                                              │  [Click a peak/trough]       │
│         ▼ (Peak — red down arrow)            │  • Timing & Structure        │
│    ▲───▲                                     │  • Candle Shape              │
│   /     \                                    │  • Volume Exhaustion         │
│  /       \                                   │  • Overextension             │
│ ─         ▼                                  │  • Trend Health              │
│            ▲ (Trough — green up arrow)        │  • KNN Top-5 Matches         │
│                                              │  • Suggested Action          │
└──────────────────────────────────────────────┴──────────────────────────────┘
```

### Compilation Script

A Python script that:
1. Reads the stock's OHLCV Parquet (price candles)
2. Reads `trend_lifecycle` Parquet (peaks, troughs, snapshots, matches, signals)
3. Merges extrema markers with indicator snapshots at matching timestamps
4. Serializes everything into JSON embedded in an HTML template
5. Writes `dashboard.html` to the stock's output directory

### Chart (Left 70%)

- **Library:** TradingView Lightweight Charts (CDN-loaded, no install)
- **Candlesticks:** OHLC with volume bars below
- **Overlays:** SMA_50 line, SMA_200 line
- **Markers:** Red down-arrows at detected peaks, green up-arrows at troughs
- **Interactivity:** Click any marker → dispatches timestamp to right panel

### Feature Inspector (Right 30%)

When a peak/trough marker is clicked:

| Section | Columns Displayed |
|---------|------------------|
| **Timing & Structure** | runup_bars, internal_dips_count, relaxation_bars |
| **Candle Shape** | upper_wick_pct, body_size_pct |
| **Volume Exhaustion** | volume_zscore_20 |
| **Overextension** | close_sma_50_pct, close_sma_200_pct, peak_ratio |
| **Trend Health** | adx_slope_5, rsi_divergence, rsi_14 |
| **Volatility** | atr_14, bb_width_pct |

### KNN Matches (Right Panel Bottom)

- **Top-5 closest historical peaks** with similarity % (cosine)
- Each shows: matching peak date, similarity score, `drawdown_pct` that followed, `recovery_time_bars`
- **Suggested action** from the signal (e.g. "Set trailing stop at -4%")

### Aesthetics

- Dark theme (slate grays, deep blues)
- Green for troughs/support, red/amber for peaks/resistance
- Modern sans-serif font (loaded from CDN)
- Smooth scrolling, zero lag

### Output Location

```
data/features/runs/{run_id}/trend_lifecycle/dashboard.html
```

Or alongside the Parquet output per symbol:

```
{data_root}/{symbol}/trend_lifecycle/dashboard.html
```

A compilation helper function in the angle's `signals.py` or a standalone `compile_dashboard.py` script will generate it post-run.
