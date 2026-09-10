from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from vinu_portfolio.config import PortfolioConfig
from vinu_portfolio.service import PortfolioService


def _service(**overrides) -> PortfolioService:
    return PortfolioService(config=PortfolioConfig(**overrides))


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    resp.raise_for_status.return_value = None
    return resp


def _force_research_link_unavailable():
    """vinu-research is now consulted in-process first (research_link.py) --
    forces the HTTP fallback path these existing tests exercise, same
    convention vinu-agent's test suite already uses for its own
    research_link.py-backed call sites."""
    return patch(
        "vinu_portfolio.research_link.get_strategy_store",
        side_effect=RuntimeError("not available"),
    )


class TestAllocateRiskParity:
    def test_empty_strategies_returns_empty(self) -> None:
        svc = _service()
        assert svc.allocate_risk_parity([]) == []

    def test_no_returns_df_falls_back_to_equal_weight(self) -> None:
        svc = _service()
        strategies = [{"name": "a", "kind": "yaml"}, {"name": "b", "kind": "yaml"}]
        result = svc.allocate_risk_parity(strategies, returns_df=None)
        weights = {r["name"]: r["target_weight"] for r in result}
        assert weights["a"] == pytest.approx(0.5)
        assert weights["b"] == pytest.approx(0.5)

    def test_inverse_vol_weighting_favors_lower_volatility_strategy(self) -> None:
        svc = _service(max_per_strategy_weight=1.0)
        strategies = [{"name": "steady", "kind": "yaml"}, {"name": "volatile", "kind": "yaml"}]
        dates = pd.date_range("2024-01-01", periods=30)
        rng = np.random.default_rng(0)
        returns_df = pd.DataFrame(
            {
                "steady": rng.normal(0, 0.001, size=30),
                "volatile": rng.normal(0, 0.05, size=30),
            },
            index=dates,
        )
        result = svc.allocate_risk_parity(strategies, returns_df=returns_df)
        weights = {r["name"]: r["target_weight"] for r in result}
        assert weights["steady"] > weights["volatile"]
        assert weights["steady"] + weights["volatile"] == pytest.approx(1.0)

    def test_per_strategy_cap_actually_binds_after_normalization(self) -> None:
        # Stage A (A4): the old `min(w, cap)` ran BEFORE the normalize step,
        # which renormalization then undid. With one very-low-vol strategy
        # dominating a 4-name book, the raw inv-vol weight for it is well
        # over the 0.30 cap -- the result must now actually respect 0.30
        # (rounded), not renormalize back over it.
        svc = _service(max_per_strategy_weight=0.30)
        strategies = [{"name": n, "kind": "yaml"} for n in ("dom", "b", "c", "d")]
        dates = pd.date_range("2024-01-01", periods=40)
        rng = np.random.default_rng(1)
        returns_df = pd.DataFrame(
            {
                "dom": rng.normal(0, 0.0002, size=40),   # tiny vol -> huge raw inv-vol weight
                "b": rng.normal(0, 0.03, size=40),
                "c": rng.normal(0, 0.03, size=40),
                "d": rng.normal(0, 0.03, size=40),
            },
            index=dates,
        )
        result = svc.allocate_risk_parity(strategies, returns_df=returns_df)
        weights = {r["name"]: r["target_weight"] for r in result}
        assert weights["dom"] <= 0.30 + 1e-4
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-3)


