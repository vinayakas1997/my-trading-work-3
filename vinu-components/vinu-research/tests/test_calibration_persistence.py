from __future__ import annotations

from vinu_research.forecast_skill import ForecastSkillConfig
from vinu_research.models import AngleCalibrationEntry, CalibrationEntry, Forecast, TradePlan
from vinu_research.trade_plan_authoring import (
    approve_trade_plan,
    freeze_trade_plan,
    load_calibration_tracker,
    record_realized_outcome,
)


def _sample_plan(direction: str = "long") -> TradePlan:
    return TradePlan(
        symbol="AAPL",
        timeframe="daily",
        direction=direction,
        position_size_pct=0.05,
        forecast=Forecast(direction=direction, confidence=0.6, magnitude_pct=0.02, magnitude_std=0.01),
    )


class TestAppendAndGetCalibrationEntries:
    def test_round_trips(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan())
        entry = CalibrationEntry(
            artifact_id=artifact.artifact_id, forecast_direction="long", actual_return_pct=0.03,
            forecast_magnitude_pct=0.02, brier_score=0.01, directional_correct=True,
            magnitude_error=0.5, timestamp="2026-07-27T00:00:00Z",
        )
        strategy_store.append_calibration_entry(entry)
        entries = strategy_store.get_calibration_entries(artifact.artifact_id)
        assert len(entries) == 1
        assert entries[0].actual_return_pct == 0.03
        assert entries[0].directional_correct is True

    def test_empty_for_unknown_artifact(self, strategy_store) -> None:
        assert strategy_store.get_calibration_entries("does_not_exist") == []

    def test_ordered_by_insertion(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan())
        for i in range(3):
            strategy_store.append_calibration_entry(CalibrationEntry(
                artifact_id=artifact.artifact_id, forecast_direction="long",
                actual_return_pct=0.01 * i, timestamp=f"t{i}",
            ))
        entries = strategy_store.get_calibration_entries(artifact.artifact_id)
        assert [e.timestamp for e in entries] == ["t0", "t1", "t2"]

    def test_delete_artifact_cleans_up_calibration_entries(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan())
        strategy_store.append_calibration_entry(CalibrationEntry(
            artifact_id=artifact.artifact_id, forecast_direction="long", actual_return_pct=0.03,
        ))
        strategy_store.delete_artifact(artifact.artifact_id)
        assert strategy_store.get_calibration_entries(artifact.artifact_id) == []


class TestRecordRealizedOutcome:
    def test_scores_a_winning_long_forecast(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan("long"))
        entry = record_realized_outcome(strategy_store, artifact.artifact_id, 0.03)
        assert entry.directional_correct is True
        assert entry.forecast_direction == "long"
        persisted = strategy_store.get_calibration_entries(artifact.artifact_id)
        assert len(persisted) == 1

    def test_scores_a_losing_long_forecast(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan("long"))
        entry = record_realized_outcome(strategy_store, artifact.artifact_id, -0.02)
        assert entry.directional_correct is False

    def test_scores_a_winning_short_forecast(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan("short"))
        entry = record_realized_outcome(strategy_store, artifact.artifact_id, -0.02)
        assert entry.directional_correct is True

    def test_raises_for_missing_artifact(self, strategy_store) -> None:
        import pytest
        with pytest.raises(ValueError):
            record_realized_outcome(strategy_store, "does_not_exist", 0.03)

    def test_raises_when_plan_has_no_forecast(self, strategy_store) -> None:
        import pytest
        plan = TradePlan(symbol="AAPL", timeframe="daily", direction="long")
        artifact = freeze_trade_plan(strategy_store, plan)
        with pytest.raises(ValueError):
            record_realized_outcome(strategy_store, artifact.artifact_id, 0.03)


