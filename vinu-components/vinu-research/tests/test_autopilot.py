from __future__ import annotations

import json
import tempfile
from pathlib import Path

from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis
from vinu_research.tools import (
    generate_backtest_config,
    link_autopilot_backtest,
    run_autopilot,
    scaffold_signal_engine,
)


def _make_registry_with_hypothesis() -> tuple[HypothesisRegistry, Hypothesis]:
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "hypotheses.json"
    reg = HypothesisRegistry(path)
    h = Hypothesis.create(
        "Momentum Decay",
        "Momentum signals decay in low-volatility regimes",
        universe=["AAPL", "MSFT"],
    )
    h.signal_definition = "rank(momentum_20d) * zscore(volume_ratio)"
    reg.create(h)
    return reg, h


class TestRunAutopilot:
    def test_creates_goal_from_hypothesis(self):
        reg, h = _make_registry_with_hypothesis()
        result = run_autopilot(h.hypothesis_id, reg)
        assert result["hypothesis_id"] == h.hypothesis_id
        assert result["goal_id"].startswith("goal_")
        assert "Momentum Decay" in result["objective"]
        assert result["universe"] == ["AAPL", "MSFT"]

    def test_raises_for_missing_hypothesis(self):
        import pytest
        with pytest.raises(ValueError, match="not found"):
            run_autopilot("hyp_nonexistent")


class TestGenerateBacktestConfig:
    def test_writes_config_json(self):
        reg, h = _make_registry_with_hypothesis()
        tmp = tempfile.mkdtemp()
        config_path = generate_backtest_config(
            h.hypothesis_id, "2024-01-01", "2024-12-31", reg, output_dir=tmp,
        )
        path = Path(config_path)
        assert path.exists()
        config = json.loads(path.read_text(encoding="utf-8"))
        assert config["hypothesis_id"] == h.hypothesis_id
        assert config["start_date"] == "2024-01-01"
        assert config["end_date"] == "2024-12-31"
        assert config["universe"] == ["AAPL", "MSFT"]
        assert "generated_at" in config

    def test_raises_for_missing_hypothesis(self):
        import pytest
        with pytest.raises(ValueError, match="not found"):
            generate_backtest_config("hyp_nonexistent", "2024-01-01", "2024-12-31")


class TestScaffoldSignalEngine:
    def test_writes_signal_engine_stub(self):
        reg, h = _make_registry_with_hypothesis()
        tmp = tempfile.mkdtemp()
        sig_path = scaffold_signal_engine(h.hypothesis_id, reg, output_dir=tmp)
        path = Path(sig_path)
        assert path.exists()
        code = path.read_text(encoding="utf-8")
        assert "SignalEngine" in code
        assert "compute_signals" in code
        assert "Momentum Decay" in code
        assert "rank(momentum_20d)" in code

    def test_raises_for_missing_hypothesis(self):
        import pytest
        with pytest.raises(ValueError, match="not found"):
            scaffold_signal_engine("hyp_nonexistent")


class TestLinkAutopilotBacktest:
    def test_links_run_card_to_hypothesis(self):
        reg, h = _make_registry_with_hypothesis()
        tmp = tempfile.mkdtemp()
        run_card = {
            "schema_version": "0.1",
            "metrics": {"sharpe": 1.23, "total_return": 0.15, "max_drawdown": -0.08},
            "run_dir": tmp,
        }
        run_card_path = Path(tmp) / "run_card.json"
        run_card_path.write_text(json.dumps(run_card), encoding="utf-8")

        result = link_autopilot_backtest(h.hypothesis_id, tmp, reg)
        assert result["run_card_found"] is True
        assert result["metrics"]["sharpe"] == 1.23

        updated = reg.get(h.hypothesis_id)
        assert updated is not None
        assert str(run_card_path) in updated.run_cards
        assert updated.status.value == "testing"

    def test_no_run_card_returns_gracefully(self):
        reg, h = _make_registry_with_hypothesis()
        tmp = tempfile.mkdtemp()
        result = link_autopilot_backtest(h.hypothesis_id, tmp, reg)
        assert result["run_card_found"] is False

    def test_raises_for_missing_hypothesis(self):
        import pytest
        with pytest.raises(ValueError, match="not found"):
            link_autopilot_backtest("hyp_nonexistent", "/tmp")
