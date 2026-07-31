from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest

from vinu_portfolio.config import PortfolioConfig
from vinu_portfolio.service import PortfolioService


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


class TestEndToEndPipeline:
    """Full pipeline: build_portfolio -> compute_daily_allocation -> compute_daily_game_plan -> compute_risk_status."""

    def test_full_pipeline_runs(self, tmp_path) -> None:
        tags_file = tmp_path / "tags.yaml"
        tags_file.write_text(
            "strategies:\n  strat_a:\n    regime: [trending]\n",
            encoding="utf-8",
        )
        svc = PortfolioService(config=PortfolioConfig(
            tags_path=tags_file,
            regime_tilt_bound=0.3,
            outcome_tilt_bound=0.0,
        ))

        dates = pd.date_range("2026-06-01", periods=60)
        rng = np.random.default_rng(42)
        returns_df = pd.DataFrame(
            {
                "strat_a": rng.normal(0, 0.02, 60),
                "strat_b": rng.normal(0, 0.03, 60),
            },
            index=dates,
        )

        svc.list_active_strategies = AsyncMock(return_value=[
            {"name": "strat_a", "kind": "yaml"},
            {"name": "strat_b", "kind": "yaml"},
        ])
        svc._build_returns_df = AsyncMock(return_value=returns_df)

        # --- build_portfolio ---
        portfolio = asyncio.run(svc.build_portfolio())
        assert portfolio["status"] == "ok"
        assert portfolio["n_strategies"] == 2
        assert len(portfolio["weights"]) == 2
        assert portfolio["shock_correlation"] is not None
        assert "calm_correlation" in portfolio["shock_correlation"]

        # --- compute_daily_allocation ---
        svc._fetch_benchmark_regime = AsyncMock(
            return_value={"status": "ok", "regime": "bull"}
        )
        svc._fetch_outcome_confidence = AsyncMock(
            return_value={"source": "not_tracked", "accuracy": None, "n_entries": 0}
        )
        svc._fetch_account_equity = AsyncMock(return_value=100_000.0)

        allocation = asyncio.run(svc.compute_daily_allocation())
        assert allocation["status"] == "ok"
        assert allocation["regime"]["regime"] == "bull"
        assert allocation["account_equity"] == 100_000.0
        weights = {w["name"]: w["target_weight"] for w in allocation["weights"]}
        total = sum(weights.values())
        assert total == pytest.approx(1.0, abs=0.02)

        # --- compute_daily_game_plan ---
        game_plan = asyncio.run(svc.compute_daily_game_plan())
        # No llm_python strategies means no trade plans, but regime and equity
        # are both live here: 2 of 4 data points (2 symbols + regime + equity).
        assert game_plan["readiness_score"] == 0.5
        assert game_plan["readiness_flags"]["n_with_plan"] == 0
        assert game_plan["readiness_flags"]["regime_available"] is True
        assert game_plan["readiness_flags"]["equity_available"] is True
        assert game_plan["n_symbols"] == 2
        assert len(game_plan["symbols"]) == 2
        assert game_plan["portfolio"]["status"] == "ok"

        # --- compute_risk_status ---
        svc._fetch_positions = AsyncMock(return_value=[
            {"symbol": "AAPL", "unrealized_pl": 500.0},
            {"symbol": "MSFT", "unrealized_pl": -200.0},
        ])
        risk = asyncio.run(svc.compute_risk_status())
        assert risk["equity"] == 100_000.0
        assert risk["aggregate"]["n_positions"] == 2
        assert risk["aggregate"]["n_halted"] == 0
        # most profitable symbol first
        assert risk["symbols"][0]["symbol"] == "AAPL"
        assert risk["symbols"][1]["daily_pnl"] == pytest.approx(-200.0, abs=1.0)
