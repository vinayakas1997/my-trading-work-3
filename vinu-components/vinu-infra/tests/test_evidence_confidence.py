"""vinu_infra.evidence_confidence is the single source of truth for
point-in-time evidence-confidence math shared by vinu-research's
track2_aggregate.py and vinu-simulator's EvidenceConfidenceSizer -- these
pin the exact Laplace-smoothing formula and the as_of lookahead cut so
the two callers can never silently diverge."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vinu_infra.evidence_confidence import laplace_smoothed_win_rate, summarize_resolved_triggers


class TestLaplaceSmoothedWinRate:
    def test_all_wins_still_pulled_below_one(self) -> None:
        assert laplace_smoothed_win_rate(3, 3) == pytest.approx(4 / 5)

    def test_all_losses_still_pulled_above_zero(self) -> None:
        assert laplace_smoothed_win_rate(0, 3) == pytest.approx(1 / 5)

    def test_converges_toward_raw_win_rate_as_sample_grows(self) -> None:
        small = laplace_smoothed_win_rate(7, 10)
        large = laplace_smoothed_win_rate(700, 1000)
        assert abs(large - 0.7) < abs(small - 0.7)


def _resolved(trigger_time, outcome_recorded_at, return_at_horizon):
    return {
        "trigger_time": trigger_time,
        "outcome_recorded_at": outcome_recorded_at,
        "return_at_horizon": return_at_horizon,
    }


class TestSummarizeResolvedTriggers:
    def test_empty_input_is_insufficient_not_a_computed_zero(self) -> None:
        result = summarize_resolved_triggers([])

        assert result["sample_size"] == 0
        assert result["win_rate"] is None
        assert result["evidence_confidence"] is None

    def test_basic_win_rate_and_confidence(self) -> None:
        triggers = [
            _resolved("2026-09-01T00:00:00+00:00", "2026-09-02T00:00:00+00:00", 0.02),
            _resolved("2026-09-03T00:00:00+00:00", "2026-09-04T00:00:00+00:00", 0.01),
            _resolved("2026-09-05T00:00:00+00:00", "2026-09-06T00:00:00+00:00", -0.03),
        ]

        result = summarize_resolved_triggers(triggers)

        assert result["sample_size"] == 3
        assert result["win_rate"] == pytest.approx(2 / 3)
        assert result["evidence_confidence"] == pytest.approx(laplace_smoothed_win_rate(2, 3))
        assert result["avg_return_at_horizon"] == pytest.approx((0.02 + 0.01 - 0.03) / 3)

    def test_as_of_excludes_outcomes_recorded_after_it(self) -> None:
        triggers = [
            _resolved("2026-09-01T00:00:00+00:00", "2026-09-02T00:00:00+00:00", 0.02),
            _resolved("2026-09-10T00:00:00+00:00", "2026-09-11T00:00:00+00:00", -0.05),
        ]

        result = summarize_resolved_triggers(
            triggers, as_of_iso="2026-09-05T00:00:00+00:00",
        )

        assert result["sample_size"] == 1
        assert result["win_rate"] == 1.0

    def test_days_since_last_trigger_uses_the_most_recent_trigger_time(self) -> None:
        triggers = [
            _resolved("2026-09-01T00:00:00+00:00", "2026-09-02T00:00:00+00:00", 0.02),
            _resolved("2026-09-05T00:00:00+00:00", "2026-09-06T00:00:00+00:00", 0.01),
        ]
        reference_now = datetime(2026, 9, 10, tzinfo=timezone.utc)

        result = summarize_resolved_triggers(triggers, reference_now=reference_now)

        assert result["days_since_last_trigger"] == 5
