from __future__ import annotations

import pytest

from vinu_research.storage.signal_evidence_store import SignalEvidenceStore
from vinu_research.track2_aggregate import compute_track2_aggregate


@pytest.fixture
def store(tmp_path):
    s = SignalEvidenceStore(tmp_path / "test_signal_evidence.db")
    yield s
    s.close()


def _trigger(store, trigger_id, trigger_time, *, symbol="AAPL", condition="sma5_cross_sma50"):
    store.record_trigger(trigger_id, symbol, trigger_time, condition, {})


def _trigger_with_indicators(
    store, trigger_id, trigger_time, indicators, *, symbol="AAPL", condition="sma5_cross_sma50",
):
    store.record_trigger(trigger_id, symbol, trigger_time, condition, indicators)


def _resolve(store, trigger_id, return_at_horizon):
    store.record_outcome(
        trigger_id,
        max_favorable_excursion=abs(return_at_horizon),
        max_adverse_excursion=-abs(return_at_horizon),
        return_at_horizon=return_at_horizon,
    )


class TestComputeTrack2Aggregate:
    def test_no_triggers_at_all_returns_insufficient_with_zero_sample(self, store):
        result = compute_track2_aggregate("AAPL", "sma5_cross_sma50", evidence_store=store)

        assert result["sample_size"] == 0
        assert result["insufficient_evidence"] is True
        assert result["win_rate"] is None
        assert result["evidence_confidence"] is None

    def test_unresolved_trigger_is_excluded_from_the_sample(self, store):
        _trigger(store, "t1", "2026-09-01T00:00:00+00:00")

        result = compute_track2_aggregate("AAPL", "sma5_cross_sma50", evidence_store=store)

        assert result["sample_size"] == 0

    def test_a_different_must_condition_is_excluded(self, store):
        _trigger(store, "t1", "2026-09-01T00:00:00+00:00", condition="other_condition")
        _resolve(store, "t1", 0.02)

        result = compute_track2_aggregate("AAPL", "sma5_cross_sma50", evidence_store=store)

        assert result["sample_size"] == 0

    def test_a_different_symbol_is_excluded(self, store):
        _trigger(store, "t1", "2026-09-01T00:00:00+00:00", symbol="MSFT")
        _resolve(store, "t1", 0.02)

        result = compute_track2_aggregate("AAPL", "sma5_cross_sma50", evidence_store=store)

        assert result["sample_size"] == 0

    def test_win_rate_and_laplace_smoothed_confidence(self, store):
        for i, ret in enumerate([0.02, 0.03, -0.01, 0.01]):
            tid = f"t{i}"
            _trigger(store, tid, f"2026-09-0{i + 1}T00:00:00+00:00")
            _resolve(store, tid, ret)

        result = compute_track2_aggregate(
            "AAPL", "sma5_cross_sma50", evidence_store=store, min_sample_size=5,
        )

        assert result["sample_size"] == 4
        assert result["win_rate"] == 0.75  # 3 of 4 positive
        assert result["evidence_confidence"] == pytest.approx((3 + 1) / (4 + 2))
        assert result["insufficient_evidence"] is True  # below min_sample_size=5

    def test_sample_size_at_or_above_threshold_is_not_flagged_insufficient(self, store):
        for i, ret in enumerate([0.02, 0.03, -0.01, 0.01, 0.02]):
            tid = f"t{i}"
            _trigger(store, tid, f"2026-09-0{i + 1}T00:00:00+00:00")
            _resolve(store, tid, ret)

        result = compute_track2_aggregate(
            "AAPL", "sma5_cross_sma50", evidence_store=store, min_sample_size=5,
        )

        assert result["sample_size"] == 5
        assert result["insufficient_evidence"] is False

    def test_as_of_excludes_evidence_not_yet_known_at_that_instant(self, store):
        """Point-in-time safety: a trigger whose outcome was recorded AFTER
        `as_of` must not leak into the aggregate -- that would be
        lookahead for a simulator replaying history."""
        _trigger(store, "t1", "2026-09-01T00:00:00+00:00")
        _resolve(store, "t1", 0.02)

        # outcome_recorded_at is "now" (real wall-clock, set inside
        # record_outcome) -- so an as_of far in the past must exclude it.
        past_as_of = 1_600_000_000  # 2020-09-13

        result = compute_track2_aggregate(
            "AAPL", "sma5_cross_sma50", evidence_store=store, as_of=past_as_of,
        )

        assert result["sample_size"] == 0

    def test_as_of_includes_evidence_already_known_by_that_instant(self, store):
        _trigger(store, "t1", "2026-09-01T00:00:00+00:00")
        _resolve(store, "t1", 0.02)

        future_as_of = 4_100_000_000  # far in the future

        result = compute_track2_aggregate(
            "AAPL", "sma5_cross_sma50", evidence_store=store, as_of=future_as_of,
        )

        assert result["sample_size"] == 1

    def test_avg_return_at_horizon_and_days_since_last_trigger(self, store):
        _trigger(store, "t1", "2026-09-01T00:00:00+00:00")
        _resolve(store, "t1", 0.02)
        _trigger(store, "t2", "2026-09-05T00:00:00+00:00")
        _resolve(store, "t2", -0.04)

        result = compute_track2_aggregate("AAPL", "sma5_cross_sma50", evidence_store=store)

        assert result["avg_return_at_horizon"] == pytest.approx((0.02 - 0.04) / 2)
        assert result["days_since_last_trigger"] is not None
        assert result["days_since_last_trigger"] >= 0


