from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from vinu_portfolio.config import PortfolioConfig
from vinu_portfolio.risk_budget import (
    DailyPositionTracker,
    compute_risk_budget,
    compute_symbol_tier,
    regime_sizing_multiplier,
    TIER_WARNING,
    TIER_REDUCE,
    TIER_HALT,
)
from vinu_portfolio.service import PortfolioService


class TestRegimeSizingMultiplier:
    def test_bull_is_normal(self) -> None:
        assert regime_sizing_multiplier("bull") == 1.0

    def test_bear_is_tightened(self) -> None:
        assert regime_sizing_multiplier("bear") == 0.8

    def test_sideways_slightly_tightened(self) -> None:
        assert regime_sizing_multiplier("sideways") == 0.9

    def test_high_vol_is_tightest(self) -> None:
        assert regime_sizing_multiplier("high_vol") == 0.6

    def test_unknown_regime_defaults_to_neutral(self) -> None:
        assert regime_sizing_multiplier(None) == 1.0
        assert regime_sizing_multiplier("unknown") == 1.0


class TestComputeSymbolTier:
    def test_no_loss_is_tier_0(self) -> None:
        assert compute_symbol_tier(100.0, 100_000.0) == 0

    def test_small_loss_is_tier_0(self) -> None:
        assert compute_symbol_tier(-500.0, 100_000.0) == 0

    def test_warning_threshold(self) -> None:
        assert compute_symbol_tier(-1500.0, 100_000.0) == TIER_WARNING

    def test_reduce_threshold(self) -> None:
        assert compute_symbol_tier(-2500.0, 100_000.0) == TIER_REDUCE

    def test_halt_threshold(self) -> None:
        assert compute_symbol_tier(-3500.0, 100_000.0) == TIER_HALT


class TestDailyPositionTracker:
    def test_tracks_accumulates_per_symbol(self) -> None:
        tracker = DailyPositionTracker()
        assert tracker.get_daily_pnl("AAPL") == 0.0
        tracker.record_daily_pnl("AAPL", 100.0)
        tracker.record_daily_pnl("AAPL", -50.0)
        assert tracker.get_daily_pnl("AAPL") == 50.0
        assert tracker.get_daily_pnl("MSFT") == 0.0

    def test_different_symbols_independent(self) -> None:
        tracker = DailyPositionTracker()
        tracker.record_daily_pnl("AAPL", 100.0)
        tracker.record_daily_pnl("MSFT", -200.0)
        assert tracker.get_daily_pnl("AAPL") == 100.0
        assert tracker.get_daily_pnl("MSFT") == -200.0


