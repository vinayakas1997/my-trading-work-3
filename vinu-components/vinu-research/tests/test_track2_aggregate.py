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
