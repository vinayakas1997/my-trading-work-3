"""The shared watchlist file is {"tickers": [...], "updated_at": ...}; the universe must be the tickers, not the keys."""

from __future__ import annotations

import json
from types import SimpleNamespace

from vinu_strategy.service import StrategyService


def _resolve(tmp_path, content, inline=None):
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    self = SimpleNamespace(_config=SimpleNamespace(shared_watchlist_path=str(path)))
    cfg = SimpleNamespace(universe={"source": "watchlist", **({"inline": inline} if inline else {})})
    return StrategyService._resolve_universe(self, cfg, None)


def test_the_stock_service_format_gives_its_tickers(tmp_path):
    assert _resolve(tmp_path, {"tickers": ["aapl", "MSFT"], "updated_at": 1}) == ["AAPL", "MSFT"]


def test_an_older_plain_list_still_works(tmp_path):
    assert _resolve(tmp_path, ["AAPL", "NVDA"]) == ["AAPL", "NVDA"]


def test_an_empty_or_unusable_watchlist_falls_back_to_the_inline_list(tmp_path):
    assert _resolve(tmp_path, {"tickers": [], "updated_at": 1}, inline=["TSLA"]) == ["TSLA"]
    assert _resolve(tmp_path, {"unexpected": True}, inline=["TSLA"]) == ["TSLA"]
