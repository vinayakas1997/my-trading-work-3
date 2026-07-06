from __future__ import annotations

from typing import Any

import numpy as np
import pytest


@pytest.fixture
def synthetic_candles() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    np.random.seed(42)
    candles = []
    ground_truth = []

    base_price = 150.0
    start_ts = 1700000000

    for i in range(43200):
        ts = start_ts + i * 60
        drift = 0.0002
        noise = np.random.normal(0, 0.001)
        ret = drift + noise
        base_price *= (1 + ret)

        if i == 1000:
            base_price *= 0.95
            ground_truth.append({"ts": ts, "drop_pct": -5.0, "sentiment": "BEARISH"})
        elif i == 2000:
            base_price *= 0.97
            ground_truth.append({"ts": ts, "drop_pct": -3.0, "sentiment": "BEARISH"})
        elif i == 3000:
            base_price *= 1.03
            ground_truth.append({"ts": ts, "drop_pct": 3.0, "sentiment": "BULLISH"})

        candles.append({
            "bar_ts": ts,
            "open": round(base_price * (1 - 0.0005), 2),
            "high": round(base_price * (1 + 0.001), 2),
            "low": round(base_price * (1 - 0.001), 2),
            "close": round(base_price, 2),
            "volume": int(np.random.randint(100000, 5000000)),
        })

    return candles, ground_truth


@pytest.fixture
def synthetic_articles() -> list[dict[str, Any]]:
    start_ts = 1700000000
    return [
        {"id": "art_001", "sort_ts": start_ts + 1000 * 60, "headline": "AAPL revenue miss",
         "tickers": ["AAPL"], "sentiment": "BEARISH", "sentiment_score": -5,
         "impact": "high", "thread_id": ""},
        {"id": "art_002", "sort_ts": start_ts + 2000 * 60, "headline": "iPhone supply cut",
         "tickers": ["AAPL"], "sentiment": "BEARISH", "sentiment_score": -4,
         "impact": "medium", "thread_id": ""},
        {"id": "art_003", "sort_ts": start_ts + 3000 * 60, "headline": "AAPL beats earnings",
         "tickers": ["AAPL"], "sentiment": "BULLISH", "sentiment_score": 5,
         "impact": "high", "thread_id": ""},
        {"id": "art_004", "sort_ts": start_ts + 4000 * 60, "headline": "Market update",
         "tickers": ["AAPL", "MSFT"], "sentiment": "NEUTRAL", "sentiment_score": 0,
         "impact": "low", "thread_id": ""},
    ]
