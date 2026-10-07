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


# ---- model-angle tests need torch, which now lives only in the model-serving image (vinu-models) ----------------------
# Without torch these files cannot even be imported (they import the angle code). They are skipped here with a note in
# the header instead of failing collection; they run, unchanged, in an environment that has torch.
import importlib.util as _ilu
import re as _re

_NEEDS_TORCH = _re.compile(
    r"test_(chronos|dlinear|itransformer|kronos|lpatchtst|lstm|patchtst|tft|timer_timerxl|timesfm|"
    r"tips_regime_aware_transformer)(_backtest)?\.py$|test_orchestration_registry.*\.py$|test_weights\.py$"
)
_TORCH_MISSING = _ilu.find_spec("torch") is None
_IGNORED_FOR_TORCH: list[str] = []


def pytest_ignore_collect(collection_path, config):
    if _TORCH_MISSING and _NEEDS_TORCH.search(collection_path.name):
        if collection_path.name not in _IGNORED_FOR_TORCH:
            _IGNORED_FOR_TORCH.append(collection_path.name)
        return True
    return None


def pytest_report_header(config):
    if _TORCH_MISSING:
        return "torch not installed: model-angle and orchestration-registry tests are not collected (they run where torch is installed)"
    return None


@pytest.fixture(autouse=True)
def _no_real_news_service(monkeypatch):
    """The real news client would call vinu-news (not running in a test) and retry with backoff before giving up, which made
    some tests wait minutes for nothing (problem log O14). Tests that need articles pass their own fake client."""
    from vinu_initial_analysis.clients.news_client import NewsClient

    monkeypatch.setattr(NewsClient, "get_ticker_news", lambda self, *a, **k: [])


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """No test may reach another service. A refused call to localhost is retried against host.docker.internal
    (net.request), which inside the test container reaches the LIVE stack's published ports: the tests were pulling real
    market data and some waited minutes on it (problem log O14). A test that needs HTTP patches the client's `request` itself."""
    import requests

    def _blocked(*args, **kwargs):
        raise requests.ConnectionError("network is blocked in tests")

    monkeypatch.setattr("vinu_initial_analysis.clients.price_client.request", _blocked)
    monkeypatch.setattr("vinu_initial_analysis.clients.news_client.request", _blocked)
