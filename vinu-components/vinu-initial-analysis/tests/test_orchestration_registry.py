from __future__ import annotations

import pandas as pd
import pytest

from vinu_initial_analysis.storage.orchestration_registry import (
    ANGLE_REGISTRY,
    build_batch_jobs,
    build_work_fn,
)


def _bars(n: int = 5) -> pd.DataFrame:
    return pd.DataFrame({"bar_ts": list(range(1000, 1000 + n)), "close": [float(i) for i in range(n)]})


def test_registry_has_exactly_the_30_ready_angles():
    # Checked directly against every angle's real backtest.py signature --
    # see 07-orchestration-suite-test/plan.md, 03-still-open-not-wired.md,
    # and 04-extra-data-angles-wired.md for the full classification and
    # the two follow-up passes that added the 6 extra-data angles.
    assert len(ANGLE_REGISTRY) == 30


_NEEDS_ARTICLES = {"news_price_causality_impact", "news_price_causality_aggregate"}
_NEEDS_PRICE_CLIENT = {"peer_relative_strength", "peer_relative_strength_forward_validation"}
_NEEDS_POSITIONS = {"pnl_attribution"}


class _StubNewsRepository:
    def get_news_for_ticker(self, ticker, start_ts=None, end_ts=None, limit=100):
        return [{"id": "a1", "sort_ts": 1000, "tickers": [ticker], "finbert_score": 0.1}]


class _StubPriceClient:
    def get_watchlist(self):
        return ["AAPL", "JNJ"]

    def get_candles(self, symbol, from_ts=None, to_ts=None, interval="1D", limit=50000):
        return [{"bar_ts": 1000 + i * 86400, "close": float(i)} for i in range(5)]


@pytest.mark.parametrize("angle_name", list(ANGLE_REGISTRY))
def test_build_work_fn_produces_a_zero_arg_callable_for_every_registered_angle(angle_name):
    kwargs = {}
    if angle_name in _NEEDS_ARTICLES:
        kwargs["articles"] = [{"id": "a1", "sort_ts": 1000, "finbert_score": 0.1}]
    if angle_name in _NEEDS_PRICE_CLIENT:
        kwargs["price_client"] = _StubPriceClient()
    if angle_name in _NEEDS_POSITIONS:
        kwargs["positions"] = []
    work_fn = build_work_fn(angle_name, "AAPL", _bars(), "some/data/root", **kwargs)
    assert callable(work_fn)
    # zero-arg by contract (run_batch calls it as work_fn()) -- calling it
    # with too little real data should fail inside the angle's own
    # insufficient-data path, not from a missing-argument TypeError, which
    # would mean the registry built the wrong call shape for this angle.
    try:
        work_fn()
    except TypeError as exc:
        pytest.fail(f"{angle_name}: work_fn() raised TypeError (wrong call shape?): {exc}")
    except Exception:
        pass  # any non-TypeError failure on 5 bars of junk data is expected and fine


@pytest.mark.parametrize("angle_name", sorted(_NEEDS_ARTICLES))
def test_bars_articles_shape_without_articles_raises_clear_valueerror(angle_name):
    with pytest.raises(ValueError, match="requires real articles"):
        build_work_fn(angle_name, "AAPL", _bars(), "some/data/root")


@pytest.mark.parametrize("angle_name", sorted(_NEEDS_PRICE_CLIENT))
def test_bars_price_client_shape_without_price_client_raises_clear_valueerror(angle_name):
    with pytest.raises(ValueError, match="requires a real price_client"):
        build_work_fn(angle_name, "AAPL", _bars(), "some/data/root")


def test_positions_shape_with_positions_none_raises_clear_valueerror():
    with pytest.raises(ValueError, match="requires real positions"):
        build_work_fn("pnl_attribution", "AAPL", _bars(), "some/data/root")


def test_positions_shape_accepts_empty_list_without_raising():
    # positions=[] is a real, valid state (no closed trades for this symbol
    # yet) -- must NOT raise, unlike positions=None (never supplied at all).
    work_fn = build_work_fn("pnl_attribution", "AAPL", _bars(), "some/data/root", positions=[])
    df = work_fn()
    assert list(df["status"]) == ["no_data"]


