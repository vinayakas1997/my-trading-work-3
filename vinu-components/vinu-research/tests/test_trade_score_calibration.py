from __future__ import annotations

from dataclasses import dataclass

import pytest

from vinu_research.config import TradeScoreThresholds
from vinu_research.trade_score_calibration import (
    approve_proposal,
    apply_directly,
    compute_calibration_metrics,
    get_pending_proposal,
    load_active_thresholds,
    propose_calibrated_thresholds,
    read_history,
    record_trade_score_outcome,
    save_proposal,
)


@dataclass
class _FakeTradeScore:
    tier: str = "strong"
    total_score: float = 115.0
    confluence_score: float = 30.0
    ev_score: float = 25.0
    risk_score: float = 20.0
    regime_fit_score: float = 15.0


class TestRecordTradeScoreOutcomeAndHistory:
    def test_round_trip(self, tmp_path) -> None:
        log_path = tmp_path / "history.jsonl"
        record_trade_score_outcome(_FakeTradeScore(), "long", 0.05, log_path=log_path)

        history = read_history(log_path=log_path)
        assert len(history) == 1
        row = history[0]
        assert row["direction"] == "long"
        assert row["actual_return_pct"] == 0.05
        assert row["tier"] == "strong"
        assert row["confluence_score"] == 30.0
        assert row["ev_score"] == 25.0
        assert row["risk_score"] == 20.0
        assert row["regime_fit_score"] == 15.0

    def test_none_trade_score_is_a_silent_no_op(self, tmp_path) -> None:
        log_path = tmp_path / "history.jsonl"
        record_trade_score_outcome(None, "long", 0.05, log_path=log_path)
        assert read_history(log_path=log_path) == []

    def test_missing_file_returns_empty_list(self, tmp_path) -> None:
        assert read_history(log_path=tmp_path / "never_written.jsonl") == []

    def test_write_failure_is_swallowed_not_raised(self, tmp_path) -> None:
        blocker = tmp_path / "not_a_dir"
        blocker.write_text("x")
        # log_path's parent is a FILE, not a directory -- mkdir(parents=True) must raise internally
        record_trade_score_outcome(_FakeTradeScore(), "long", 0.05, log_path=blocker / "history.jsonl")
        # No exception propagated -- that's the assertion.


def _history_row(confluence, ev, risk, regime_fit, actual_return_pct):
    return {
        "confluence_score": confluence, "ev_score": ev, "risk_score": risk,
        "regime_fit_score": regime_fit, "actual_return_pct": actual_return_pct,
    }


class TestComputeCalibrationMetrics:
    def test_below_min_sample_is_insufficient(self) -> None:
        history = [_history_row(30, 25, 20, 15, 0.05) for _ in range(5)]
        metrics = compute_calibration_metrics(history, min_sample=30)
        assert metrics["status"] == "insufficient_sample"
        assert metrics["n_entries"] == 5

    def test_enough_samples_computes_correlations(self) -> None:
        # confluence_score tracks actual_return_pct exactly -- correlation should be 1.0.
        # risk_score is constant -- correlation should read 0.0 (StatisticsError caught).
        history = [
            _history_row(confluence=i, ev=30 - i, risk=10.0, regime_fit=i % 3, actual_return_pct=i * 0.01)
            for i in range(30)
        ]
        metrics = compute_calibration_metrics(history, min_sample=30)
        assert metrics["status"] == "ok"
        assert metrics["n_entries"] == 30
        assert metrics["correlations"]["confluence_score"] == pytest.approx(1.0, abs=1e-9)
        assert metrics["correlations"]["ev_score"] == pytest.approx(-1.0, abs=1e-9)
        assert metrics["correlations"]["risk_score"] == 0.0


class TestProposeCalibratedThresholds:
    def test_insufficient_sample_returns_none(self) -> None:
        result = propose_calibrated_thresholds(
            TradeScoreThresholds(), {"status": "insufficient_sample"}, bound=0.2,
        )
        assert result is None

    def test_all_non_positive_correlations_returns_none(self) -> None:
        metrics = {
            "status": "ok",
            "correlations": {
                "confluence_score": -0.1, "ev_score": 0.0, "risk_score": -0.3, "regime_fit_score": 0.0,
            },
        }
        result = propose_calibrated_thresholds(TradeScoreThresholds(), metrics, bound=0.2)
        assert result is None

    def test_positive_signal_reallocates_within_bound(self) -> None:
        current = TradeScoreThresholds()  # 40/35/30/30, total 135
        metrics = {
            "status": "ok",
            "correlations": {
                "confluence_score": 0.8, "ev_score": 0.1, "risk_score": 0.05, "regime_fit_score": 0.0,
            },
        }
        result = propose_calibrated_thresholds(current, metrics, bound=0.2)

        assert result is not None
        # Each sub-max's change is strictly clamped to +-20% of its current
        # value -- the bound is never violated to force the total back to
        # its prior sum (see the function's own docstring on this tradeoff).
        assert result.confluence_max <= current.confluence_max * 1.2 + 1e-9
        assert result.ev_max >= current.ev_max * 0.8 - 1e-9
        assert result.risk_max >= current.risk_max * 0.8 - 1e-9
        assert result.regime_fit_max >= current.regime_fit_max * 0.8 - 1e-9
        # Tier cutoffs untouched.
        assert result.strong_threshold == current.strong_threshold
        assert result.moderate_threshold == current.moderate_threshold
        assert result.watch_threshold == current.watch_threshold

    def test_bound_is_never_violated_even_for_a_dominant_signal(self) -> None:
        # An extreme, single dominant correlation (previously exposed a bug
        # where post-clamp renormalization silently pushed confluence_max
        # to ~52, well past its +20% bound of 48).
        current = TradeScoreThresholds()
        metrics = {
            "status": "ok",
            "correlations": {
                "confluence_score": 0.95, "ev_score": 0.01, "risk_score": 0.0, "regime_fit_score": 0.0,
            },
        }
        result = propose_calibrated_thresholds(current, metrics, bound=0.2)

        assert result is not None
        for field, max_field in [
            ("confluence_score", "confluence_max"), ("ev_score", "ev_max"),
            ("risk_score", "risk_max"), ("regime_fit_score", "regime_fit_max"),
        ]:
            current_val = getattr(current, max_field)
            new_val = getattr(result, max_field)
            assert current_val * 0.8 - 1e-9 <= new_val <= current_val * 1.2 + 1e-9

    def test_never_moves_tier_cutoffs(self) -> None:
        current = TradeScoreThresholds(strong_threshold=120.0, moderate_threshold=95.0, watch_threshold=75.0)
        metrics = {
            "status": "ok",
            "correlations": {
                "confluence_score": 0.5, "ev_score": 0.3, "risk_score": 0.1, "regime_fit_score": 0.05,
            },
        }
        result = propose_calibrated_thresholds(current, metrics, bound=0.2)
        assert result.strong_threshold == 120.0
        assert result.moderate_threshold == 95.0
        assert result.watch_threshold == 75.0


