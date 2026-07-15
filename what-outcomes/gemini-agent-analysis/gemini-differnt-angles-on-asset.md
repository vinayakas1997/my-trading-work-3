# Advanced Quantitative Study Angles (Gemini Contribution)

These 5 advanced quantitative study angles and their sub-dimensions represent proposed additions to the asset research pipeline, building on top of the platform's core news, technical, and backtesting layers.

---

## ANGLE 20: Options Market & Implied Volatility (IV) Skew
**Question:** What is the derivatives market pricing in for this asset?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Implied Volatility Term Structure | Short-term vs. long-term IV pricing to detect upcoming catalyst volatility (e.g., earnings spikes) | Yet to be implemented |
| IV Skew / Smile | Pricing delta between OTM puts and calls (measures downside hedging demand) | Yet to be implemented |
| Gamma Exposure (GEX) | Net options market maker gamma exposure, which acts as price magnets or accelerators | Yet to be implemented |
| Put/Call volume ratio | Shifts in trading volumes of bearish puts relative to bullish calls | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
*   **Status**: *Yet to be implemented*.
*   **Details**: The [vinu-stock-price](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-stock-price/) package uses Alpaca and Polygon clients which support option data feeds, but no Option OHLCV/GEX ingestion pipeline or option analytics engine exists yet in the simulator.

**Example:** "AAPL: Put/Call ratio spiked to 1.34 with negative dealer GEX at the $180 strike, indicating downside momentum acceleration risk."

---

## ANGLE 21: Macroeconomic & Policy Sensitivity
**Question:** How does this asset respond to macroeconomic policy releases and rate changes?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| FOMC day excess return | Statistical returns & volatility profile on Central Bank policy announcement days | Yet to be implemented |
| Economic print betas | Sensitivity regression against NFP (employment) and CPI (inflation) surprises | Yet to be implemented |
| Macro factor exposures | Multi-factor correlation to crude oil, currency indexes (DXY), and 10Y-2Y yield spreads | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
*   **Status**: *Yet to be implemented*.
*   **Details**: The platform currently lacks database schemas, scheduled ingestors, and event databases to fetch and align macroeconomic calendars (like CPI or FOMC releases) with asset price series.

**Example:** "TSLA: Extreme macro-beta of 1.45 to interest rate curve shifts, underperforming significantly during rising-yield environments."

---

## ANGLE 22: Crowding & Market Liquidity Dynamics
**Question:** Is this asset crowded, and what is its transaction liquidity risk under stress?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Short Float & DTC | Total float shorted (%) and Days-to-Cover (DTC) to identify short squeeze thresholds | Yet to be implemented |
| Institutional holding velocity | Velocity of ownership shifts (institutional accumulation vs. retail distribution) | Yet to be implemented |
| Bid-ask spread expansion | Intraday volatility of spread transaction cost under high volume stress | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
*   **Status**: *Yet to be implemented*.
*   **Details**: Bid-ask spread volatility and short interest metrics are not captured by the current daily candle/OHLCV data ingestors in [vinu-stock-price](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-stock-price/).

**Example:** "GME: Short interest at 22% of float with 12 days-to-cover, indicating high systemic short squeeze risk."

---

## ANGLE 23: Cointegration & Supply Chain Relationships
**Question:** How does this asset move relative to its immediate economic network?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Pairwise cointegration | Identification of stationary pricing spreads with sector peers for pairs-trading spreads | Partially present |
| Supply chain lead-lag | Delay offsets where hardware/supplier price moves predict downstream manufacturer moves | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
*   **Status**: *Partially present*.
*   **Details**: The base correlation math and matrix engines exist in [portfolio.py](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-research/vinu_research/portfolio.py) and [vinu-correlation](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-correlation/), but the specific cointegration testing algorithms (e.g., ADF, Johansen) and corporate supply-chain mapping matrices are yet to be built.

**Example:** "AAPL is cointegrated with supplier TSM with a 3-day lead-lag structure ($r = 0.64$ at 3-day offset)."

---

## ANGLE 24: SEC Filing Sentiment Shifts
**Question:** Are there structural risk modifications hidden in corporate text disclosures?

| Dimension | What You Learn | Status |
|-----------|---------------|--------|
| Section 1A Risk Factor NLP | Year-over-year text similarity indices (cosine similarity) of corporate risk disclosures | Partially present |
| Insider transactions velocity | Aggregated net buy/sell volume and value of corporate insiders (directors/executives) | Yet to be implemented |

**Current Implementation Details & Architecture Gaps:**
*   **Status**: *Partially present*.
*   **Details**: The NLP text enrichment and sentiment calculation pipeline exists in [vinu-news](file:///c:/Users/vinay/Desktop/my-trading-work-3/vinu-components/vinu-news/), but it must be expanded to download and parse SEC EDGAR 10-K/10-Q text documents.

**Example:** "NVDA: Cosine similarity of 10-Q risk sections dropped to 0.72, signaling major new disclosures regarding trade restrictions."