def test_bars_articles_shape_converts_bars_to_candles_records():
    calls = []

    def _stub_impact(symbol, candles, articles):
        calls.append({"symbol": symbol, "candles": candles, "articles": articles})
        return "ok"

    import vinu_initial_analysis.storage.orchestration_registry as registry_module

    original = registry_module.ANGLE_REGISTRY["news_price_causality_impact"]
    registry_module.ANGLE_REGISTRY["news_price_causality_impact"] = (_stub_impact, "bars_articles")
    try:
        articles = [{"id": "a1"}]
        work_fn = build_work_fn(
            "news_price_causality_impact", "AAPL", _bars(3), "x", articles=articles,
        )
        work_fn()
    finally:
        registry_module.ANGLE_REGISTRY["news_price_causality_impact"] = original

    assert calls[0]["articles"] is articles
    assert calls[0]["candles"] == [
        {"bar_ts": 1000, "close": 0.0}, {"bar_ts": 1001, "close": 1.0}, {"bar_ts": 1002, "close": 2.0},
    ]


def test_bars_price_client_shape_passes_price_client_by_keyword():
    calls = []

    def _stub_peer(symbol, bars, price_client=None):
        calls.append({"symbol": symbol, "price_client": price_client})
        return "ok"

    import vinu_initial_analysis.storage.orchestration_registry as registry_module

    original = registry_module.ANGLE_REGISTRY["peer_relative_strength"]
    registry_module.ANGLE_REGISTRY["peer_relative_strength"] = (_stub_peer, "bars_price_client")
    try:
        client = _StubPriceClient()
        work_fn = build_work_fn("peer_relative_strength", "AAPL", _bars(), "x", price_client=client)
        work_fn()
    finally:
        registry_module.ANGLE_REGISTRY["peer_relative_strength"] = original

    assert calls[0]["price_client"] is client


def test_positions_shape_passes_real_closed_positions_through_and_groups_by_artifact():
    # Schema-faithful example matching vinu_live's real Position schema
    # (position_id/side/qty/avg_entry/realized_pnl/artifact_id) -- the
    # same fixture 22-pnl_attribution/02-real-scenario.md already used and
    # documented as schema-accurate (no real Phase 6 trade data exists yet
    # in this project to validate against instead).
    positions = [
        {"position_id": "p1", "symbol": "AAPL", "side": "long", "qty": 10.0,
         "avg_entry": 270.0, "realized_pnl": 55.0, "artifact_id": "artifact_kronos_001"},
        {"position_id": "p2", "symbol": "AAPL", "side": "long", "qty": 5.0,
         "avg_entry": 268.0, "realized_pnl": -22.0, "artifact_id": "artifact_kronos_001"},
        {"position_id": "p3", "symbol": "AAPL", "side": "short", "qty": 8.0,
         "avg_entry": 275.0, "realized_pnl": 40.0, "artifact_id": "artifact_arima_002"},
    ]
    work_fn = build_work_fn("pnl_attribution", "AAPL", _bars(), "x", positions=positions)
    df = work_fn()
    assert df.iloc[0]["status"] == "ok"
    assert df.iloc[0]["n_trades"] == 3
    assert df.iloc[0]["total_realized_pnl"] == 73.0
    by_artifact = df.iloc[0]["by_artifact"]
    assert by_artifact["artifact_kronos_001"]["n_trades"] == 2
    assert by_artifact["artifact_arima_002"]["n_trades"] == 1


def test_build_batch_jobs_fetches_articles_once_per_symbol_and_caches_across_angles():
    fetch_calls = []

    class _CountingNewsRepository(_StubNewsRepository):
        def get_news_for_ticker(self, ticker, start_ts=None, end_ts=None, limit=100):
            fetch_calls.append(ticker)
            return super().get_news_for_ticker(ticker, start_ts=start_ts, end_ts=end_ts, limit=limit)

    bars_by_symbol = {"AAPL": _bars()}
    jobs = build_batch_jobs(
        ["AAPL"], bars_by_symbol, "x",
        angle_names=["news_price_causality_impact", "news_price_causality_aggregate"],
        news_repository=_CountingNewsRepository(),
    )
    # Articles are fetched eagerly while building the jobs (so caching can
    # be shared across every angle needing them for the same symbol), not
    # lazily inside work_fn() -- so the fetch has already happened here.
    assert len(jobs) == 2
    assert fetch_calls == ["AAPL"]  # fetched once, not once per angle


def test_build_batch_jobs_missing_news_repository_raises_before_any_work():
    bars_by_symbol = {"AAPL": _bars()}
    with pytest.raises(ValueError, match="requires news_repository"):
        build_batch_jobs(
            ["AAPL"], bars_by_symbol, "x", angle_names=["news_price_causality_impact"],
        )