class TestAngleCalibrationEntries:
    def test_round_trips(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan())
        entry = AngleCalibrationEntry(
            angle_name="patchtst", artifact_id=artifact.artifact_id, forecast_direction="long",
            actual_return_pct=0.03, forecast_magnitude_pct=0.02, brier_score=0.01,
            directional_correct=True, magnitude_error=0.5, timestamp="2026-07-27T00:00:00Z",
        )
        strategy_store.append_angle_calibration_entry(entry)
        entries = strategy_store.get_angle_calibration_entries("patchtst")
        assert len(entries) == 1
        assert entries[0].artifact_id == artifact.artifact_id
        assert entries[0].actual_return_pct == 0.03

    def test_empty_for_unknown_angle(self, strategy_store) -> None:
        assert strategy_store.get_angle_calibration_entries("does_not_exist") == []

    def test_ordered_by_insertion(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan())
        for i in range(3):
            strategy_store.append_angle_calibration_entry(AngleCalibrationEntry(
                angle_name="patchtst", artifact_id=artifact.artifact_id, forecast_direction="long",
                actual_return_pct=0.01 * i, timestamp=f"t{i}",
            ))
        entries = strategy_store.get_angle_calibration_entries("patchtst")
        assert [e.timestamp for e in entries] == ["t0", "t1", "t2"]

    def test_delete_artifact_cleans_up_angle_calibration_entries(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan())
        strategy_store.append_angle_calibration_entry(AngleCalibrationEntry(
            angle_name="patchtst", artifact_id=artifact.artifact_id, forecast_direction="long",
            actual_return_pct=0.03,
        ))
        strategy_store.delete_artifact(artifact.artifact_id)
        assert strategy_store.get_angle_calibration_entries("patchtst") == []


class TestOriginAnglesPersistence:
    def test_round_trips_through_upsert_and_get(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan())
        artifact.origin_angles = ["patchtst", "shock_personality"]
        strategy_store.upsert_artifact(artifact)

        fetched = strategy_store.get_artifact(artifact.artifact_id)
        assert fetched.origin_angles == ["patchtst", "shock_personality"]

    def test_defaults_to_empty_list(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan())
        fetched = strategy_store.get_artifact(artifact.artifact_id)
        assert fetched.origin_angles == []


class TestRecordRealizedOutcomeAngleFanout:
    def test_fans_out_one_entry_per_origin_angle(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan("long"))
        artifact.origin_angles = ["patchtst", "shock_personality"]
        strategy_store.upsert_artifact(artifact)

        record_realized_outcome(strategy_store, artifact.artifact_id, 0.03)

        patchtst_entries = strategy_store.get_angle_calibration_entries("patchtst")
        shock_entries = strategy_store.get_angle_calibration_entries("shock_personality")
        assert len(patchtst_entries) == 1
        assert len(shock_entries) == 1
        # Same real outcome, attributed to both -- not independently recomputed.
        assert patchtst_entries[0].actual_return_pct == shock_entries[0].actual_return_pct
        assert patchtst_entries[0].directional_correct == shock_entries[0].directional_correct
        assert patchtst_entries[0].artifact_id == artifact.artifact_id

    def test_no_origin_angles_writes_no_angle_entries(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan("long"))
        record_realized_outcome(strategy_store, artifact.artifact_id, 0.03)
        assert strategy_store.get_angle_calibration_entries("patchtst") == []

    def test_trade_plan_calibration_entry_unaffected_by_angle_fanout(self, strategy_store) -> None:
        """The existing, already-tested trade-plan-level write must behave
        identically whether or not origin_angles is populated."""
        artifact = freeze_trade_plan(strategy_store, _sample_plan("long"))
        artifact.origin_angles = ["patchtst"]
        strategy_store.upsert_artifact(artifact)

        entry = record_realized_outcome(strategy_store, artifact.artifact_id, 0.03)
        assert entry.directional_correct is True
        assert len(strategy_store.get_calibration_entries(artifact.artifact_id)) == 1


class TestLoadCalibrationTracker:
    def test_reconstructs_tracker_matching_a_freshly_fed_one(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan("long"))
        cfg = ForecastSkillConfig(min_calibration_window=3)
        for ret in (0.03, 0.02, 0.04):
            record_realized_outcome(strategy_store, artifact.artifact_id, ret, cfg)

        tracker = load_calibration_tracker(strategy_store, artifact.artifact_id, cfg)
        result = tracker.evaluate()
        assert result.n_entries == 3
        assert result.accuracy == 1.0

    def test_empty_when_no_entries(self, strategy_store) -> None:
        tracker = load_calibration_tracker(strategy_store, "art_none")
        assert tracker.entries == []


class TestApproveEndToEnd:
    def test_approve_fails_then_succeeds_as_entries_accumulate(self, strategy_store) -> None:
        artifact = freeze_trade_plan(strategy_store, _sample_plan("long"))
        cfg = ForecastSkillConfig(min_calibration_window=3)

        import pytest
        from vinu_research.trade_plan_authoring import TradePlanApprovalError
        with pytest.raises(TradePlanApprovalError):
            approve_trade_plan(strategy_store, artifact.artifact_id, cfg)

        for ret in (0.03, 0.02, 0.04):
            record_realized_outcome(strategy_store, artifact.artifact_id, ret, cfg)

        approved = approve_trade_plan(strategy_store, artifact.artifact_id, cfg)
        assert approved.status.value == "ACTIVE"
