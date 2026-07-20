from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

LOG = logging.getLogger(__name__)


@dataclass
class ReconciliationReport:
    drift_detected: bool = False
    symbol_drifts: list[dict[str, Any]] = field(default_factory=list)
    total_drift_pct: float = 0.0


class ReconciliationEngine:
    """Compares broker-reported positions against expected state.

    After each order cycle (C1→C2), this engine checks whether actual
    positions match what the portfolio service expects. Drift alerts
    can be wired to the notification/alerting system (Phase E).
    """

    def reconcile(
        self,
        expected_positions: dict[str, float],
        actual_positions: dict[str, float],
        portfolio_value: float,
    ) -> ReconciliationReport:
        """Compare expected vs actual positions.

        Args:
            expected_positions: {symbol: qty} from the portfolio service.
            actual_positions: {symbol: qty} from the broker.
            portfolio_value: Total portfolio value for pct calculations.

        Returns:
            ReconciliationReport with any drifts detected.
        """
        report = ReconciliationReport()
        all_symbols = set(expected_positions) | set(actual_positions)

        for sym in sorted(all_symbols):
            expected = expected_positions.get(sym, 0.0)
            actual = actual_positions.get(sym, 0.0)
            diff = actual - expected

            if abs(diff) < 0.001:
                continue

            drift_pct = diff / (abs(expected) + 1e-6) * 100 if expected != 0 else float("inf")
            report.symbol_drifts.append({
                "symbol": sym,
                "expected_qty": round(expected, 4),
                "actual_qty": round(actual, 4),
                "diff": round(diff, 4),
                "drift_pct": round(drift_pct, 2),
            })
            report.drift_detected = True

        if report.symbol_drifts:
            total_diff = sum(abs(d["diff"]) for d in report.symbol_drifts)
            report.total_drift_pct = round(
                total_diff / (portfolio_value + 1e-6) * 100, 2
            )

        return report
