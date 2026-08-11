"""End-to-end scenario test for Phase 8 (New-talk-agents/new-thinking/
new-restructure/phases/phase-8-summary-agent-polish/) -- proves the
consensus check and calibration wiring work together without the
grounding discipline breaking anywhere, using the same realistic mix
03-test.md's end-to-end case describes: agreeing angles, diverging
angles, one empty angle, and calibration spanning both high- and
low-trust cases.

This exercises the real deterministic functions directly (agent/
angle_consensus.py, agent/trade_plan_calibration.py) -- not a live LLM
call. Confirming the LLM actually follows the updated prompt.md (calls
the right tools, reports each condition distinctly in prose) needs a real
multi-turn agent run against the configured model, deliberately not done
here -- same limitation flagged for Phase 1's prompt-behavior tests, for
the same reason (a real LLM call is expensive/slow to fold into the fast
unit suite, and free-tier rate limits are a real, already-confirmed risk
this session). What IS proven here: the tools this phase built produce
correct, distinctly-labeled results for every condition the Summary
Agent's prompt now instructs it to report, so if the LLM calls them and
reports their outputs faithfully (which the prompt explicitly requires),
the full behavior holds.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.agent.angle_consensus import (
    AGREE,
    DIVERGE,
    INSUFFICIENT_DATA,
    compare_categorical,
    compare_directional,
)
from vinu_agent.agent.trade_plan_calibration import get_trade_plan_calibration
from vinu_research.models import Artifact, CalibrationEntry
from vinu_research.storage.strategy_store import SqliteStrategyStore


@pytest.fixture
def strategy_store(monkeypatch):
    data_root = Path(tempfile.mkdtemp())
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(data_root))
    store = SqliteStrategyStore(data_root / "strategy_store.db")
    yield store
    store.close()


def test_phase8_full_summary_with_consensus_and_calibration(strategy_store) -> None:
    # --- Realistic mix of angle data for one ticker, "AAPL" ---
    angles = {
        # Two directional angles that AGREE (same sign).
        "arima": {"row_count": 100, "forecast_return_pct": 0.021},
        "chronos": {"row_count": 80, "forecast_return_pct": 0.015},
        # Two categorical angles that DIVERGE (not adjacent per config).
        "regime_analysis": {"row_count": 120, "regime": "bear"},
        "trend_lifecycle": {"row_count": 90, "stage": "uptrend"},
        # One angle with no data at all.
        "kronos": {"row_count": 0},
    }

    directional = compare_directional(
        "arima", angles["arima"]["row_count"], angles["arima"]["forecast_return_pct"],
        "chronos", angles["chronos"]["row_count"], angles["chronos"]["forecast_return_pct"],
    )
    categorical = compare_categorical(
        "regime_analysis", angles["regime_analysis"]["row_count"], angles["regime_analysis"]["regime"],
        "trend_lifecycle", angles["trend_lifecycle"]["row_count"], angles["trend_lifecycle"]["stage"],
    )
    empty_comparison = compare_directional(
        "kronos", angles["kronos"]["row_count"], 0.0,
        "arima", angles["arima"]["row_count"], angles["arima"]["forecast_return_pct"],
    )

    # Condition 1: agreeing angles cited together, with real values.
    assert directional.outcome == AGREE
    assert "0.021" in directional.reasoning
    assert "0.015" in directional.reasoning

    # Condition 2: diverging angles flagged, with both real values.
    assert categorical.outcome == DIVERGE
    assert "bear" in categorical.reasoning
    assert "uptrend" in categorical.reasoning

    # Condition 3: the empty angle marked insufficient-data, not silently
    # dropped, not treated as disagreement.
    assert empty_comparison.outcome == INSUFFICIENT_DATA
    assert empty_comparison.outcome != DIVERGE

    # --- Calibration spanning both high- and low-trust cases ---
    high_trust_artifact = Artifact.create("trade_plan", "aapl-plan-good", universe=["AAPL"])
    strategy_store.upsert_artifact(high_trust_artifact)
    for _ in range(15):
        strategy_store.append_calibration_entry(CalibrationEntry(
            artifact_id=high_trust_artifact.artifact_id, forecast_direction="up",
            actual_return_pct=0.02, forecast_magnitude_pct=0.02, brier_score=0.05,
            directional_correct=True, magnitude_error=0.01, timestamp="2026-01-01T00:00:00Z",
        ))

    low_trust_artifact = Artifact.create("trade_plan", "aapl-plan-weak", universe=["AAPL"])
    strategy_store.upsert_artifact(low_trust_artifact)
    for i in range(15):
        strategy_store.append_calibration_entry(CalibrationEntry(
            artifact_id=low_trust_artifact.artifact_id, forecast_direction="up",
            actual_return_pct=-0.01 if i % 2 == 0 else 0.01, forecast_magnitude_pct=0.02,
            brier_score=0.6, directional_correct=(i % 2 != 0), magnitude_error=0.5,
            timestamp="2026-01-01T00:00:00Z",
        ))

    high_trust_result = get_trade_plan_calibration(high_trust_artifact.artifact_id)
    low_trust_result = get_trade_plan_calibration(low_trust_artifact.artifact_id)

    # Condition 4: low-calibration angle flagged as "has data, less
    # trustworthy" (n_entries > 0 but passed=False), never simply omitted
    # the way a row_count=0 angle would be.
    assert high_trust_result["n_entries"] > 0
    assert high_trust_result["passed"] is True
    assert low_trust_result["n_entries"] > 0
    assert low_trust_result["passed"] is False
    # Both have real data (n_entries > 0) -- the distinction is in
    # `passed`, not in whether data exists at all. This is exactly the
    # "has data but underperformed" vs. "no data" distinction the guard
    # rail requires stay visibly separate.
    assert high_trust_result["n_entries"] > 0 and low_trust_result["n_entries"] > 0
