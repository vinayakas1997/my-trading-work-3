"""v2 audit IA1: a failed bars fetch is an error row (not a 'completed' empty run); a failed news fetch is flagged."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from vinu_initial_analysis.runner import AngleRunner
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.parquet import AngleStorage


class _Mod:
    @staticmethod
    def compute(symbol, bars=None, news=None, from_ts=None, to_ts=None, time_format=None):
        if bars is None or len(bars) == 0:
            return pd.DataFrame()
        return pd.DataFrame([{"symbol": symbol, "n_news": len(news or []), "n_bars": len(bars)}])


class _BadPrice:
    def get_candles(self, *a, **k):
        raise ConnectionError("stock-price down")


class _EmptyPrice:
    def get_candles(self, *a, **k):
        return []


class _GoodPrice:
    def get_candles(self, *a, **k):
        return [{"bar_ts": 1, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]


class _BadNews:
    def get_ticker_news(self, *a, **k):
        raise ConnectionError("news down")


def _runner(tmp, **clients):
    Path(tmp).mkdir(parents=True, exist_ok=True)
    r = AngleRunner(AngleStorage(tmp), RunLog(Path(tmp) / "runs.db"), **clients)
    r._angles = [{"name": "fake", "spec": {"time_formats": ["1D"]}}]
    r._import_compute = lambda name: _Mod
    return r


def test_a_failed_bars_fetch_is_an_error_not_an_empty_completed_run(tmp_path):
    r = _runner(str(tmp_path), price_client=_BadPrice())
    out = r.run("AAPL", angle_names=["fake"])
    assert out["fake"]["status"] == "error" and "stock-price down" in out["fake"]["error"]
    assert not r._run_log.has_existing_run("AAPL", "fake", None, None, granularity="1D")


def test_genuinely_no_bars_is_still_the_old_empty_completed_result(tmp_path):
    out = _runner(str(tmp_path), price_client=_EmptyPrice()).run("AAPL", angle_names=["fake"])
    assert out["fake"]["status"] == "completed" and out["fake"]["row_count"] == 0


def test_a_failed_news_fetch_is_flagged_on_the_result_and_a_good_one_is_not(tmp_path):
    out = _runner(str(tmp_path / "a"), price_client=_GoodPrice(), news_client=_BadNews()).run("AAPL", angle_names=["fake"])
    assert out["fake"]["status"] == "completed" and "news down" in out["fake"]["news_fetch_failed"]
    out = _runner(str(tmp_path / "b"), price_client=_GoodPrice()).run("AAPL", angle_names=["fake"])
    assert "news_fetch_failed" not in out["fake"]


class _PlaceholderMod:
    """Like drawdown_deep_dive / backtesting_44_metrics: answers empty bars with a
    placeholder row instead of an empty frame."""

    @staticmethod
    def compute(symbol, bars=None, news=None, from_ts=None, to_ts=None, time_format=None):
        if bars is None or len(bars) == 0:
            return pd.DataFrame([{"symbol": symbol, "type": "status", "drawdown_count": 0}])
        return pd.DataFrame([{"symbol": symbol, "type": "drawdown", "n_bars": len(bars)}])


def test_no_bars_yet_is_not_recorded_as_a_finished_run_so_it_is_retried_when_bars_arrive(tmp_path):
    """A ticker whose price history is not backfilled yet must not get a stored
    'zero drawdowns' result that blocks the real computation later."""
    r = _runner(str(tmp_path), price_client=_EmptyPrice())
    r._import_compute = lambda name: _PlaceholderMod
    out = r.run("MSFT", angle_names=["fake"])
    assert out["fake"]["row_count"] == 0
    assert not r._run_log.has_existing_run("MSFT", "fake", None, None, granularity="1D")

    r._price_client = _GoodPrice()  # the backfill finished
    out = r.run("MSFT", angle_names=["fake"])
    assert out["fake"]["row_count"] == 1
    assert r._run_log.has_existing_run("MSFT", "fake", None, None, granularity="1D")


def test_an_explicit_single_timeframe_trigger_still_gets_its_answer_with_no_bars(tmp_path):
    """The v1 trigger route polls one exact run id; it must still resolve (with the
    module's own placeholder row), not stay 'not_found' forever."""
    r = _runner(str(tmp_path), price_client=_EmptyPrice())
    r._import_compute = lambda name: _PlaceholderMod
    out = r.run("MSFT", angle_names=["fake"], time_format="1D", run_id="trigger-run-1")
    assert out["fake"]["row_count"] == 1