class TestComputeCorrelationMatrix:
    def test_fewer_than_two_strategies_with_data_returns_none(self) -> None:
        svc = _service()
        svc._fetch_strategy_returns = AsyncMock(return_value=None)
        result = asyncio.run(
            svc.compute_correlation_matrix([{"name": "a", "kind": "yaml"}])
        )
        assert result is None

    def test_computes_correlation_from_returns(self) -> None:
        svc = _service()
        dates = pd.date_range("2024-01-01", periods=12)
        series_a = pd.Series(np.linspace(0.0, 0.11, 12), index=dates)
        series_b = pd.Series(np.linspace(0.11, 0.0, 12), index=dates)

        async def fake_fetch(strategy):
            return series_a if strategy["name"] == "a" else series_b

        svc._fetch_strategy_returns = fake_fetch
        strategies = [{"name": "a", "kind": "yaml"}, {"name": "b", "kind": "yaml"}]
        result = asyncio.run(svc.compute_correlation_matrix(strategies))
        assert result is not None
        # Stage A (A2): Ledoit-Wolf shrinkage deliberately pulls this
        # perfectly-linear-by-construction, 12-sample series pair's raw
        # -1.0 sample correlation toward a less extreme, better-regularized
        # estimate -- exact -1.0 is no longer expected, only that the
        # strong negative relationship is still clearly detected.
        assert result.loc["a", "b"] < -0.7

    def test_correlation_matrix_is_always_positive_semidefinite(self) -> None:
        # Stage A (A1): a direct regression guard for the spectral-repair
        # path, using a case where pandas' pairwise-NaN .corr() handling is
        # a known way to produce a non-PSD matrix -- three series with
        # non-overlapping NaN gaps so each pairwise correlation is computed
        # from a different subset of rows.
        svc = _service()
        dates = pd.date_range("2024-01-01", periods=20)
        rng = np.random.default_rng(3)
        a = pd.Series(rng.normal(size=20), index=dates)
        b = pd.Series(rng.normal(size=20), index=dates)
        c = pd.Series(rng.normal(size=20), index=dates)
        a.iloc[0:5] = np.nan
        b.iloc[5:10] = np.nan
        c.iloc[10:15] = np.nan
        series = {"a": a, "b": b, "c": c}

        async def fake_fetch(strategy):
            return series[strategy["name"]]

        svc._fetch_strategy_returns = fake_fetch
        strategies = [{"name": n, "kind": "yaml"} for n in ("a", "b", "c")]
        result = asyncio.run(svc.compute_correlation_matrix(strategies))
        assert result is not None
        eigenvalues = np.linalg.eigvalsh(result.to_numpy())
        assert np.all(eigenvalues >= -1e-8)