class TestRegimeAwareAggregate:
    """A1 fix: the aggregate reads the recorded regime/news_confound
    indicators instead of blending every trigger into one number."""

    def test_same_condition_in_bull_vs_bear_yields_separate_confidences(self, store):
        for i, ret in enumerate([0.02, 0.03, 0.01]):
            tid = f"bull{i}"
            _trigger_with_indicators(store, tid, f"2026-09-0{i + 1}T00:00:00+00:00", {"regime": "bull"})
            _resolve(store, tid, ret)
        for i, ret in enumerate([-0.02, -0.03, -0.01]):
            tid = f"bear{i}"
            _trigger_with_indicators(store, tid, f"2026-09-1{i + 1}T00:00:00+00:00", {"regime": "bear"})
            _resolve(store, tid, ret)

        result = compute_track2_aggregate("AAPL", "sma5_cross_sma50", evidence_store=store)

        assert result["sample_size"] == 6  # overall number unchanged
        bull = result["by_regime"]["bull"]
        bear = result["by_regime"]["bear"]
        assert bull["sample_size"] == 3
        assert bear["sample_size"] == 3
        assert bull["evidence_confidence"] == pytest.approx((3 + 1) / (3 + 2))
        assert bear["evidence_confidence"] == pytest.approx((0 + 1) / (3 + 2))
        assert bull["evidence_confidence"] > bear["evidence_confidence"]

    def test_news_confounded_triggers_flagged_and_excluded_from_ex_news(self, store):
        clean = {"regime": "bull", "news_confound": {"occurred": False, "minutes_before": None, "article_id": None}}
        confounded = {"regime": "bull", "news_confound": {"occurred": True, "minutes_before": 12.0, "article_id": "a1"}}
        _trigger_with_indicators(store, "c1", "2026-09-01T00:00:00+00:00", clean)
        _resolve(store, "c1", 0.02)
        _trigger_with_indicators(store, "c2", "2026-09-02T00:00:00+00:00", clean)
        _resolve(store, "c2", 0.03)
        _trigger_with_indicators(store, "n1", "2026-09-03T00:00:00+00:00", confounded)
        _resolve(store, "n1", 0.05)

        result = compute_track2_aggregate("AAPL", "sma5_cross_sma50", evidence_store=store)

        bull = result["by_regime"]["bull"]
        assert bull["sample_size"] == 3
        assert bull["news_confounded"] == 1
        assert bull["ex_news"]["sample_size"] == 2
        assert bull["ex_news"]["evidence_confidence"] == pytest.approx((2 + 1) / (2 + 2))
        assert result["news_confounded_total"] == 1

    def test_triggers_without_regime_land_in_unknown_bucket(self, store):
        _trigger(store, "t1", "2026-09-01T00:00:00+00:00")  # {} indicators, no regime
        _resolve(store, "t1", 0.02)

        result = compute_track2_aggregate("AAPL", "sma5_cross_sma50", evidence_store=store)

        assert result["by_regime"]["unknown"]["sample_size"] == 1

    def test_bucket_samples_reconcile_with_overall_sample(self, store):
        _trigger_with_indicators(store, "b1", "2026-09-01T00:00:00+00:00", {"regime": "bull"})
        _resolve(store, "b1", 0.02)
        _trigger_with_indicators(store, "b2", "2026-09-02T00:00:00+00:00", {"regime": "bear"})
        _resolve(store, "b2", -0.01)
        _trigger(store, "u1", "2026-09-03T00:00:00+00:00")
        _resolve(store, "u1", 0.01)

        result = compute_track2_aggregate("AAPL", "sma5_cross_sma50", evidence_store=store)

        assert sum(b["sample_size"] for b in result["by_regime"].values()) == result["sample_size"]