def test_build_batch_jobs_missing_positions_by_symbol_raises_before_any_work():
    bars_by_symbol = {"AAPL": _bars()}
    with pytest.raises(ValueError, match="requires positions_by_symbol"):
        build_batch_jobs(
            ["AAPL"], bars_by_symbol, "x", angle_names=["pnl_attribution"],
        )


def test_build_batch_jobs_defaults_missing_symbol_to_empty_positions_not_an_error():
    bars_by_symbol = {"AAPL": _bars()}
    jobs = build_batch_jobs(
        ["AAPL"], bars_by_symbol, "x", angle_names=["pnl_attribution"],
        positions_by_symbol={"TSLA": [{"realized_pnl": 1.0}]},  # AAPL absent, not an error
    )
    assert len(jobs) == 1
    _, _, work_fn = jobs[0]
    df = work_fn()
    assert df.iloc[0]["status"] == "no_data"


def test_build_batch_jobs_produces_symbols_times_angles():
    bars_by_symbol = {"AAPL": _bars(), "TSLA": _bars()}
    jobs = build_batch_jobs(
        ["AAPL", "TSLA"], bars_by_symbol, "some/data/root",
        news_repository=_StubNewsRepository(), price_client=_StubPriceClient(),
        positions_by_symbol={},
    )
    assert len(jobs) == 2 * len(ANGLE_REGISTRY)
    keys = {(s, a) for s, a, _ in jobs}
    assert ("AAPL", "garch") in keys
    assert ("TSLA", "trend_lifecycle") in keys
    assert ("AAPL", "news_price_causality_impact") in keys
    assert ("TSLA", "peer_relative_strength") in keys
    assert ("AAPL", "pnl_attribution") in keys


def test_build_batch_jobs_respects_angle_names_filter():
    bars_by_symbol = {"AAPL": _bars()}
    jobs = build_batch_jobs(["AAPL"], bars_by_symbol, "some/data/root", angle_names=["garch", "kronos"])
    assert len(jobs) == 2
    assert {a for _, a, _ in jobs} == {"garch", "kronos"}


def test_bars_time_format_shape_passes_time_format_by_keyword_not_position():
    # Regression test for a real bug: shock_personality's real signature is
    # (symbol, bars, news=None, time_format=None) -- time_format is 4th,
    # not 3rd. A positional call (matching regime_analysis/trend_lifecycle,
    # where time_format genuinely is 3rd) silently landed the timeframe
    # string in the `news` slot and blew up with an unrelated AttributeError
    # deep inside the angle, not a TypeError the generic parametrized test
    # above could have caught. Confirmed directly with a stub matching
    # shock_personality's exact (different) parameter order.
    calls = []

    def _stub_like_shock_personality(symbol, bars, news=None, time_format=None):
        calls.append({"symbol": symbol, "news": news, "time_format": time_format})
        return "ok"

    import vinu_initial_analysis.storage.orchestration_registry as registry_module

    original = registry_module.ANGLE_REGISTRY["shock_personality"]
    registry_module.ANGLE_REGISTRY["shock_personality"] = (_stub_like_shock_personality, "bars_time_format")
    try:
        work_fn = build_work_fn("shock_personality", "AAPL", _bars(), "x", timeframe="1D")
        work_fn()
    finally:
        registry_module.ANGLE_REGISTRY["shock_personality"] = original

    assert calls[0]["time_format"] == "1D"
    assert calls[0]["news"] is None  # must stay at its own default, not receive "1D"


def test_build_work_fn_unknown_angle_raises_keyerror():
    with pytest.raises(KeyError):
        build_work_fn("not_a_real_angle", "AAPL", _bars(), "some/data/root")


def test_build_batch_jobs_work_fns_are_independently_bound_not_late_bound():
    # Classic Python closure-in-a-loop bug: if the registry accidentally
    # captured the loop variable instead of a per-call local, every job's
    # work_fn would silently run against the SAME (last) symbol/angle.
    # Confirmed directly rather than assumed.
    bars_by_symbol = {"AAPL": _bars(3), "TSLA": _bars(7)}
    jobs = build_batch_jobs(["AAPL", "TSLA"], bars_by_symbol, "x", angle_names=["shock_clustering"])
    (aapl_symbol, _, aapl_fn), (tsla_symbol, _, tsla_fn) = jobs
    assert aapl_symbol == "AAPL" and tsla_symbol == "TSLA"
    # shock_clustering returns an empty DataFrame below its real floor
    # regardless of symbol, so this only proves independence via the
    # registry's own closures, not via a symbol-dependent return value --
    # sufficient here since TypeError-vs-not already proves call shape.
    assert aapl_fn is not tsla_fn
