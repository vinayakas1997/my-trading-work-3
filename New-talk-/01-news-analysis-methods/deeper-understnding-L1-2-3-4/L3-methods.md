---
name: L3-methods
status: discussion-phase
purpose: detail of Level 3 — news text + stock price, statistics only (no predictive ML). Links news to price with event-study methodology and statistical tests. Produces evidence and ground-truth labels.
---

# L3 — News Text + Stock Price: Methods (Statistics, No ML)

## What L3 is

The event-study / statistical layer. It links news to price *without building a
predictive model*. Output = evidence (which news types actually move prices) and
ground-truth labels (which news events produced significant abnormal returns).

## Method families

### 1. Event study methodology

The core mechanism. Standard reference: Brown & Warner; Kothari & Warner,
"Econometrics of Event Studies".

1. Estimate a normal-return model (market model) over a pre-event estimation window
2. Abnormal return = actual − expected in the event window
3. Cumulate into CAR (cumulative abnormal return)
4. Test significance of the CAR

### 2. Timestamp → price alignment (the critical operational detail)

- News before market close → event date = that day
- News after close → event date = the **next trading day**
  (PLOS biopharma study searches up to 5 calendar days to find the next valid trading day)
- Session-aware windows: truncate the event window at session boundaries
- Trading-day calendar: weekends and holidays map to the next trading day

### 3. Conditional statistics

- Group news by keyword category / event type → average abnormal return per category
- Hit rate of direction per category (how often does up-news → up-price)
- Statistical significance of the differences between categories

### 4. Granger causality

- Does news volume / news sentiment *precede* returns?
- Test whether news time series adds predictive power for price beyond price's own history

### 5. Leak vs surprise detection

- Pre-event CAR (−2, −1) vs post-event CAR (0, +1)
- Same sign → candidate **leak** (prices moved before the news)
- Opposite sign → candidate **surprise**

### 6. Baseline comparison

- News-day return distribution vs normal-day return distribution
- Abnormal-return methodology is the formal version of this

### 7. Volatility / volume response

- Does news change realized volatility?
- Does news change trading volume?
- News density vs volume/volatility relationship

## Ground-truth labels produced

- `ar_significant`: was the abnormal return statistically significant?
- `car_1h` / multi-window CAR: magnitude of cumulative reaction
- Event-window labels usable as ML targets at L4

## What L3 feeds

- **Evidence**: which news features (from L1/L2) are worth keeping for L4
- **Ground-truth labels**: `ar_significant`/`car_1h` become the targets for L4 prediction

## This project already implements most of L3

- `impact.py`: real Brown & Warner market-model abnormal returns vs SPY,
  `ar_significant` / `car_1h` labels
- `_market_hours.py`: NYSE calendar, session classification, session-aware truncation
- `significance_model.py`: leak-safe XGBoost classifier for magnitude/surprise
- `granger.py`: Granger causality test
- `correlation.py`: Pearson correlation, lag analysis
- `novelty.py`: TF-IDF novelty scoring

The L3 machinery is genuinely rigorous. The weakness is upstream — the feature
(disproven sentiment score) being fed into it. L1/L2 must supply better features.