class TestComputeRiskBudget:
    def test_returns_no_equity_when_equity_none(self) -> None:
        budget = compute_risk_budget([], equity=None)
        assert budget.aggregate["status"] == "no_equity"

    def test_returns_no_equity_when_equity_zero(self) -> None:
        budget = compute_risk_budget([], equity=0.0)
        assert budget.aggregate["status"] == "no_equity"

    def test_empty_positions_returns_placeholder(self) -> None:
        budget = compute_risk_budget([], equity=100_000.0)
        assert budget.aggregate["n_positions"] == 1
        assert budget.symbols[0]["symbol"] == "*no_positions"

    def test_single_profitable_position(self) -> None:
        positions = [{"symbol": "AAPL", "unrealized_pl": 500.0}]
        budget = compute_risk_budget(positions, equity=100_000.0)
        assert len(budget.symbols) == 1
        assert budget.symbols[0]["symbol"] == "AAPL"
        assert budget.symbols[0]["tier"] == 0
        assert budget.aggregate["n_halted"] == 0

    def test_large_loss_triggers_halt(self) -> None:
        positions = [{"symbol": "AAPL", "unrealized_pl": -5000.0}]
        budget = compute_risk_budget(positions, equity=100_000.0)
        assert budget.symbols[0]["tier"] == TIER_HALT
        assert budget.symbols[0]["halted"] is True
        assert budget.symbols[0]["suggested_size_multiplier"] == 0.0
        assert budget.aggregate["n_halted"] == 1

    def test_regime_tightens_bands(self) -> None:
        positions = [{"symbol": "AAPL", "unrealized_pl": 100.0}]
        budget = compute_risk_budget(positions, equity=100_000.0, regime="high_vol")
        assert budget.symbols[0]["regime_band_multiplier"] == 0.6

    def test_reduce_tier_halves_size(self) -> None:
        positions = [{"symbol": "AAPL", "unrealized_pl": -2500.0}]
        budget = compute_risk_budget(positions, equity=100_000.0, regime="bull")
        assert budget.symbols[0]["tier"] == TIER_REDUCE
        assert budget.symbols[0]["suggested_size_multiplier"] == pytest.approx(0.5)

    def test_regime_shift_tightening_is_distinct_from_budget_breach(self) -> None:
        """Regime-shift tightening (no P&L breach) must apply on its own,
        distinct from a tier-driven budget breach with no regime change."""
        positions = [{"symbol": "AAPL", "unrealized_pl": 100.0}]  # profitable: tier 0

        neutral = compute_risk_budget(positions, equity=100_000.0, regime="bull")
        assert neutral.symbols[0]["tier"] == 0
        assert neutral.symbols[0]["suggested_size_multiplier"] == pytest.approx(1.0)

        tightened = compute_risk_budget(positions, equity=100_000.0, regime="high_vol")
        assert tightened.symbols[0]["tier"] == 0  # no budget breach
        assert tightened.symbols[0]["regime_band_multiplier"] == 0.6
        # Regime alone (no tier reduction) drives the suggested size down.
        assert tightened.symbols[0]["suggested_size_multiplier"] == pytest.approx(0.6)

    def test_regime_tightening_composes_multiplicatively_with_tier_reduce(self) -> None:
        """When both a budget breach (tier >= REDUCE) and a tightened regime
        apply together, the two multipliers compose rather than one masking
        the other."""
        positions = [{"symbol": "AAPL", "unrealized_pl": -2500.0}]  # tier REDUCE
        budget = compute_risk_budget(positions, equity=100_000.0, regime="high_vol")
        assert budget.symbols[0]["tier"] == TIER_REDUCE
        assert budget.symbols[0]["regime_band_multiplier"] == 0.6
        # band_mult(0.6) * tier-reduce factor(0.5) = 0.3
        assert budget.symbols[0]["suggested_size_multiplier"] == pytest.approx(0.3)

    def test_halt_tier_zeroes_size_regardless_of_regime(self) -> None:
        positions = [{"symbol": "AAPL", "unrealized_pl": -5000.0}]  # tier HALT
        budget = compute_risk_budget(positions, equity=100_000.0, regime="bull")
        assert budget.symbols[0]["tier"] == TIER_HALT
        assert budget.symbols[0]["suggested_size_multiplier"] == 0.0


class TestComputeRiskStatus:
    def _service(**overrides) -> PortfolioService:
        return PortfolioService(config=PortfolioConfig(**overrides))

    def test_calls_through_to_pipeline(self) -> None:
        svc = TestComputeRiskStatus._service()
        svc.compute_daily_game_plan = AsyncMock(
            return_value={
                "status": "ok",
                "readiness_score": 0.5,
                "account_equity": 100_000.0,
                "regime": {"regime": "bull"},
                "n_strategies": 1,
                "strategies": [],
                "weights": [],
                "portfolio": {},
                "date": "2026-07-31",
            }
        )
        svc._fetch_positions = AsyncMock(
            return_value=[{"symbol": "AAPL", "unrealized_pl": 100.0}]
        )
        result = asyncio.run(svc.compute_risk_status())
        assert result["equity"] == 100_000.0
        assert result["regime"] == "bull"
        assert result["aggregate"]["n_positions"] == 1
        assert result["game_plan_readiness"] == 0.5

    def test_daily_pnl_does_not_accumulate_across_repeated_calls(self) -> None:
        """Documents a known gap (see live-safety/SKILL.md's 'Daily risk
        budget' section): compute_risk_status() builds a fresh
        DailyPositionTracker on every call, so repeated polling never
        accumulates P&L the way DailyPositionTracker itself supports —
        each call just reflects that call's unrealized_pl snapshot."""
        svc = TestComputeRiskStatus._service()
        svc.compute_daily_game_plan = AsyncMock(
            return_value={
                "status": "ok",
                "readiness_score": 1.0,
                "account_equity": 100_000.0,
                "regime": {"regime": "bull"},
            }
        )
        svc._fetch_positions = AsyncMock(
            return_value=[{"symbol": "AAPL", "unrealized_pl": 500.0}]
        )
        first = asyncio.run(svc.compute_risk_status())
        second = asyncio.run(svc.compute_risk_status())
        # If daily_pnl accumulated across calls (as DailyPositionTracker
        # supports in isolation), the second call would show 1000.0, not 500.0.
        assert first["symbols"][0]["daily_pnl"] == 500.0
        assert second["symbols"][0]["daily_pnl"] == 500.0
