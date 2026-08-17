"""Tests for risk_gatekeeper's deterministic position sizing
(implementation-plan task 05, shortcoming #7). See
agent/position_sizing.py, tools/position_sizing_tool.py, and the
sizing_inputs wiring in agent/risk_gatekeeper_hook.py.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.agent.position_sizing import (
    atr_stop_size,
    compute_position_size,
    fixed_fractional_size,
    fractional_kelly_size,
    full_kelly_fraction,
)
from vinu_agent.tools.position_sizing_tool import ComputePositionSizeTool


class TestKellyFraction:
    def test_positive_edge_returns_positive_fraction(self) -> None:
        # p=0.6, b=1.5 -> (0.6*1.5 - 0.4)/1.5 = 0.5/1.5 = 0.3333
        f = full_kelly_fraction(0.6, 1.5)
        assert f == pytest.approx(0.3333, abs=1e-3)
        assert 0.0 < f < 1.0

    def test_breakeven_returns_zero(self) -> None:
        # p*b == q -> 0
        assert full_kelly_fraction(0.4, 1.5) == pytest.approx(0.0, abs=1e-9)

    def test_no_win_rate_returns_zero(self) -> None:
        assert full_kelly_fraction(0.0, 2.0) == 0.0
        assert full_kelly_fraction(-0.1, 2.0) == 0.0

    def test_certainty_returns_zero(self) -> None:
        assert full_kelly_fraction(1.0, 2.0) == 0.0
        assert full_kelly_fraction(1.5, 2.0) == 0.0

    def test_nonpositive_payoff_returns_zero(self) -> None:
        assert full_kelly_fraction(0.6, 0.0) == 0.0
        assert full_kelly_fraction(0.6, -1.0) == 0.0

    def test_never_negative_for_negative_edge(self) -> None:
        f = full_kelly_fraction(0.3, 1.5)
        assert f == 0.0  # (0.3*1.5 - 0.7)/1.5 < 0, clamped to 0


class TestFractionalKellySize:
    def test_quarter_kelly_of_equity(self) -> None:
        # full kelly 0.3333, quarter -> equity * 0.3333 * 0.25
        size = fractional_kelly_size(100000.0, 0.6, 1.5, kelly_fraction=0.25)
        assert size == pytest.approx(100000.0 * 0.3333 * 0.25, abs=1.0)

    def test_no_edge_never_positive(self) -> None:
        assert fractional_kelly_size(100000.0, 0.0, 2.0) == 0.0
        assert fractional_kelly_size(100000.0, 0.5, 0.0) == 0.0
        assert fractional_kelly_size(100000.0, 0.3, 1.5) == 0.0

    def test_nonpositive_equity_is_zero(self) -> None:
        assert fractional_kelly_size(0.0, 0.6, 1.5) == 0.0
        assert fractional_kelly_size(-1000.0, 0.6, 1.5) == 0.0


class TestFixedFractionalSize:
    def test_two_percent_rule(self) -> None:
        assert fixed_fractional_size(100000.0, risk_pct=0.02) == pytest.approx(2000.0)

    def test_zero_or_negative_risk_pct_is_zero(self) -> None:
        assert fixed_fractional_size(100000.0, risk_pct=0.0) == 0.0
        assert fixed_fractional_size(100000.0, risk_pct=-0.02) == 0.0


class TestAtrStopSize:
    def test_units_times_price(self) -> None:
        # risk budget 2000, per-unit risk 2*atr=4 -> 500 units * 10 = 5000
        size = atr_stop_size(100000.0, entry_price=10.0, atr=2.0, risk_pct=0.02)
        assert size == pytest.approx(5000.0)

    def test_missing_price_or_atr_falls_back_to_fixed_fractional(self) -> None:
        assert atr_stop_size(100000.0, entry_price=0.0, atr=2.0) == pytest.approx(2000.0)
        assert atr_stop_size(100000.0, entry_price=10.0, atr=0.0) == pytest.approx(2000.0)


class TestComputePositionSize:
    def test_records_inputs_for_traceability(self) -> None:
        result = compute_position_size(
            account_equity=100000.0, method="fractional_kelly",
            win_rate=0.6, payoff_ratio=1.5, kelly_fraction=0.25,
        )
        assert result["status"] == "ok"
        assert result["size"] > 0
        assert result["method"] == "fractional_kelly"
        assert result["inputs"]["win_rate"] == 0.6
        assert result["inputs"]["payoff_ratio"] == 1.5
        assert result["inputs"]["account_equity"] == 100000.0

    def test_zero_edge_returns_zero_size(self) -> None:
        result = compute_position_size(
            account_equity=100000.0, method="fractional_kelly", win_rate=0.3, payoff_ratio=1.5,
        )
        assert result["status"] == "ok"
        assert result["size"] == 0.0
        assert result["kelly_pct"] == 0.0

    def test_fixed_fractional_comparison_case(self) -> None:
        kelly = compute_position_size(
            account_equity=100000.0, method="fractional_kelly",
            win_rate=0.6, payoff_ratio=1.5, kelly_fraction=0.25,
        )["size"]
        fixed = compute_position_size(
            account_equity=100000.0, method="fixed_fractional", risk_pct=0.02,
        )["size"]
        assert fixed == pytest.approx(2000.0)
        # A strong edge at quarter Kelly can exceed the 2% rule; that is
        # expected, the concentration cap still bounds it downstream.
        assert kelly >= fixed

    def test_nonpositive_equity_is_zero(self) -> None:
        result = compute_position_size(account_equity=0.0, method="fractional_kelly")
        assert result["status"] == "ok"
        assert result["size"] == 0.0

    def test_unknown_method_is_error(self) -> None:
        result = compute_position_size(account_equity=100000.0, method="martingale")
        assert result["status"] == "error"

    def test_atr_stop_reports_actual_method_used(self) -> None:
        with_atr = compute_position_size(
            account_equity=100000.0, method="atr_stop",
            entry_price=10.0, atr=2.0, risk_pct=0.02,
        )
        assert with_atr["method"] == "atr_stop"
        without_atr = compute_position_size(
            account_equity=100000.0, method="atr_stop", entry_price=10.0, atr=0.0,
        )
        assert without_atr["method"] == "fixed_fractional"


class TestComputePositionSizeTool:
    def test_returns_json_with_size_and_inputs(self) -> None:
        tool = ComputePositionSizeTool()
        out = json.loads(tool.execute(
            account_equity=100000.0, win_rate=0.6, payoff_ratio=1.5,
        ))
        assert out["status"] == "ok"
        assert out["size"] > 0
        assert "inputs" in out

    def test_config_injection_sets_fraction(self) -> None:
        config = MagicMock()
        config.position_sizing_method = "fractional_kelly"
        config.kelly_fraction = 0.5
        config.risk_per_trade_pct = 0.01
        config.atr_stop_multiple = 2.0
        tool = ComputePositionSizeTool()
        tool._config = config
        out = json.loads(tool.execute(account_equity=100000.0, win_rate=0.6, payoff_ratio=1.5))
        full_kelly = (0.6 * 1.5 - 0.4) / 1.5
        assert out["size"] == pytest.approx(100000.0 * full_kelly * 0.5, abs=1.0)


def _pend_content(artifact_id: str, approved_size: float, sizing_inputs: dict) -> str:
    body = {
        "verdict": "APPROVED", "artifact_id": artifact_id,
        "reason": "within limits", "approved_size": approved_size,
        "sizing_inputs": sizing_inputs,
    }
    return f"Verdict: APPROVED.\n\n```json\n{json.dumps(body)}\n```\n"


class TestRiskGatekeeperHookSizing:
    """The verdict path recomputes the formula size deterministically from
    the recorded sizing_inputs and stores min(formula, headroom cap)."""

    def _stores(self):
        store_path = Path(tempfile.mktemp(suffix=".db"))
        ledger_path = Path(tempfile.mktemp(suffix=".db"))
        from vinu_agent.storage.ticker_ledger import TickerLedgerStore
        from vinu_research.storage.strategy_store import SqliteStrategyStore

        store = SqliteStrategyStore(store_path)
        ledger = TickerLedgerStore(ledger_path)
        artifact = self._pendable_artifact(store)
        return store, ledger, artifact, store_path, ledger_path

    def _pendable_artifact(self, store):
        from vinu_research.models import Artifact, ArtifactStatus

        artifact = Artifact.create("strategy", "AAPL-test", universe=["AAPL"])
        artifact.status = ArtifactStatus.BENCHING
        store.upsert_artifact(artifact)
        return artifact

    def _hook(self):
        from vinu_agent.agent.risk_gatekeeper_hook import apply_risk_gatekeeper_verdict

        return apply_risk_gatekeeper_verdict

    def test_approved_size_capped_at_formula_when_inputs_recorded(self) -> None:
        from vinu_research.models import ArtifactStatus

        store, ledger, artifact, store_path, ledger_path = self._stores()
        try:
            # formula for (0.6, 1.5, quarter kelly) x 100k = ~8333
            headroom_cap = 50000.0
            content = _pend_content(artifact.artifact_id, headroom_cap, {
                "account_equity": 100000.0, "win_rate": 0.6, "payoff_ratio": 1.5,
                "method": "fractional_kelly", "kelly_fraction": 0.25,
            })
            self._hook()(content, strategy_store=store, ticker_ledger_store=ledger)
            stored = store.get_artifact(artifact.artifact_id)
            assert stored.status == ArtifactStatus.PEND
            assert 0.0 < stored.approved_size < headroom_cap
            events = ledger.get_events("AAPL")
            assert "sizing_inputs" in events[0].text
        finally:
            store.close()
            ledger.close()
            store_path.unlink(missing_ok=True)
            ledger_path.unlink(missing_ok=True)

    def test_no_sizing_inputs_keeps_manager_size_unchanged(self) -> None:
        """Backward compatibility: verdicts without sizing_inputs (pre-
        task-05) pass the manager's approved_size through untouched."""
        from vinu_research.models import ArtifactStatus

        store, ledger, artifact, store_path, ledger_path = self._stores()
        try:
            content = (
                f"Verdict: APPROVED.\n\n```json\n"
                f'{{"verdict": "APPROVED", "artifact_id": "{artifact.artifact_id}", '
                f'"reason": "within limits", "approved_size": 15000.0}}\n```\n'
            )
            self._hook()(content, strategy_store=store, ticker_ledger_store=ledger)
            stored = store.get_artifact(artifact.artifact_id)
            assert stored.status == ArtifactStatus.PEND
            assert stored.approved_size == 15000.0
        finally:
            store.close()
            ledger.close()
            store_path.unlink(missing_ok=True)
            ledger_path.unlink(missing_ok=True)

    def test_zero_edge_never_gets_positive_size(self) -> None:
        from vinu_research.models import ArtifactStatus

        store, ledger, artifact, store_path, ledger_path = self._stores()
        try:
            content = _pend_content(artifact.artifact_id, 50000.0, {
                "account_equity": 100000.0, "win_rate": 0.3, "payoff_ratio": 1.5,
                "method": "fractional_kelly",
            })
            self._hook()(content, strategy_store=store, ticker_ledger_store=ledger)
            stored = store.get_artifact(artifact.artifact_id)
            assert stored.status == ArtifactStatus.PEND
            assert stored.approved_size == 0.0
        finally:
            store.close()
            ledger.close()
            store_path.unlink(missing_ok=True)
            ledger_path.unlink(missing_ok=True)