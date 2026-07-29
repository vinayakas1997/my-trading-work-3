from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class PositionSizer(ABC):
    """
    Scales a strategy's raw target weights by a single exposure factor based on
    realized performance observed strictly *before* the current rebalance day —
    never the current or future day's return, so this can never introduce
    look-ahead bias on top of whatever the strategy's own signal already does.

    Direction (long/short) always comes from the strategy; a sizer only ever
    scales magnitude, it never flips or invents a position the signal didn't call
    for.
    """

    @abstractmethod
    def size(self, target_weights: np.ndarray, realized_returns: np.ndarray) -> np.ndarray:
        ...


class FixedSizer(PositionSizer):
    """No adjustment — today's default behavior. The strategy's own weights are
    used exactly as given, with no risk-based scaling."""

    def size(self, target_weights: np.ndarray, realized_returns: np.ndarray) -> np.ndarray:
        return target_weights


class VolTargetSizer(PositionSizer):
    """
    Scales exposure inversely to trailing realized volatility so the strategy
    carries roughly constant risk instead of constant capital. When realized vol
    spikes, position size shrinks automatically; when it's calm, size grows (up to
    `max_leverage`).
    """

    def __init__(
        self,
        target_annual_vol: float = 0.15,
        lookback_days: int = 20,
        max_leverage: float = 1.0,
        periods_per_year: int = 252,
    ):
        self.target_annual_vol = target_annual_vol
        self.lookback_days = lookback_days
        self.max_leverage = max_leverage
        self.periods_per_year = periods_per_year

    def size(self, target_weights: np.ndarray, realized_returns: np.ndarray) -> np.ndarray:
        if len(realized_returns) < self.lookback_days:
            # Not enough history yet to estimate vol — don't guess, leave sizing
            # unadjusted rather than scaling on a noisy tiny sample.
            return target_weights

        window = realized_returns[-self.lookback_days:]
        realized_vol = float(np.std(window, ddof=1)) * np.sqrt(self.periods_per_year)

        if realized_vol <= 1e-9:
            scale = self.max_leverage
        else:
            scale = min(self.target_annual_vol / realized_vol, self.max_leverage)
        scale = max(scale, 0.0)

        return target_weights * scale


class FractionalKellySizer(PositionSizer):
    """
    Sizes exposure from a trailing win-rate / payoff-ratio estimate, scaled down by
    `kelly_fraction` (default 0.25 — "quarter Kelly") since full Kelly is provably
    optimal only under perfect knowledge of the true edge, which a trailing sample
    estimate never is; full Kelly on a noisy estimate risks ruinous drawdowns.
    """

    def __init__(
        self,
        kelly_fraction: float = 0.25,
        lookback_days: int = 60,
        max_leverage: float = 1.0,
    ):
        self.kelly_fraction = kelly_fraction
        self.lookback_days = lookback_days
        self.max_leverage = max_leverage

    def size(self, target_weights: np.ndarray, realized_returns: np.ndarray) -> np.ndarray:
        if len(realized_returns) < self.lookback_days:
            return target_weights

        window = realized_returns[-self.lookback_days:]
        wins = window[window > 0]
        losses = window[window < 0]

        if len(wins) == 0 or len(losses) == 0:
            # Can't estimate a payoff ratio from an all-win or all-loss sample —
            # leave sizing unadjusted rather than extrapolate from a degenerate case.
            return target_weights

        win_rate = len(wins) / len(window)
        avg_win = float(wins.mean())
        avg_loss = float(np.abs(losses.mean()))
        if avg_loss <= 1e-12:
            return target_weights
        payoff_ratio = avg_win / avg_loss

        # Kelly criterion for a binary win/loss bet: f* = p - (1-p)/b, where p is
        # win probability and b is the payoff ratio (win size / loss size).
        kelly_estimate = win_rate - (1 - win_rate) / payoff_ratio
        kelly_estimate = max(kelly_estimate, 0.0)  # never flip direction via sizing

        scale = min(kelly_estimate * self.kelly_fraction, self.max_leverage)
        return target_weights * scale


def build_position_sizer(
    model: str,
    target_annual_vol: float = 0.15,
    vol_lookback_days: int = 20,
    kelly_fraction: float = 0.25,
    kelly_lookback_days: int = 60,
    max_leverage: float = 1.0,
) -> PositionSizer:
    if model == "vol_target":
        return VolTargetSizer(
            target_annual_vol=target_annual_vol,
            lookback_days=vol_lookback_days,
            max_leverage=max_leverage,
        )
    if model == "kelly":
        return FractionalKellySizer(
            kelly_fraction=kelly_fraction,
            lookback_days=kelly_lookback_days,
            max_leverage=max_leverage,
        )
    if model == "fixed":
        return FixedSizer()
    raise ValueError(f"Unknown position_sizing_model: {model}")