class TestBuildPortfolio:
    def test_empty_when_no_active_strategies(self) -> None:
        svc = _service()
        svc.list_active_strategies = AsyncMock(return_value=[])
        result = asyncio.run(svc.build_portfolio())
        assert result["status"] == "empty"

    def test_allocator_receives_actual_returns_not_the_correlation_matrix(self) -> None:
        # Regression test: build_portfolio used to pass compute_correlation_matrix's
        # output (values bounded in [-1, 1], diagonal 1.0) into allocate_risk_parity,
        # which then treated it as a returns time series and annualized its column
        # std as "volatility" -- a meaningless quantity. allocate_risk_parity must
        # receive the real per-strategy returns series instead.
        svc = _service()
        strategies = [{"name": "a", "kind": "yaml"}, {"name": "b", "kind": "yaml"}]
        svc.list_active_strategies = AsyncMock(return_value=strategies)

        dates = pd.date_range("2024-01-01", periods=15)
        returns_df = pd.DataFrame(
            {"a": np.linspace(-0.01, 0.01, 15), "b": np.linspace(-0.05, 0.05, 15)},
            index=dates,
        )
        svc._build_returns_df = AsyncMock(return_value=returns_df)

        with patch.object(
            PortfolioService, "allocate_risk_parity", wraps=svc.allocate_risk_parity
        ) as spy:
            result = asyncio.run(svc.build_portfolio())

        spy.assert_called_once()
        passed_df = spy.call_args[0][1]
        pd.testing.assert_frame_equal(passed_df, returns_df)
        assert result["correlation_matrix"]["strategies"] == ["a", "b"]

    def test_no_return_data_still_returns_equal_weight_portfolio(self) -> None:
        svc = _service()
        strategies = [{"name": "a", "kind": "yaml"}, {"name": "b", "kind": "yaml"}]
        svc.list_active_strategies = AsyncMock(return_value=strategies)
        svc._build_returns_df = AsyncMock(return_value=None)

        result = asyncio.run(svc.build_portfolio())

        assert result["status"] == "ok"
        assert result["correlation_matrix"] is None
        weights = {w["name"]: w["target_weight"] for w in result["weights"]}
        assert weights["a"] == pytest.approx(0.5)
        assert weights["b"] == pytest.approx(0.5)

    def test_extra_candidates_evaluated_alongside_active_book(self) -> None:
        """Phase 2: a PEND candidate (not ACTIVE, so list_active_strategies()
        would never surface it on its own) must still get a real weight
        when passed via extra_candidates."""
        svc = _service()
        active = [{"name": "active_a", "kind": "yaml", "symbol": "AAPL"}]
        svc.list_active_strategies = AsyncMock(return_value=active)
        svc._build_returns_df = AsyncMock(return_value=None)  # equal-weight path, simplest to assert

        candidate = {
            "name": "pend_b", "kind": "llm_python", "symbol": "MSFT",
            "artifact_id": "art_pend_1", "weights_source": "artifact:art_pend_1",
            "is_candidate": True,
        }
        result = asyncio.run(svc.build_portfolio(extra_candidates=[candidate]))

        assert result["status"] == "ok"
        assert result["n_strategies"] == 2
        names = {w["name"] for w in result["weights"]}
        assert names == {"active_a", "pend_b"}
        pend_weight = next(w for w in result["weights"] if w["name"] == "pend_b")
        assert pend_weight["artifact_id"] == "art_pend_1"
        assert pend_weight["is_candidate"] is True
        active_weight = next(w for w in result["weights"] if w["name"] == "active_a")
        assert active_weight["is_candidate"] is False

    def test_no_extra_candidates_behaves_exactly_as_before(self) -> None:
        """Existing no-arg callers (the pre-Phase-2 /portfolio/state,
        /portfolio/weights routes) must see identical behavior -- extra_
        candidates is purely additive."""
        svc = _service()
        active = [{"name": "a", "kind": "yaml"}, {"name": "b", "kind": "yaml"}]
        svc.list_active_strategies = AsyncMock(return_value=active)
        svc._build_returns_df = AsyncMock(return_value=None)

        with_none = asyncio.run(svc.build_portfolio(extra_candidates=None))
        with_empty = asyncio.run(svc.build_portfolio(extra_candidates=[]))
        no_arg = asyncio.run(svc.build_portfolio())

        assert with_none["weights"] == with_empty["weights"] == no_arg["weights"]

    def test_pend_vs_pend_correlation_reflected_in_matrix(self) -> None:
        """Two PEND candidates in the same batch, highly correlated with
        each other -- the correlation matrix must show it (this is what
        Phase 2's 'NEW-vs-NEW correlation' guard rail relies on: routing
        the batch through vinu-portfolio's own correlation matrix rather
        than needing a separate check)."""
        svc = _service()
        svc.list_active_strategies = AsyncMock(return_value=[])
        dates = pd.date_range("2024-01-01", periods=15)
        returns_df = pd.DataFrame(
            {"pend_x": np.linspace(-0.01, 0.01, 15), "pend_y": np.linspace(-0.01, 0.01, 15)},
            index=dates,
        )
        svc._build_returns_df = AsyncMock(return_value=returns_df)

        candidates = [
            {"name": "pend_x", "kind": "llm_python", "artifact_id": "x", "is_candidate": True},
            {"name": "pend_y", "kind": "llm_python", "artifact_id": "y", "is_candidate": True},
        ]
        result = asyncio.run(svc.build_portfolio(extra_candidates=candidates))

        matrix = result["correlation_matrix"]
        assert matrix is not None
        idx_x = matrix["strategies"].index("pend_x")
        idx_y = matrix["strategies"].index("pend_y")
        # Stage A (A2): Ledoit-Wolf shrinkage pulls this perfectly-linear
        # synthetic pair's raw 1.0 sample correlation toward a less extreme
        # estimate -- the guard rail this test protects only needs "still
        # clearly, strongly positively correlated," not exact identity.
        assert matrix["values"][idx_x][idx_y] > 0.8


