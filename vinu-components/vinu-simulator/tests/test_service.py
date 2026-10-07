"""item #13 finding #6: `service.py` (the main orchestration/caching/
hashing logic, 700+ lines) had no dedicated test file at all -- only
indirectly touched via test_sizing_knobs_wired_through_api.py's own
narrower focus. These cover the pieces that file doesn't: the OHLCV
cache's TTL/eviction behavior, config-hash determinism, benchmark-metric
computation, the read/delete methods, close(), a real end-to-end
simulate() happy path, and simulate_custom()'s validation paths (security
rejection, unknown class, wrong base class) -- none of which had any
coverage before this file."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from vinu_simulator.config import VinuSimulatorConfig
from vinu_simulator.engine.strategies import BaseStrategy
from vinu_simulator.models.simulation import SimulationResult, TradeRecord
from vinu_simulator.server.schemas import CustomSimulateRequest, SimulateRequest
from vinu_simulator.service import SimulatorService


@pytest.fixture
def service(tmp_path) -> SimulatorService:
    config = VinuSimulatorConfig(
        host="127.0.0.1", port=0, data_root=tmp_path,
        initial_capital=1_000_000.0, transaction_cost_pct=0.001, slippage_pct=0.0005,
        benchmark_tickers=("SPY",), allow_short=True,
        strategy_api_url="http://unused", stock_api_url="http://unused",
        features_api_url="http://unused", deviation_threshold=0.05,
    )
    svc = SimulatorService(config=config)
    yield svc
    svc.close()


class TestComputeConfigHash:
    def test_deterministic_for_the_same_input(self, service) -> None:
        params = {"a": 1, "b": "x"}
        assert service._compute_config_hash(params) == service._compute_config_hash(params)

    def test_key_order_does_not_matter(self, service) -> None:
        h1 = service._compute_config_hash({"a": 1, "b": 2})
        h2 = service._compute_config_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_different_values_hash_differently(self, service) -> None:
        h1 = service._compute_config_hash({"a": 1})
        h2 = service._compute_config_hash({"a": 2})
        assert h1 != h2


class TestOhclvCache:
    def _series_frame(self, value: float) -> dict[str, pd.DataFrame]:
        dates = pd.date_range("2023-01-02", periods=3, freq="D")
        frame = pd.DataFrame({"close": [value] * 3}, index=dates)
        return {"AAPL": frame, "MSFT": frame}  # a complete answer for the symbols the tests ask for

    def test_a_repeated_call_hits_the_cache_not_the_client(self, service, monkeypatch) -> None:
        calls = {"n": 0}

        def _fake_get_ohclv(symbols, start, end, resolution="1d", indicators=None):
            calls["n"] += 1
            return self._series_frame(100.0)

        monkeypatch.setattr(service._price_client, "get_ohclv", _fake_get_ohclv)
        service._get_ohclv_cached(["AAPL"], "2023-01-01", "2023-01-10", "1d", ["sma_20"])
        service._get_ohclv_cached(["AAPL"], "2023-01-01", "2023-01-10", "1d", ["sma_20"])
        assert calls["n"] == 1

    def test_identical_concurrent_requests_share_one_fetch(self, service, monkeypatch) -> None:
        """A sweep round runs many points at once for the same candles. Each used
        to fetch on its own; the stock API timed out under that load and every
        walk-forward window saw 'no data'."""
        import threading
        import time

        calls = {"n": 0}

        def _slow_get_ohclv(symbols, start, end, resolution="1d", indicators=None):
            calls["n"] += 1
            time.sleep(0.2)
            return self._series_frame(100.0)

        monkeypatch.setattr(service._price_client, "get_ohclv", _slow_get_ohclv)
        threads = [
            threading.Thread(target=service._get_ohclv_cached,
                             args=(["AAPL"], "2023-01-01", "2023-01-10", "1d", None))
            for _ in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert calls["n"] == 1

    def test_a_failed_fetch_is_not_cached(self, service, monkeypatch) -> None:
        calls = {"n": 0}

        def _get_ohclv(symbols, start, end, resolution="1d", indicators=None):
            calls["n"] += 1
            return {} if calls["n"] == 1 else self._series_frame(100.0)

        monkeypatch.setattr(service._price_client, "get_ohclv", _get_ohclv)
        assert service._get_ohclv_cached(["AAPL"], "2023-01-01", "2023-01-10", "1d", None) == {}
        assert "AAPL" in service._get_ohclv_cached(["AAPL"], "2023-01-01", "2023-01-10", "1d", None)
        assert calls["n"] == 2

    def test_symbol_order_does_not_defeat_the_cache(self, service, monkeypatch) -> None:
        calls = {"n": 0}

        def _fake_get_ohclv(symbols, start, end, resolution="1d", indicators=None):
            calls["n"] += 1
            return self._series_frame(100.0)

        monkeypatch.setattr(service._price_client, "get_ohclv", _fake_get_ohclv)
        service._get_ohclv_cached(["AAPL", "MSFT"], "2023-01-01", "2023-01-10", "1d", None)
        service._get_ohclv_cached(["MSFT", "AAPL"], "2023-01-01", "2023-01-10", "1d", None)
        assert calls["n"] == 1

    def test_a_different_date_range_is_a_real_cache_miss(self, service, monkeypatch) -> None:
        calls = {"n": 0}

        def _fake_get_ohclv(symbols, start, end, resolution="1d", indicators=None):
            calls["n"] += 1
            return self._series_frame(100.0)

        monkeypatch.setattr(service._price_client, "get_ohclv", _fake_get_ohclv)
        service._get_ohclv_cached(["AAPL"], "2023-01-01", "2023-01-10", "1d", None)
        service._get_ohclv_cached(["AAPL"], "2023-02-01", "2023-02-10", "1d", None)
        assert calls["n"] == 2

    def test_an_expired_entry_is_refetched(self, service, monkeypatch) -> None:
        import vinu_simulator.service as service_mod
        monkeypatch.setattr(service_mod, "_OHCLV_CACHE_TTL_SECONDS", 0.0)
        calls = {"n": 0}

        def _fake_get_ohclv(symbols, start, end, resolution="1d", indicators=None):
            calls["n"] += 1
            return self._series_frame(100.0)

        monkeypatch.setattr(service._price_client, "get_ohclv", _fake_get_ohclv)
        service._get_ohclv_cached(["AAPL"], "2023-01-01", "2023-01-10", "1d", None)
        service._get_ohclv_cached(["AAPL"], "2023-01-01", "2023-01-10", "1d", None)
        assert calls["n"] == 2


class TestComputeBenchmarkMetrics:
    def test_computes_metrics_for_present_tickers(self, service) -> None:
        from vinu_simulator.models.simulation import SimulationConfig
        dates = pd.date_range("2023-01-02", periods=10, freq="D")
        price_data = pd.DataFrame({"SPY": 100.0 + np.arange(10)}, index=dates)
        config = SimulationConfig(
            strategy_name="s", start_date="2023-01-02", end_date="2023-01-11",
            benchmark_tickers=("SPY",),
        )
        result = service._compute_benchmark_metrics(price_data, config)
        assert "SPY" in result
        assert "sharpe_ratio" in result["SPY"]

    def test_a_missing_ticker_is_skipped_not_a_crash(self, service) -> None:
        from vinu_simulator.models.simulation import SimulationConfig
        dates = pd.date_range("2023-01-02", periods=10, freq="D")
        price_data = pd.DataFrame({"SPY": 100.0 + np.arange(10)}, index=dates)
        config = SimulationConfig(
            strategy_name="s", start_date="2023-01-02", end_date="2023-01-11",
            benchmark_tickers=("QQQ",),
        )
        assert service._compute_benchmark_metrics(price_data, config) == {}

    def test_fewer_than_two_valid_points_is_skipped(self, service) -> None:
        from vinu_simulator.models.simulation import SimulationConfig
        dates = pd.date_range("2023-01-02", periods=2, freq="D")
        price_data = pd.DataFrame({"SPY": [100.0, np.nan]}, index=dates)
        config = SimulationConfig(
            strategy_name="s", start_date="2023-01-02", end_date="2023-01-03",
            benchmark_tickers=("SPY",),
        )
        assert service._compute_benchmark_metrics(price_data, config) == {}


def _seed_run(service: SimulatorService, run_id: str, symbols: list[str], *, start: str = "2023-01-02", freq: str = "D") -> None:
    from vinu_simulator.models.simulation import SimulationConfig
    dates = pd.date_range(start, periods=3, freq=freq)
    result = SimulationResult(
        run_id=run_id, strategy_name="s", timestamp=datetime.now(timezone.utc),
        config=SimulationConfig(strategy_name="s", start_date="2023-01-02", end_date="2023-01-04"),
        portfolio_values=pd.Series([1_000_000.0, 1_010_000.0, 1_005_000.0], index=dates),
        daily_returns=pd.Series([0.0, 0.01, -0.005], index=dates),
        weights_history=pd.DataFrame({symbols[0]: [1.0, 1.0, 1.0]}, index=dates),
        trades=[
            TradeRecord(
                date=dates[1], symbol=symbols[0], side="buy", shares=10.0, price=100.0,
                cost=1.0, weight_before=0.0, weight_after=1.0,
            )
        ],
        metrics={"sharpe_ratio": 1.0},
        benchmark_metrics={},
    )
    service._result_storage.save(result)
    service._meta_storage.insert_run(
        run_id=run_id, strategy_name="s", timestamp=result.timestamp,
        config={"strategy_name": "s", "start_date": "2023-01-02", "end_date": "2023-01-04"},
        metrics=result.metrics, benchmark_metrics={}, equity_points=3, trade_count=1,
        config_hash=f"hash-{run_id}", symbols=symbols,
    )


class TestReadAndDeleteMethods:
    def test_get_result_returns_none_for_unknown_run(self, service) -> None:
        assert service.get_result("ghost") is None

    def test_get_result_includes_equity_and_trades_when_requested(self, service) -> None:
        _seed_run(service, "run-1", ["AAPL"])
        result = service.get_result("run-1")
        assert result is not None
        assert len(result["equity"]) == 3
        assert len(result["trades"]) == 1

    def test_get_result_skips_loading_data_when_not_requested(self, service) -> None:
        _seed_run(service, "run-1", ["AAPL"])
        result = service.get_result("run-1", load_data=False)
        assert result is not None
        assert "equity" not in result

    def test_get_equity_date_format_matches_get_weights(self, service) -> None:
        _seed_run(service, "run-1", ["AAPL"])
        equity = service.get_equity("run-1")
        weights = service.get_weights("run-1")
        assert equity[0]["date"] == weights[0]["date"]

    def test_an_intraday_equity_curve_keeps_its_time_of_day(self, service) -> None:
        # date-only text made a day's 26 or 96 bars read as one instant, so no return could be attributed to a session
        _seed_run(service, "run-h", ["AAPL"], start="2024-10-07 14:30", freq="h")
        dates = [row["date"] for row in service.get_equity("run-h")]
        assert dates == ["2024-10-07 14:30:00", "2024-10-07 15:30:00", "2024-10-07 16:30:00"]
        assert len(set(dates)) == 3

    def test_get_equity_unknown_run_returns_none(self, service) -> None:
        assert service.get_equity("ghost") is None

    def test_get_weights_unknown_run_returns_none(self, service) -> None:
        assert service.get_weights("ghost") is None

    def test_get_trades_returns_recorded_trades(self, service) -> None:
        _seed_run(service, "run-1", ["AAPL"])
        trades = service.get_trades("run-1")
        assert len(trades) == 1
        assert trades[0]["symbol"] == "AAPL"

    def test_get_trades_unknown_run_returns_none(self, service) -> None:
        assert service.get_trades("ghost") is None

    def test_list_runs_returns_summaries(self, service) -> None:
        _seed_run(service, "run-1", ["AAPL"])
        _seed_run(service, "run-2", ["MSFT"])
        summaries = service.list_runs()
        assert {s.run_id for s in summaries} == {"run-1", "run-2"}

    def test_list_runs_filters_by_symbol(self, service) -> None:
        _seed_run(service, "run-1", ["AAPL"])
        _seed_run(service, "run-2", ["MSFT"])
        summaries = service.list_runs(symbol="AAPL")
        assert {s.run_id for s in summaries} == {"run-1"}

    def test_delete_run_removes_meta_and_result_data(self, service) -> None:
        _seed_run(service, "run-1", ["AAPL"])
        assert service.delete_run("run-1") is True
        assert service.get_result("run-1") is None

    def test_delete_run_unknown_run_returns_false(self, service) -> None:
        assert service.delete_run("ghost") is False

    def test_delete_runs_by_strategy_removes_all_matching(self, service) -> None:
        _seed_run(service, "run-1", ["AAPL"])
        _seed_run(service, "run-2", ["MSFT"])
        deleted = service.delete_runs(strategy_name="s")
        assert deleted == 2
        assert service.list_runs() == []


class TestClose:
    def test_close_closes_the_http_clients_and_meta_storage(self, service) -> None:
        calls = []
        service._strategy_client.close = lambda: calls.append("strategy")
        service._price_client.close = lambda: calls.append("price")
        service._meta_storage.close = lambda: calls.append("meta")
        service.close()
        assert set(calls) == {"strategy", "price", "meta"}


class _ConstantWeightStrategy(BaseStrategy):
    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        return pd.Series(1.0, index=data.index)


class TestSimulateDryRun:
    def test_dry_run_never_touches_clients_or_storage(self, service, monkeypatch) -> None:
        def _boom(*a, **kw):
            raise AssertionError("dry_run must not call this")

        monkeypatch.setattr(service._strategy_client, "get_weights", _boom)
        monkeypatch.setattr(service._price_client, "get_price_and_volume", _boom)
        req = SimulateRequest(strategy_name="unused", dry_run=True)
        result = service.simulate(req)
        assert result.run_id == "dry_run"
        assert result.metrics["total_return"] == 0.0


class TestSimulateHappyPathAndCache:
    def _wire_fakes(self, service, monkeypatch) -> None:
        dates = pd.date_range("2023-01-02", periods=10, freq="D")
        weights = pd.DataFrame({"AAPL": [1.0]}, index=[dates[0]])
        prices = pd.DataFrame({"AAPL": 100.0 + np.arange(10)}, index=dates)
        volumes = pd.DataFrame({"AAPL": np.full(10, 1_000_000.0)}, index=dates)
        monkeypatch.setattr(service._strategy_client, "get_weights", lambda *a, **kw: weights)
        monkeypatch.setattr(
            service._price_client, "get_price_and_volume", lambda *a, **kw: (prices, volumes)
        )

    def test_a_real_run_persists_and_returns_a_result(self, service, monkeypatch) -> None:
        self._wire_fakes(service, monkeypatch)
        req = SimulateRequest(
            strategy_name="momentum", start_date="2023-01-02", end_date="2023-01-11",
        )
        result = service.simulate(req)
        assert result.strategy_name == "momentum"
        assert service.get_result(result.run_id) is not None

    def test_an_identical_request_is_served_from_the_config_hash_cache(self, service, monkeypatch) -> None:
        self._wire_fakes(service, monkeypatch)
        req = SimulateRequest(
            strategy_name="momentum", start_date="2023-01-02", end_date="2023-01-11",
        )
        first = service.simulate(req)

        def _boom(*a, **kw):
            raise AssertionError("a cache hit must not re-fetch weights")

        monkeypatch.setattr(service._strategy_client, "get_weights", _boom)
        second = service.simulate(req)
        assert second.run_id == first.run_id

    def test_no_weight_data_raises_value_error(self, service, monkeypatch) -> None:
        monkeypatch.setattr(service._strategy_client, "get_weights", lambda *a, **kw: pd.DataFrame())
        req = SimulateRequest(strategy_name="ghost", start_date="2023-01-02", end_date="2023-01-11")
        with pytest.raises(ValueError, match="No weight data"):
            service.simulate(req)


class TestSimulateCustomValidation:
    def test_security_violation_is_rejected_before_any_execution(self, service) -> None:
        req = CustomSimulateRequest(
            strategy_code="import os\nclass X(BaseStrategy):\n    def generate_weights(self, data): return data['close']*0",
            class_name="X", symbols=["AAPL"],
        )
        with pytest.raises(ValueError, match="security validation"):
            service.simulate_custom(req)

    def test_missing_class_name_raises(self, service) -> None:
        req = CustomSimulateRequest(
            strategy_code="class X(BaseStrategy):\n    def generate_weights(self, data): return data['close']*0",
            class_name="NotThere", symbols=["AAPL"],
        )
        with pytest.raises(ValueError, match="not found"):
            service.simulate_custom(req)

    def test_class_not_a_base_strategy_subclass_raises(self, service) -> None:
        req = CustomSimulateRequest(
            strategy_code="class X:\n    pass",
            class_name="X", symbols=["AAPL"],
        )
        with pytest.raises(ValueError, match="must be a subclass"):
            service.simulate_custom(req)


class TestSessionIsPartOfTheQuestion:
    """A request for all 24 hours must not be answered with the stored regular-hours run of the same strategy."""

    CODE = ("class UserStrategy(BaseStrategy):\n    def generate_weights(self, data):\n"
            "        return (data['close'] > data['close'].rolling(5).mean()).astype(int) * 0.98\n")

    @staticmethod
    def _frames(n):
        import numpy as np
        import pandas as pd

        idx = pd.date_range("2026-01-05 14:30", periods=n, freq="h")
        close = 100 + np.cumsum(np.random.default_rng(1).normal(0, 0.5, n))
        return {"AAA": pd.DataFrame({"open": close, "high": close + 0.1, "low": close - 0.1, "close": close, "volume": 1e6}, index=idx)}

    def test_a_different_session_is_a_different_run_and_reaches_the_price_service(self, service) -> None:
        calls = []

        def fake(symbols, start, end, resolution="1d", indicators=None, session="regular"):
            calls.append(session)
            return self._frames(60 if session == "regular" else 150)

        service._price_client.get_ohclv = fake
        mk = lambda sess: CustomSimulateRequest(strategy_code=self.CODE, class_name="UserStrategy", symbols=["AAA"],
                                                start_date="2026-01-05", end_date="2026-03-01", interval="1h", session=sess,
                                                allow_short=False, run_validation=False)
        regular = service.simulate_custom(mk("regular"))
        everything = service.simulate_custom(mk("all"))
        assert regular.run_id != everything.run_id
        assert len(regular.portfolio_values) < len(everything.portfolio_values)
        assert calls == ["regular", "all"] and everything.config.sessions == "all"

    def test_the_default_session_keeps_its_old_hash(self, service) -> None:
        # a regular-hours request is looked up exactly as before this change (the stored runs stay reusable)
        calls = []
        service._price_client.get_ohclv = lambda *a, **k: (calls.append(k), self._frames(60))[1]
        req = CustomSimulateRequest(strategy_code=self.CODE, class_name="UserStrategy", symbols=["AAA"], start_date="2026-01-05",
                                    end_date="2026-03-01", interval="1h", allow_short=False, run_validation=False)
        first = service.simulate_custom(req)
        second = service.simulate_custom(req)
        assert first.run_id == second.run_id and len(calls) == 1 and "session" not in calls[0]
