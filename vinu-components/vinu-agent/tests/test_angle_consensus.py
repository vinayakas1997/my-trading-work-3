"""Tests for the cross-angle consensus check -- Phase 8 (New-talk-agents/
new-thinking/new-restructure/phases/phase-8-summary-agent-polish/). See
agent/angle_consensus.py.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.agent.angle_consensus import (
    AGREE,
    DIVERGE,
    INSUFFICIENT_DATA,
    compare_categorical,
    compare_directional,
    compare_magnitude,
    load_adjacency_table,
)


class TestCompareDirectional:
    def test_insufficient_data_when_either_angle_empty(self) -> None:
        result = compare_directional("arima", 0, 0.02, "chronos", 100, 0.03)
        assert result.outcome == INSUFFICIENT_DATA
        assert "arima" in result.reasoning

    def test_agreement_same_sign(self) -> None:
        result = compare_directional("arima", 100, 0.02, "chronos", 80, 0.05)
        assert result.outcome == AGREE

    def test_divergence_opposite_sign(self) -> None:
        result = compare_directional("arima", 100, 0.02, "chronos", 80, -0.01)
        assert result.outcome == DIVERGE

    def test_reasoning_cites_actual_values(self) -> None:
        result = compare_directional("arima", 100, 0.02, "chronos", 80, -0.01)
        assert "0.02" in result.reasoning
        assert "-0.01" in result.reasoning


class TestCompareMagnitude:
    def test_insufficient_data(self) -> None:
        result = compare_magnitude("arima", 0, 0.02, "chronos", 100, 0.021)
        assert result.outcome == INSUFFICIENT_DATA

    def test_within_tolerance_agrees(self) -> None:
        result = compare_magnitude("arima", 100, 0.020, "chronos", 100, 0.021, tolerance=0.15)
        assert result.outcome == AGREE

    def test_beyond_tolerance_diverges(self) -> None:
        result = compare_magnitude("arima", 100, 0.020, "chronos", 100, 0.050, tolerance=0.15)
        assert result.outcome == DIVERGE

    def test_reasoning_cites_actual_values_and_tolerance(self) -> None:
        result = compare_magnitude("arima", 100, 0.020, "chronos", 100, 0.050, tolerance=0.15)
        assert "0.02" in result.reasoning
        assert "0.05" in result.reasoning
        assert "15%" in result.reasoning


class TestCompareCategorical:
    def test_insufficient_data(self) -> None:
        result = compare_categorical("regime_analysis", 0, "bull", "trend_lifecycle", 50, "uptrend")
        assert result.outcome == INSUFFICIENT_DATA

    def test_exact_match_agrees(self) -> None:
        result = compare_categorical("regime_analysis", 50, "sideways", "trend_lifecycle", 50, "sideways")
        assert result.outcome == AGREE
        assert "exact match" in result.reasoning

    def test_adjacent_labels_agree_via_config(self) -> None:
        result = compare_categorical(
            "regime_analysis", 50, "bull", "trend_lifecycle", 50, "uptrend",
            adjacency_table={"regime_analysis": {"trend_lifecycle": {"bull": ["uptrend", "basing"]}}},
        )
        assert result.outcome == AGREE

    def test_non_adjacent_labels_diverge(self) -> None:
        result = compare_categorical(
            "regime_analysis", 50, "bull", "trend_lifecycle", 50, "downtrend",
            adjacency_table={"regime_analysis": {"trend_lifecycle": {"bull": ["uptrend", "basing"]}}},
        )
        assert result.outcome == DIVERGE

    def test_adjacency_lookup_is_order_independent(self) -> None:
        table = {"regime_analysis": {"trend_lifecycle": {"bull": ["uptrend"]}}}
        # Called with trend_lifecycle as "a" and regime_analysis as "b" --
        # must still resolve correctly regardless of call order.
        result = compare_categorical(
            "trend_lifecycle", 50, "uptrend", "regime_analysis", 50, "bull",
            adjacency_table=table,
        )
        assert result.outcome == AGREE

    def test_config_edit_changes_the_outcome_without_any_code_change(self, tmp_path: Path) -> None:
        """Proves the adjacency table is externally configurable, not
        hardcoded in prose (03-test.md)."""
        config_path = tmp_path / "adjacency.yaml"
        config_path.write_text(
            "regime_analysis:\n  trend_lifecycle:\n    bull: []\n", encoding="utf-8",
        )
        table_v1 = load_adjacency_table(config_path)
        result_v1 = compare_categorical(
            "regime_analysis", 50, "bull", "trend_lifecycle", 50, "uptrend", adjacency_table=table_v1,
        )
        assert result_v1.outcome == DIVERGE

        config_path.write_text(
            "regime_analysis:\n  trend_lifecycle:\n    bull: [uptrend]\n", encoding="utf-8",
        )
        table_v2 = load_adjacency_table(config_path)
        result_v2 = compare_categorical(
            "regime_analysis", 50, "bull", "trend_lifecycle", 50, "uptrend", adjacency_table=table_v2,
        )
        assert result_v2.outcome == AGREE

    def test_load_adjacency_table_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_adjacency_table(tmp_path / "nonexistent.yaml") == {}

    def test_default_adjacency_table_loads_the_real_shipped_config(self) -> None:
        table = load_adjacency_table()
        assert "regime_analysis" in table
        assert "trend_lifecycle" in table["regime_analysis"]
        assert "uptrend" in table["regime_analysis"]["trend_lifecycle"]["bull"]
