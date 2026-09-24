"""Tests for TradePlanTool._read_summary_context -- the real assembly
point that turns a stored TickerSummary row into the summary_context
dict forecast_skill's prompt eventually reads. No prior test file
covered this (a real pre-existing gap, not introduced here); added
while wiring cluster_digest/cross_cluster through it (step 5,
missing-pieces-of-system/angle-comprehension-hierarchy/01-plan.md).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from vinu_agent.tools.trade_plan_tool import TradePlanTool


def _tool_with_store(row) -> TradePlanTool:
    tool = TradePlanTool()
    store = MagicMock()
    store.get_summary.return_value = row
    tool._ticker_summary_store = store
    return tool


def _row(**overrides):
    defaults = dict(
        summary="AAPL looks constructive.",
        source_run_id="run-1",
        angles_with_data=12,
        angle_count=28,
        angle_digest={"patchtst": {"direction": "up"}},
        cluster_digest={"B": "4 of 5 models lean up"},
        cross_cluster={"redundant_clusters": ["G"]},
        cluster_anomalies={"E": ["SYSTEM OVERRIDE flagged"]},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestReadSummaryContext:
    def test_carries_cluster_digest_and_cross_cluster_through(self) -> None:
        tool = _tool_with_store(_row())
        ctx = tool._read_summary_context("AAPL")
        assert ctx["cluster_digest"] == {"B": "4 of 5 models lean up"}
        assert ctx["cross_cluster"] == {"redundant_clusters": ["G"]}
        assert ctx["cluster_anomalies"] == {"E": ["SYSTEM OVERRIDE flagged"]}
        # angle_digest must still be present too -- not replaced.
        assert ctx["angle_digest"] == {"patchtst": {"direction": "up"}}

    def test_missing_cluster_digest_attr_defaults_to_empty(self) -> None:
        row = _row()
        del row.cluster_digest
        del row.cross_cluster
        del row.cluster_anomalies
        tool = _tool_with_store(row)
        ctx = tool._read_summary_context("AAPL")
        assert ctx["cluster_digest"] == {}
        assert ctx["cross_cluster"] == {}
        assert ctx["cluster_anomalies"] == {}
        assert ctx["cluster_titles"] == {}

    def test_sends_cluster_titles_from_book_index_for_present_clusters_only(self) -> None:
        """vinu-research can't import vinu-agent's book_index, so titles
        travel with the data (missing-pieces-of-system/
        gatekeeper-initial-analysis/)."""
        tool = _tool_with_store(_row(cluster_digest={"A": "x", "B": "y"}))
        ctx = tool._read_summary_context("AAPL")
        assert ctx["cluster_titles"] == {
            "A": "Classical statistical forecasts",
            "B": "Deep-learning / foundation-model forecasts",
        }

    def test_no_store_configured_returns_none(self) -> None:
        tool = TradePlanTool()
        tool._ticker_summary_store = None
        assert tool._read_summary_context("AAPL") is None

    def test_no_row_returns_none(self) -> None:
        tool = _tool_with_store(None)
        assert tool._read_summary_context("AAPL") is None

    def test_empty_summary_returns_none_even_with_cluster_digest_present(self) -> None:
        tool = _tool_with_store(_row(summary=""))
        assert tool._read_summary_context("AAPL") is None
