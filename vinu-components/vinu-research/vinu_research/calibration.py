from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from vinu_research.forecast_skill import (
    ForecastSkillConfig,
    compute_angle_calibration,
    compute_brier_score,
    compute_calibration,
    compute_directional_error,
)
from vinu_research.models import AngleCalibrationResult, CalibrationEntry, CalibrationResult, Forecast

if TYPE_CHECKING:
    from vinu_research.storage.strategy_store import SqliteStrategyStore

logger = logging.getLogger(__name__)


def get_angle_calibration(store: "SqliteStrategyStore", angle_name: str) -> AngleCalibrationResult:
    """Read-only aggregate for one angle across every artifact it has ever
    been attributed to (Artifact.origin_angles) -- the real per-angle
    trust signal the Summary Agent needs (previously nonexistent, see
    trade_plan_authoring.py's record_realized_outcome, the one write
    path). An angle with zero entries (never attributed to any closed
    position yet) returns n_entries=0, not an error."""
    entries = store.get_angle_calibration_entries(angle_name)
    return compute_angle_calibration(angle_name, entries)


class CalibrationTracker:
    """Tracks forecast accuracy over a sliding window and determines pass/fail.

    Extends the existing decay.py pattern — calibration is a complementary
    health metric alongside decay snapshots.
    """

    def __init__(
        self,
        artifact_id: str,
        config: ForecastSkillConfig | None = None,
    ) -> None:
        self.artifact_id = artifact_id
        self.config = config or ForecastSkillConfig()
        self._entries: list[CalibrationEntry] = []

    @property
    def entries(self) -> list[CalibrationEntry]:
        return list(self._entries)

    def load_entries(self, entries: list[CalibrationEntry]) -> None:
        """Bulk-load already-scored entries (e.g. read back from persistent storage).

        Unlike `add_entry`, this trusts the entries' scores as given rather than
        recomputing them from a `Forecast` -- used by Phase 7's `load_calibration_tracker`
        to reconstruct a tracker's state across process restarts.
        """
        self._entries = list(entries)

    def add_entry(
        self,
        forecast: Forecast,
        actual_return_pct: float,
    ) -> CalibrationEntry:
        entry = CalibrationEntry(
            artifact_id=self.artifact_id,
            forecast_direction=forecast.direction,
            actual_return_pct=actual_return_pct,
            forecast_magnitude_pct=forecast.magnitude_pct,
            brier_score=compute_brier_score(
                forecast.direction, forecast.confidence, actual_return_pct,
            ),
            directional_correct=compute_directional_error(
                forecast.direction, actual_return_pct,
            ),
            magnitude_error=(
                abs(forecast.magnitude_pct - actual_return_pct)
                / max(abs(actual_return_pct), 0.001)
                if forecast.magnitude_pct > 0
                else 0.0
            ),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._entries.append(entry)
        return entry

    def evaluate(self) -> CalibrationResult:
        return compute_calibration(self._entries, self.config)

    def clear(self) -> None:
        self._entries.clear()


class CalibrationGate:
    """Fail-closed gate that blocks trade-plan approval unless calibration passes.

    Used by the approval flow — if the gate is closed, the plan cannot be
    promoted to ACTIVE.
    """

    def __init__(
        self,
        tracker: CalibrationTracker,
        min_window: int = 10,
    ) -> None:
        self._tracker = tracker
        self._min_window = min_window

    def is_open(self) -> bool:
        result = self._tracker.evaluate()
        return result.n_entries >= self._min_window and result.passed

    def check(self) -> CalibrationResult:
        result = self._tracker.evaluate()
        if not self.is_open():
            result.passed = False
            if result.n_entries < self._min_window:
                result.reasons.append(
                    f"calibration window too small ({result.n_entries} < {self._min_window})"
                )
        return result
