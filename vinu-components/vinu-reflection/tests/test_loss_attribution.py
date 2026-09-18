"""Tests for analysis C (loss-cause / slippage attribution)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra.trade_audit_log import record_entry, record_exit

from vinu_reflection.reflection import loss_attribution


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _log_path(data_root: Path) -> Path:
    return data_root / "vinu_live" / "trade_audit_log.jsonl"


def _record_trade(
    data_root: Path,
    *,
    trade_id: str,
    tier: str,
    realized_pnl: float,
    loss_cause: str = "",
    slippage_bps: float = 2.0,
) -> None:
    log_path = _log_path(data_root)
    record_entry(
        trade_id, "AAPL",
        {"trade_score_tier": tier, "slippage_bps": slippage_bps},
        log_path=log_path,
    )
    record_exit(
        trade_id, "AAPL",
        {"realized_pnl": realized_pnl, "loss_cause": loss_cause},
        log_path=log_path,
    )


class TestLossAttributionRun:
    def test_no_data_returns_no_findings(self, data_root):
        assert loss_attribution.run({"vinu_live": data_root / "vinu_live"}) == []

    def test_below_window_minimum_is_skipped(self, data_root):
        for i in range(40):
            _record_trade(data_root, trade_id=f"t{i}", tier="strong", realized_pnl=10.0)
        findings = loss_attribution.run({"vinu_live": data_root / "vinu_live"})
        assert findings == []

    def test_rising_loss_rate_is_flagged(self, data_root):
        # 90 reference trades, all wins.
        for i in range(90):
            _record_trade(data_root, trade_id=f"ref-{i}", tier="strong", realized_pnl=10.0)
        # 30 recent trades, all losses (execution_error).
        for i in range(30):
            _record_trade(
                data_root, trade_id=f"cur-{i}", tier="strong",
                realized_pnl=-5.0, loss_cause="execution_error",
            )

        findings = loss_attribution.run({"vinu_live": data_root / "vinu_live"})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "system"
        assert finding.scope_key == "strong"
        assert finding.metric_name == "loss_rate"
        assert finding.primary_metric == pytest.approx(1.0)  # 100% vs 0% loss rate
        assert finding.psi > 0.25
        assert finding.evidence_count == 120
        assert finding.signal_json["dominant_loss_cause"] == "execution_error"

    def test_trades_without_a_matching_entry_are_excluded(self, data_root):
        log_path = _log_path(data_root)
        for i in range(40):
            # exit with no preceding entry -- e.g. log rotated/truncated.
            record_exit(f"orphan-{i}", "AAPL", {"realized_pnl": -1.0}, log_path=log_path)
        findings = loss_attribution.run({"vinu_live": data_root / "vinu_live"})
        assert findings == []

    def test_tiers_evaluated_independently(self, data_root):
        for i in range(90):
            _record_trade(data_root, trade_id=f"strong-ref-{i}", tier="strong", realized_pnl=10.0)
        for i in range(30):
            _record_trade(data_root, trade_id=f"strong-cur-{i}", tier="strong", realized_pnl=10.0)
        # "watch" tier never reaches the 120-trade minimum.
        for i in range(10):
            _record_trade(data_root, trade_id=f"watch-{i}", tier="watch", realized_pnl=-1.0)

        findings = loss_attribution.run({"vinu_live": data_root / "vinu_live"})
        assert {f.scope_key for f in findings} == {"strong"}
        assert findings[0].psi < 0.1  # stable -- both windows all-wins