class TestListActiveStrategies:
    def test_merges_yaml_and_llm_strategies(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(
            side_effect=[
                _resp(200, [{"name": "yaml_strat", "symbol": "AAPL"}]),
                _resp(200, [{"name": "llm_strat", "artifact_id": "art_1", "universe": ["MSFT"]}]),
            ]
        )
        with _force_research_link_unavailable():
            result = asyncio.run(svc.list_active_strategies())
        names = {s["name"] for s in result}
        assert names == {"yaml_strat", "llm_strat"}

    def test_one_source_failing_does_not_drop_the_other(self) -> None:
        svc = _service()

        async def fake_get(url, **kwargs):
            if "strategy/strategies" in url:
                raise ConnectionError("strategy-api down")
            return _resp(200, [{"name": "llm_strat", "artifact_id": "art_1"}])

        svc._http.get = fake_get
        with _force_research_link_unavailable():
            result = asyncio.run(svc.list_active_strategies())
        assert [s["name"] for s in result] == ["llm_strat"]

    def test_lists_real_active_llm_strategies_in_process(self) -> None:
        from vinu_research.models import Artifact, ArtifactStatus
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        import tempfile
        from pathlib import Path

        store = SqliteStrategyStore(Path(tempfile.mktemp(suffix=".db")))
        active = Artifact.create("strategy", "llm_strat", universe=["MSFT"])
        active.status = ArtifactStatus.ACTIVE
        store.upsert_artifact(active)

        svc = _service()
        svc._http.get = AsyncMock(return_value=_resp(200, [{"name": "yaml_strat", "symbol": "AAPL"}]))
        with patch("vinu_portfolio.research_link.get_strategy_store", return_value=store):
            result = asyncio.run(svc.list_active_strategies())

        llm_entries = [s for s in result if s["kind"] == "llm_python"]
        assert len(llm_entries) == 1
        assert llm_entries[0]["artifact_id"] == active.artifact_id
        assert llm_entries[0]["symbol"] == "MSFT"


class TestFetchBenchmarkRegime:
    def test_returns_classified_regime_on_success(self) -> None:
        svc = _service()
        cycle = [0.025, -0.025, 0.001] * 13
        closes = [100.0]
        for r in cycle + [0.015]:
            closes.append(closes[-1] * (1 + r))
        records = [{"close": c} for c in closes]
        svc._http.get = AsyncMock(return_value=_resp(200, {"data": records}))

        result = asyncio.run(svc._fetch_benchmark_regime())
        assert result["status"] == "ok"
        assert result["regime"] == "bull"

    def test_fails_open_on_http_error(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(side_effect=ConnectionError("stock-api down"))
        result = asyncio.run(svc._fetch_benchmark_regime())
        assert result["status"] == "unavailable"
        assert result["regime"] is None

    def test_fails_open_on_non_200(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(return_value=_resp(500))
        result = asyncio.run(svc._fetch_benchmark_regime())
        assert result["status"] == "unavailable"

    def test_fails_open_on_empty_data(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(return_value=_resp(200, {"data": []}))
        result = asyncio.run(svc._fetch_benchmark_regime())
        assert result["status"] == "unavailable"


class TestFetchOutcomeConfidence:
    def test_yaml_strategy_with_no_symbol_not_tracked(self) -> None:
        svc = _service()
        result = asyncio.run(svc._fetch_outcome_confidence({"kind": "yaml", "name": "a"}))
        assert result == {"source": "not_tracked", "accuracy": None, "n_entries": 0}

    def test_llm_strategy_with_no_artifact_id_not_tracked(self) -> None:
        svc = _service()
        result = asyncio.run(svc._fetch_outcome_confidence({"kind": "llm_python"}))
        assert result["source"] == "not_tracked"

    def test_llm_strategy_with_enough_entries_returns_accuracy(self) -> None:
        svc = _service(min_calibration_entries_for_tilt=5)
        svc._http.get = AsyncMock(
            return_value=_resp(200, {"n_entries": 8, "accuracy": 0.75})
        )
        with _force_research_link_unavailable():
            result = asyncio.run(
                svc._fetch_outcome_confidence({"kind": "llm_python", "artifact_id": "art_1"})
            )
        assert result == {"source": "calibration", "accuracy": 0.75, "n_entries": 8}

    def test_llm_strategy_with_insufficient_entries(self) -> None:
        svc = _service(min_calibration_entries_for_tilt=5)
        svc._http.get = AsyncMock(
            return_value=_resp(200, {"n_entries": 2, "accuracy": 1.0})
        )
        with _force_research_link_unavailable():
            result = asyncio.run(
                svc._fetch_outcome_confidence({"kind": "llm_python", "artifact_id": "art_1"})
            )
        assert result["source"] == "insufficient_data"
        assert result["accuracy"] is None

    def test_fails_open_on_http_error(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(side_effect=ConnectionError("research-api down"))
        with _force_research_link_unavailable():
            result = asyncio.run(
                svc._fetch_outcome_confidence({"kind": "llm_python", "artifact_id": "art_1"})
            )
        assert result["source"] == "unavailable"

    def test_reads_real_calibration_entries_in_process(self) -> None:
        from vinu_research.models import Artifact, CalibrationEntry
        from vinu_research.storage.strategy_store import SqliteStrategyStore
        import tempfile
        from pathlib import Path

        store = SqliteStrategyStore(Path(tempfile.mktemp(suffix=".db")))
        artifact = Artifact.create("trade_plan", "plan-aapl", universe=["AAPL"])
        store.upsert_artifact(artifact)
        for _ in range(6):
            store.append_calibration_entry(CalibrationEntry(
                artifact_id=artifact.artifact_id, forecast_direction="up", actual_return_pct=0.02,
                forecast_magnitude_pct=0.02, brier_score=0.1, directional_correct=True,
                magnitude_error=0.01, timestamp="2026-01-01T00:00:00Z",
            ))

        svc = _service(min_calibration_entries_for_tilt=5)
        with patch("vinu_portfolio.research_link.get_strategy_store", return_value=store):
            result = asyncio.run(
                svc._fetch_outcome_confidence({"kind": "llm_python", "artifact_id": artifact.artifact_id})
            )
        assert result["source"] == "calibration"
        assert result["n_entries"] == 6
        assert result["accuracy"] == 1.0


class TestYamlTrackRecord:
    """Stage 2 (how-to-make-it-live.md #20): YAML strategies used to be
    permanently "not_tracked" no matter how long they ran -- there was no
    calibration_entries equivalent for a portfolio target-weight strategy.
    _fetch_yaml_track_record derives a directional track record from the
    weight history + price history vinu-portfolio already fetches
    elsewhere; these prove the accuracy math and the fail-open contract."""

    @staticmethod
    def _bar_ts(date_str: str) -> int:
        from datetime import datetime, timezone
        return int(datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc).timestamp())

    def _mock_http(self, svc: PortfolioService, weights, candles) -> None:
        async def _get(url, **kwargs):
            if "candles" in url:
                return _resp(200, {"data": candles})
            return _resp(200, weights)
        svc._http.get = AsyncMock(side_effect=_get)

    def _strategy(self) -> dict:
        return {
            "kind": "yaml", "name": "s1", "symbol": "AAPL",
            "weights_source": "http://strategy-api-test/strategy/weights/s1",
        }

    def _sample_series(self):
        weights = [
            {"date": "2024-01-01", "weight": 1.0},   # long
            {"date": "2024-01-02", "weight": 1.0},   # long
            {"date": "2024-01-03", "weight": -1.0},  # short
            {"date": "2024-01-04", "weight": 0.0},   # flat -- no call, excluded
        ]
        candles = [
            {"bar_ts": self._bar_ts("2024-01-01"), "close": 100.0},
            {"bar_ts": self._bar_ts("2024-01-02"), "close": 105.0},  # +5% -- day1's long call: correct
            {"bar_ts": self._bar_ts("2024-01-03"), "close": 103.0},  # -1.9% -- day2's long call: wrong
            {"bar_ts": self._bar_ts("2024-01-04"), "close": 110.0},  # +6.8% -- day3's short call: wrong
        ]
        return weights, candles

    def test_computes_directional_accuracy(self) -> None:
        svc = _service(min_calibration_entries_for_tilt=2)
        weights, candles = self._sample_series()
        self._mock_http(svc, weights, candles)

        result = asyncio.run(svc._fetch_outcome_confidence(self._strategy()))

        assert result["source"] == "yaml_track_record"
        assert result["n_entries"] == 3  # day4's flat weight excludes the (day3,day4) call
        assert result["accuracy"] == pytest.approx(1 / 3)

    def test_insufficient_entries(self) -> None:
        svc = _service(min_calibration_entries_for_tilt=10)
        weights, candles = self._sample_series()
        self._mock_http(svc, weights, candles)

        result = asyncio.run(svc._fetch_outcome_confidence(self._strategy()))

        assert result["source"] == "insufficient_data"
        assert result["accuracy"] is None
        assert result["n_entries"] == 3

    def test_all_flat_weights_is_not_tracked(self) -> None:
        svc = _service(min_calibration_entries_for_tilt=1)
        weights = [
            {"date": "2024-01-01", "weight": 0.0},
            {"date": "2024-01-02", "weight": 0.0},
        ]
        candles = [
            {"bar_ts": self._bar_ts("2024-01-01"), "close": 100.0},
            {"bar_ts": self._bar_ts("2024-01-02"), "close": 101.0},
        ]
        self._mock_http(svc, weights, candles)

        result = asyncio.run(svc._fetch_outcome_confidence(self._strategy()))

        assert result == {"source": "not_tracked", "accuracy": None, "n_entries": 0}

    def test_empty_weights_is_not_tracked(self) -> None:
        svc = _service()
        self._mock_http(svc, [], [{"bar_ts": self._bar_ts("2024-01-01"), "close": 100.0}])
        result = asyncio.run(svc._fetch_outcome_confidence(self._strategy()))
        assert result == {"source": "not_tracked", "accuracy": None, "n_entries": 0}

    def test_empty_candles_is_not_tracked(self) -> None:
        svc = _service()
        self._mock_http(svc, [{"date": "2024-01-01", "weight": 1.0}], [])
        result = asyncio.run(svc._fetch_outcome_confidence(self._strategy()))
        assert result == {"source": "not_tracked", "accuracy": None, "n_entries": 0}

    def test_missing_symbol_is_not_tracked_without_any_http_call(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(side_effect=AssertionError("must not be called"))
        result = asyncio.run(
            svc._fetch_outcome_confidence({"kind": "yaml", "name": "s1", "weights_source": "http://x"})
        )
        assert result == {"source": "not_tracked", "accuracy": None, "n_entries": 0}

    def test_fails_open_on_http_error(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(side_effect=ConnectionError("strategy-api down"))
        result = asyncio.run(svc._fetch_outcome_confidence(self._strategy()))
        assert result == {"source": "not_tracked", "accuracy": None, "n_entries": 0}

    def test_fails_open_on_non_200_weights(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(return_value=_resp(500))
        result = asyncio.run(svc._fetch_outcome_confidence(self._strategy()))
        assert result == {"source": "not_tracked", "accuracy": None, "n_entries": 0}


class TestRegimeAlignmentMultiplier:
    @staticmethod
    def _service_with_tags(tmp_path, bound=0.3) -> PortfolioService:
        tags_file = tmp_path / "tags.yaml"
        tags_file.write_text(
            "strategies:\n"
            "  trend_strat:\n"
            "    regime: [trending]\n"
            "  meanrev_strat:\n"
            "    regime: [ranging, mean_reverting]\n",
            encoding="utf-8",
        )
        return _service(tags_path=tags_file, regime_tilt_bound=bound)

    def test_aligned_regime_gets_positive_tilt(self, tmp_path) -> None:
        svc = self._service_with_tags(tmp_path)
        assert svc._regime_alignment_multiplier("trend_strat", "bull") == pytest.approx(1.3)

    def test_mismatched_regime_gets_negative_tilt(self, tmp_path) -> None:
        svc = self._service_with_tags(tmp_path)
        assert svc._regime_alignment_multiplier("trend_strat", "sideways") == pytest.approx(0.7)

    def test_untagged_strategy_is_neutral(self, tmp_path) -> None:
        svc = self._service_with_tags(tmp_path)
        assert svc._regime_alignment_multiplier("unknown_strat", "bull") == pytest.approx(1.0)

    def test_high_vol_is_neutral_regardless_of_tags(self, tmp_path) -> None:
        svc = self._service_with_tags(tmp_path)
        assert svc._regime_alignment_multiplier("trend_strat", "high_vol") == pytest.approx(1.0)

    def test_missing_tags_file_is_neutral_not_fatal(self, tmp_path) -> None:
        svc = _service(tags_path=tmp_path / "does_not_exist.yaml")
        assert svc._regime_alignment_multiplier("anything", "bull") == pytest.approx(1.0)


class TestOutcomeConfidenceMultiplier:
    def test_untracked_is_neutral(self) -> None:
        svc = _service()
        assert svc._outcome_confidence_multiplier({"accuracy": None}) == pytest.approx(1.0)

    def test_high_accuracy_tilts_up(self) -> None:
        svc = _service(outcome_tilt_bound=0.3)
        assert svc._outcome_confidence_multiplier({"accuracy": 1.0}) == pytest.approx(1.3)

    def test_low_accuracy_tilts_down(self) -> None:
        svc = _service(outcome_tilt_bound=0.3)
        assert svc._outcome_confidence_multiplier({"accuracy": 0.0}) == pytest.approx(0.7)

    def test_coinflip_accuracy_is_neutral(self) -> None:
        svc = _service(outcome_tilt_bound=0.3)
        assert svc._outcome_confidence_multiplier({"accuracy": 0.5}) == pytest.approx(1.0)


class TestConfidenceGradientMultiplier:
    """Stage 2 (how-to-make-it-live.md #34): a strategy that barely cleared
    the promotion bar and one that cleared it comfortably used to get
    identical downstream allocation weight -- promotion.meets_promotion_bar
    is binary, nothing carried the margin forward."""

    def test_yaml_strategy_is_always_neutral(self) -> None:
        svc = _service()
        strategy = {"kind": "yaml", "deflated_sharpe": 0.99}
        assert svc._confidence_gradient_multiplier(strategy) == pytest.approx(1.0)

    def test_missing_deflated_sharpe_is_neutral(self) -> None:
        svc = _service()
        assert svc._confidence_gradient_multiplier({"kind": "llm_python"}) == pytest.approx(1.0)

    def test_at_threshold_gets_the_low_bound(self) -> None:
        svc = _service(promotion_deflated_sharpe_threshold=0.95, confidence_tilt_bound=0.3)
        strategy = {"kind": "llm_python", "deflated_sharpe": 0.95}
        assert svc._confidence_gradient_multiplier(strategy) == pytest.approx(0.7)

    def test_at_ceiling_gets_the_high_bound(self) -> None:
        svc = _service(promotion_deflated_sharpe_threshold=0.95, confidence_tilt_bound=0.3)
        strategy = {"kind": "llm_python", "deflated_sharpe": 1.0}
        assert svc._confidence_gradient_multiplier(strategy) == pytest.approx(1.3)

    def test_below_threshold_is_clamped_to_the_low_bound(self) -> None:
        """A force=true override could promote below-threshold artifacts --
        those size as conservatively as a bare pass, not worse and not
        neutral."""
        svc = _service(promotion_deflated_sharpe_threshold=0.95, confidence_tilt_bound=0.3)
        strategy = {"kind": "llm_python", "deflated_sharpe": 0.5}
        assert svc._confidence_gradient_multiplier(strategy) == pytest.approx(0.7)

    def test_midpoint_between_threshold_and_ceiling(self) -> None:
        svc = _service(promotion_deflated_sharpe_threshold=0.9, confidence_tilt_bound=0.3)
        strategy = {"kind": "llm_python", "deflated_sharpe": 0.95}  # halfway from 0.9 to 1.0
        assert svc._confidence_gradient_multiplier(strategy) == pytest.approx(1.0)

    def test_a_barely_passed_strategy_gets_smaller_weight_than_a_strongly_passed_one(self) -> None:
        svc = _service(promotion_deflated_sharpe_threshold=0.95, confidence_tilt_bound=0.3)
        bare = svc._confidence_gradient_multiplier({"kind": "llm_python", "deflated_sharpe": 0.951})
        strong = svc._confidence_gradient_multiplier({"kind": "llm_python", "deflated_sharpe": 0.999})
        assert bare < strong


class TestComputeDailyAllocation:
    def test_passes_through_empty_base_portfolio(self) -> None:
        svc = _service()
        svc.build_portfolio = AsyncMock(return_value={"status": "empty", "strategies": [], "weights": []})
        result = asyncio.run(svc.compute_daily_allocation())
        assert result["status"] == "empty"

    def test_applies_tilts_and_renormalizes(self, tmp_path) -> None:
        tags_file = tmp_path / "tags.yaml"
        tags_file.write_text(
            "strategies:\n  favored:\n    regime: [trending]\n", encoding="utf-8"
        )
        svc = _service(tags_path=tags_file, regime_tilt_bound=0.3, outcome_tilt_bound=0.0)
        svc.build_portfolio = AsyncMock(return_value={
            "status": "ok",
            "strategies": [
                {"name": "favored", "kind": "yaml"},
                {"name": "other", "kind": "yaml"},
            ],
            "weights": [
                {"name": "favored", "kind": "yaml", "symbol": "", "target_weight": 0.5},
                {"name": "other", "kind": "yaml", "symbol": "", "target_weight": 0.5},
            ],
            "correlation_matrix": None,
        })
        svc._fetch_benchmark_regime = AsyncMock(return_value={"status": "ok", "regime": "bull"})
        svc._fetch_outcome_confidence = AsyncMock(return_value={"source": "not_tracked", "accuracy": None, "n_entries": 0})
        svc._fetch_account_equity = AsyncMock(return_value=None)

        result = asyncio.run(svc.compute_daily_allocation())

        weights = {w["name"]: w for w in result["weights"]}
        assert weights["favored"]["target_weight"] > weights["other"]["target_weight"]
        total = sum(w["target_weight"] for w in result["weights"])
        assert total == pytest.approx(1.0)
        assert "position_size" not in weights["favored"]  # no equity available

    def test_applies_position_sizing_when_equity_available(self) -> None:
        svc = _service()
        svc.build_portfolio = AsyncMock(return_value={
            "status": "ok",
            "strategies": [{"name": "a", "kind": "yaml"}],
            "weights": [{"name": "a", "kind": "yaml", "symbol": "", "target_weight": 1.0}],
            "correlation_matrix": None,
        })
        svc._fetch_benchmark_regime = AsyncMock(return_value={"status": "unavailable", "regime": None})
        svc._fetch_outcome_confidence = AsyncMock(return_value={"source": "not_tracked", "accuracy": None, "n_entries": 0})
        svc._fetch_account_equity = AsyncMock(return_value=100_000.0)

        result = asyncio.run(svc.compute_daily_allocation())
        assert result["weights"][0]["position_size"] == pytest.approx(100_000.0, rel=0.01)
        assert result["account_equity"] == 100_000.0

    def test_confidence_gradient_tilts_llm_python_strategies(self) -> None:
        """Stage 2 (#34): two llm_python strategies with equal base weight
        but different promotion margins must end up with different final
        weight -- this is the end-to-end proof, not just the unit-level
        multiplier math above."""
        svc = _service(
            promotion_deflated_sharpe_threshold=0.95, confidence_tilt_bound=0.3,
            outcome_tilt_bound=0.0,
        )
        svc.build_portfolio = AsyncMock(return_value={
            "status": "ok",
            "strategies": [
                {"name": "bare_pass", "kind": "llm_python", "deflated_sharpe": 0.951},
                {"name": "strong_pass", "kind": "llm_python", "deflated_sharpe": 0.999},
            ],
            "weights": [
                {"name": "bare_pass", "kind": "llm_python", "symbol": "", "target_weight": 0.5},
                {"name": "strong_pass", "kind": "llm_python", "symbol": "", "target_weight": 0.5},
            ],
            "correlation_matrix": None,
        })
        svc._fetch_benchmark_regime = AsyncMock(return_value={"status": "unavailable", "regime": None})
        svc._fetch_outcome_confidence = AsyncMock(return_value={"source": "not_tracked", "accuracy": None, "n_entries": 0})
        svc._fetch_account_equity = AsyncMock(return_value=None)

        result = asyncio.run(svc.compute_daily_allocation())

        weights = {w["name"]: w for w in result["weights"]}
        assert weights["strong_pass"]["target_weight"] > weights["bare_pass"]["target_weight"]
        assert weights["bare_pass"]["confidence_gradient_multiplier"] < weights["strong_pass"]["confidence_gradient_multiplier"]


class TestFetchAccountEquity:
    def test_returns_none_when_not_configured(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(return_value=_resp(200, {"configured": False}))
        assert asyncio.run(svc._fetch_account_equity()) is None

    def test_returns_equity_when_configured(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(return_value=_resp(200, {"configured": True, "equity": 50000.0}))
        assert asyncio.run(svc._fetch_account_equity()) == 50000.0

    def test_fails_open_on_error(self) -> None:
        svc = _service()
        svc._http.get = AsyncMock(side_effect=ConnectionError("agent-api down"))
        assert asyncio.run(svc._fetch_account_equity()) is None