class TestCalibrationState:
    def test_load_active_defaults_when_no_state_file(self, tmp_path) -> None:
        thresholds = load_active_thresholds(state_path=tmp_path / "state.json")
        assert thresholds == TradeScoreThresholds()

    def test_load_active_defaults_on_corrupt_file(self, tmp_path) -> None:
        state_path = tmp_path / "state.json"
        state_path.write_text("{not valid json")
        thresholds = load_active_thresholds(state_path=state_path)
        assert thresholds == TradeScoreThresholds()

    def test_save_and_read_pending_proposal(self, tmp_path) -> None:
        state_path = tmp_path / "state.json"
        proposed = TradeScoreThresholds(confluence_max=45.0)
        save_proposal(proposed, {"status": "ok", "n_entries": 30}, state_path=state_path)

        pending = get_pending_proposal(state_path=state_path)
        assert pending is not None
        assert pending["thresholds"]["confluence_max"] == 45.0
        assert pending["metrics"]["n_entries"] == 30
        # Not active yet.
        assert load_active_thresholds(state_path=state_path) == TradeScoreThresholds()

    def test_approve_proposal_moves_it_to_active(self, tmp_path) -> None:
        state_path = tmp_path / "state.json"
        proposed = TradeScoreThresholds(confluence_max=45.0)
        save_proposal(proposed, {"status": "ok"}, state_path=state_path)

        approved = approve_proposal("alice", state_path=state_path)

        assert approved.confluence_max == 45.0
        assert load_active_thresholds(state_path=state_path).confluence_max == 45.0
        assert get_pending_proposal(state_path=state_path) is None

    def test_approve_requires_a_pending_proposal(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            approve_proposal("alice", state_path=tmp_path / "state.json")

    def test_approve_requires_a_non_empty_approver(self, tmp_path) -> None:
        state_path = tmp_path / "state.json"
        save_proposal(TradeScoreThresholds(confluence_max=45.0), {"status": "ok"}, state_path=state_path)
        with pytest.raises(ValueError):
            approve_proposal("", state_path=state_path)

    def test_apply_directly_sets_active_without_a_proposal(self, tmp_path) -> None:
        state_path = tmp_path / "state.json"
        thresholds = TradeScoreThresholds(confluence_max=42.0)
        apply_directly(thresholds, {"status": "ok"}, state_path=state_path)

        assert load_active_thresholds(state_path=state_path).confluence_max == 42.0
        assert get_pending_proposal(state_path=state_path) is None


class TestApproveTradeScoreCalibrationMain:
    """cli.py's `approve-trade-score-calibration` subcommand -- previously
    approve_proposal had no caller reachable outside a Python REPL. Same
    CLI-first pattern as approve-decay's own TestApproveDecayMain, except
    this isn't artifact-keyed (one global pending proposal, or none)."""

    @staticmethod
    def _args(approver: str) -> "argparse.Namespace":
        import argparse
        return argparse.Namespace(approver=approver)

    def test_approves_and_prints_new_weights(self, tmp_path, monkeypatch, capsys) -> None:
        import vinu_research.trade_score_calibration as tsc
        from vinu_research.cli import approve_trade_score_calibration_main

        monkeypatch.setattr(tsc, "DEFAULT_STATE_PATH", str(tmp_path / "state.json"))
        save_proposal(TradeScoreThresholds(confluence_max=45.0), {"status": "ok"})

        approve_trade_score_calibration_main(self._args("alice"))

        out = capsys.readouterr().out
        assert "confluence_max=45.0" in out
        assert load_active_thresholds().confluence_max == 45.0

    def test_no_proposal_exits_nonzero(self, tmp_path, monkeypatch, capsys) -> None:
        import vinu_research.trade_score_calibration as tsc
        from vinu_research.cli import approve_trade_score_calibration_main

        monkeypatch.setattr(tsc, "DEFAULT_STATE_PATH", str(tmp_path / "state.json"))

        try:
            approve_trade_score_calibration_main(self._args("alice"))
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 1
        assert "Error" in capsys.readouterr().out
