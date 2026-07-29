# LLM Forecasting Validation — Synthesized vs. Real Market Benchmarking

This document details **Step 2 (Research-Simulations)** of the architecture: how to quantitatively benchmark, score, and validate the LLM's price-forecasting capabilities before using them in any strategy or money simulations.

---

## 1. Overview: The Zero-Trust Model

We do not treat the LLM as a "god" model that makes perfect predictions. Instead, we treat the LLM as a **system under test**. 

We use the deterministic mathematical output of the `trend_lifecycle` analysis (from Step 1) as the **scoring engine** to cross-examine the LLM's predictions against actual market reality. This allows us to map exactly **when** the LLM is accurate and **when** it fails.

```
                      ┌──────────────────┐
                      │   Real Candles   │
                      │ (Price History)  │
                      └────────┬─────────┘
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
          [Real Market]               [LLM Generator]
      (What actually happened)    (Predicts future candles)
                 │                           │
                 ▼                           ▼
       [Real Trend Lifecycle]    [Synthesized Trend Lifecycle]
         (Peaks / Troughs)           (Peaks / Troughs)
                 │                           │
                 └─────────────┬─────────────┘
                               ▼
                     [Cross-Comparison]
                 (Scores accuracy & timing)
                               ▼
                [LLM Reliability Database]
           "Believable in Basing. Fails in Topping."
```

---

## 2. Validation Workflow

For any historical validation timestamp $T$:

### Step A: Feed Lookback & Generate Future
1. Extract the historical candles leading up to $T$ (e.g., a lookback context of 512 bars).
2. Feed these candles into the LLM forecasting model (e.g., `Kronos-base`).
3. Request the LLM to generate a synthetic price path for the next $N$ bars (e.g., a 20-bar forecast).

### Step B: The Mirror Analysis
We run the exact same deterministic peak/trough and indicator calculations on both series:
1. **Real Trend Lifecycle:** Extract the actual peaks, troughs, and trend stages from the real market data that followed $T$.
2. **Synthesized Trend Lifecycle:** Extract the peaks, troughs, and trend stages from the LLM-generated synthetic candles.

### Step C: Cross-Comparison Scoring
We align the two lifecycle models and calculate key performance indicators (KPIs):
* **Peak Alignment Score:** Did the LLM forecast a peak where a real peak actually formed? (Tolerance: $\pm 2$ bars).
* **Drawdown Magnitude Error:** `abs(Real Drawdown % - Synthesized Drawdown %)`
* **Recovery Timing Error:** `abs(Real Recovery Bars - Synthesized Recovery Bars)`
* **Stage Concordance:** Did the LLM correctly classify the lifecycle transition stage (e.g., Topping $\rightarrow$ Downtrend)?

---

## 3. The LLM Reliability Database

The comparison scores are recorded in a permanent run log. This log builds a matrix of **conditional trust**:

```
                       LLM FORECAST ACCURACY MATRIX
┌──────────────────────┬─────────────────┬──────────────────┬─────────────────┐
│ Trend Regime (1D)    │ Peak Detection  │ Drawdown Error   │ Action          │
├──────────────────────┼─────────────────┼──────────────────┼─────────────────┤
│ Basing (Consolidate) │ 88% Accuracy    │ ± 1.2%           │ BELIEVE SIGNAL  │
│ Uptrend (Steady)     │ 72% Accuracy    │ ± 1.9%           │ BELIEVE SIGNAL  │
│ Topping (Exhaustion) │ 31% Accuracy    │ ± 5.4%           │ IGNORE SIGNAL   │
│ Downtrend (Panics)   │ 15% Accuracy    │ ± 8.2%           │ IGNORE SIGNAL   │
└──────────────────────┴─────────────────┴──────────────────┴─────────────────┘
```

* **Core Rule:** The LLM's forecasts are only trusted when the current market regime matches a state where the LLM has historically demonstrated high accuracy and low error.

---

## 4. Integration into Strategy & Money Simulations

Once the reliability profile is established, we move to the execution phase in **Research-Simulations**:

* **Conditional Signal Triggering:** Strategies will discard LLM forecasts if they are generated during low-accuracy regimes (e.g., Downtrends).
* **Dynamic Sizing / Position Sizing:** Leverage and position sizes are scaled proportionally to the LLM's historical accuracy in the current regime.
* **Paper Trading & Performance Accounting:** Simulates trading in a sandbox environment to track cumulative returns, maximum drawdowns, and transaction costs before promoting any strategy to `Live-Trading`.

---

## 5. Model Reference: Kronos-base

* **Model Name:** `NeoQuasar/Kronos-base`
* **Hugging Face Model Link:** [NeoQuasar/Kronos-base](https://huggingface.co/NeoQuasar/Kronos-base)
* **Official GitHub Repository:** [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)
* **Model Type:** Financial time-series foundation model pre-trained on multi-dimensional K-line (candlestick OHLCV) data.
* **Architecture:** Autoregressive decoder-only Transformer (~102.3M parameters) with a specialized hierarchical discrete K-line tokenizer (`Kronos-Tokenizer-base`). Max context length is 512 tokens.
