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

    def test_steady_unrealized_pnl_does_not_inflate_across_repeated_calls(self) -> None:
        """situation-test/31-risk-budget-accumulates-repeated-unrealized-pnl-snapshots.md:
        the tracker used to be fed the raw unrealized_pl on every call via
        record_daily_pnl() (a += accumulator meant for discrete REALIZED
        events), so a position sitting at a steady, healthy -$500 all day
        would drift into TIER_HALT purely from being polled enough times
        (every order check, every dashboard refresh) -- completely
        independent of any real change in the position. The tracker now
        lives on the service instance specifically so a real change is
        remembered across calls (that part of the original Stage 2 fix was
        right); repeated IDENTICAL snapshots must report the identical
        result."""
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
            return_value=[{"symbol": "AAPL", "unrealized_pl": -500.0}]
        )
        results = [asyncio.run(svc.compute_risk_status()) for _ in range(5)]
        daily_pnls = [r["symbols"][0]["daily_pnl"] for r in results]
        assert daily_pnls == [-500.0] * 5
        assert all(r["symbols"][0]["tier"] == 0 for r in results)

    def test_a_breach_latches_for_the_rest_of_the_day_even_after_recovery(self) -> None:
        """The intended "accumulates across a real trading day" behavior,
        implemented correctly: the WORST unrealized reading seen for a
        symbol today is what should be sticky, not a nonsensical sum of
        repeated reads -- a position that touched TIER_HALT and later
        recovered should stay flagged, matching how a real circuit breaker
        behaves (it doesn't silently clear the instant the price ticks
        back)."""
        svc = TestComputeRiskStatus._service()
        svc.compute_daily_game_plan = AsyncMock(
            return_value={
                "status": "ok",
                "readiness_score": 1.0,
                "account_equity": 100_000.0,
                "regime": {"regime": "bull"},
            }
        )

        def _fetch_with(pnl: float):
            return AsyncMock(return_value=[{"symbol": "AAPL", "unrealized_pl": pnl}])

        svc._fetch_positions = _fetch_with(-100.0)
        asyncio.run(svc.compute_risk_status())
        svc._fetch_positions = _fetch_with(-3500.0)  # breaches TIER_HALT
        breach = asyncio.run(svc.compute_risk_status())
        svc._fetch_positions = _fetch_with(-50.0)  # recovers to nearly flat
        recovered = asyncio.run(svc.compute_risk_status())

        assert breach["symbols"][0]["halted"] is True
        assert recovered["symbols"][0]["halted"] is True
        assert recovered["symbols"][0]["daily_pnl"] == -3500.0
