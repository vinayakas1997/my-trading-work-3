---
name: sentiment-analysis
description: News sentiment, social media intelligence, and behavioral finance signals
category: sentiment
---

## Sentiment Analysis

### Data Sources

| Source | Type | Coverage |
|--------|------|----------|
| News APIs | Structured news | Global, real-time |
| Twitter/X | Social media | Retail sentiment |
| Reddit (r/wallstreetbets) | Forum | Meme stock signals |
| SEC EDGAR | Filings | 10-K/10-Q sentiment |
| Earnings call transcripts | Audio → text | Management tone |

### Sentiment Metrics

| Metric | Calculation | Interpretation |
|--------|-------------|----------------|
| Bullish Ratio | (positive - negative) / total | > 0.3 = bullish |
| Fear & Greed | Composite of 7 indicators | < 25 = fear, > 75 = greed |
| Put/Call Ratio | put volume / call volume | > 1.0 = bearish |
| VIX | Implied vol SPX 30d | > 30 = fear, < 15 = complacency |
| Short Interest | shares short / float | > 20% = high short risk |

### Behavioral Finance Biases
- **Recency bias**: over-weighting recent events
- **Confirmation bias**: seeking information that confirms position
- **Herding**: following the crowd into crowded trades
- **Anchoring**: fixating on a specific price level
- **Disposition effect**: selling winners too early, holding losers too long

### Backtest Integration
- Add sentiment as a filter: `sentiment_score > 0.3`
- Regime detection: high fear → mean reversion, high greed → momentum
- Event-driven: trade around earnings/CPI/FOMC with sentiment confirmation
