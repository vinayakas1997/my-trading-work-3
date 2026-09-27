from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from vinu_infra.risk_math import kelly_fraction as _kelly_fraction
from vinu_tools.compute.risk.shock_correlation import dcc_shock_correlation


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
    def size(
        self,
        target_weights: np.ndarray,
        realized_returns: np.ndarray,
        *,
        symbol_returns: pd.DataFrame | None = None,
    ) -> np.ndarray:
        """`symbol_returns`, when given, is the backtest's own per-symbol
        daily-return history strictly before the current rebalance day
        (same point-in-time-safe cutoff as `realized_returns`) -- only
        `CompositeSizer` reads it today; every other sizer here accepts
        and ignores it so the engine's one call site can pass it
        unconditionally without an isinstance check."""
        ...


class FixedSizer(PositionSizer):
    """No adjustment — today's default behavior. The strategy's own weights are
    used exactly as given, with no risk-based scaling."""

    def size(
        self,
        target_weights: np.ndarray,
        realized_returns: np.ndarray,
        *,
        symbol_returns: pd.DataFrame | None = None,
    ) -> np.ndarray:
        return target_weights


def _vol_target_scale_factor(
    realized_returns: np.ndarray,
    target_annual_vol: float,
    lookback_days: int,
    max_leverage: float,
    periods_per_year: int,
) -> float:
    """Extracted from `VolTargetSizer.size()` unchanged (byte-identical
    formula) so `CompositeSizer` can reuse the exact same vol-target math
    rather than a second, independently-derived copy."""
    if len(realized_returns) < lookback_days:
        # Not enough history yet to estimate vol — don't guess, leave sizing
        # unadjusted rather than scaling on a noisy tiny sample.
        return 1.0

    window = realized_returns[-lookback_days:]
    realized_vol = float(np.std(window, ddof=1)) * np.sqrt(periods_per_year)

    if realized_vol <= 1e-9:
        scale = max_leverage
    else:
        scale = min(target_annual_vol / realized_vol, max_leverage)
    return max(scale, 0.0)


class VolTargetSizer(PositionSizer):
    """
    Scales exposure inversely to trailing realized volatility so the strategy
    carries roughly constant risk instead of constant capital. When realized vol
    spikes, position size shrinks automatically; when it's calm, size grows (up to
    `max_leverage`).

    Deliberately NOT delegated to vinu_infra.risk_math.vol_target_scale despite
    the similar name and intent -- that shared helper treats current_vol as
    *daily* and target_vol as *annual* (converting the latter before
    comparing) and never scales past 1.0 by design ("a calm market does not
    license extra leverage"). This sizer instead takes both vols already
    annualized and explicitly DOES scale above 1.0 in calm markets, up to
    `max_leverage` -- a real, tested, intentional behavior difference
    (see test_low_realized_vol_scales_up_toward_max_leverage), not
    accidental duplication. Unifying the two would either change live
    backtest sizing or silently drop the leverage-up feature.
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

    def size(
        self,
        target_weights: np.ndarray,
        realized_returns: np.ndarray,
        *,
        symbol_returns: pd.DataFrame | None = None,
    ) -> np.ndarray:
        scale = _vol_target_scale_factor(
            realized_returns, self.target_annual_vol, self.lookback_days,
            self.max_leverage, self.periods_per_year,
        )
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

    def size(
        self,
        target_weights: np.ndarray,
        realized_returns: np.ndarray,
        *,
        symbol_returns: pd.DataFrame | None = None,
    ) -> np.ndarray:
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

        # f* = p - (1-p)/b (p = win_rate, b = avg_win/avg_loss) -- delegated
        # to vinu_infra.risk_math.kelly_fraction, the single source of truth
        # for this exact formula (also used by vinu-tools' identical
        # kelly_optimal_fraction) rather than reimplementing it a third time.
        kelly_estimate = _kelly_fraction(win_rate, avg_win, avg_loss, fraction_of_kelly=1.0)

        scale = min(kelly_estimate * self.kelly_fraction, self.max_leverage)
        return target_weights * scale


class CompositeSizer(PositionSizer):
    """Multiplies vol-target sizing with correlation-aware shrinkage into
    one scale factor -- the senior-quant "composite risk sizing"
    follow-up (system-wide-audit-and-design item #14): two positions
    that are secretly the same underlying bet no longer both get full
    size just because each one's own vol-target factor looks fine in
    isolation. Still only ever scales the strategy's own weight vector
    by one scalar, same discipline as every sizer in this file --
    direction/which-symbols always comes from the strategy.

    Correlation-awareness reuses `vinu_tools.compute.risk.shock_correlation
    .dcc_shock_correlation` unchanged (relocated from `vinu-portfolio` for
    exactly this reuse) rather than a second, independently-derived
    correlation model.
    """

    # Refitting a GARCH model per symbol on every single rebalance day
    # would make backtests using this sizer prohibitively slow for no
    # real benefit -- correlation structure does not meaningfully change
    # day to day. Recomputed only every N new rows of return history,
    # cached in between. A reasonable default, same posture as every
    # other guessed-until-real-data-exists constant in this codebase.
    _DEFAULT_CORRELATION_LOOKBACK_DAYS = 60
    _DEFAULT_CORRELATION_RECOMPUTE_EVERY = 20
    _DEFAULT_HIGH_CORRELATION_THRESHOLD = 0.7
    _DEFAULT_MAX_CORRELATION_SHRINK = 0.5

    def __init__(
        self,
        target_annual_vol: float = 0.15,
        vol_lookback_days: int = 20,
        max_leverage: float = 1.0,
        periods_per_year: int = 252,
        correlation_lookback_days: int = _DEFAULT_CORRELATION_LOOKBACK_DAYS,
        correlation_recompute_every: int = _DEFAULT_CORRELATION_RECOMPUTE_EVERY,
        max_correlation_shrink: float = _DEFAULT_MAX_CORRELATION_SHRINK,
    ):
        self.target_annual_vol = target_annual_vol
        self.vol_lookback_days = vol_lookback_days
        self.max_leverage = max_leverage
        self.periods_per_year = periods_per_year
        self.correlation_lookback_days = correlation_lookback_days
        self.correlation_recompute_every = correlation_recompute_every
        self.max_correlation_shrink = max_correlation_shrink
        self._cached_corr_scale = 1.0
        self._cached_at_n_rows = -1

    def size(
        self,
        target_weights: np.ndarray,
        realized_returns: np.ndarray,
        *,
        symbol_returns: pd.DataFrame | None = None,
    ) -> np.ndarray:
        vol_scale = _vol_target_scale_factor(
            realized_returns, self.target_annual_vol, self.vol_lookback_days,
            self.max_leverage, self.periods_per_year,
        )
        corr_scale = self._correlation_scale(symbol_returns)
        return target_weights * vol_scale * corr_scale

    def _correlation_scale(self, symbol_returns: pd.DataFrame | None) -> float:
        if symbol_returns is None or symbol_returns.shape[1] < 2:
            return 1.0
        n_rows = len(symbol_returns)
        if n_rows < self.correlation_lookback_days:
            return 1.0
        if (
            self._cached_at_n_rows >= 0
            and n_rows - self._cached_at_n_rows < self.correlation_recompute_every
        ):
            return self._cached_corr_scale

        window = symbol_returns.iloc[-self.correlation_lookback_days:]
        result = dcc_shock_correlation(window)
        if result["status"] != "ok":
            # Fails open to no shrinkage, same posture every other
            # best-effort diagnostic in this codebase uses -- an
            # unavailable correlation read is not evidence positions are
            # safe, but silently blocking sizing on it would turn a
            # diagnostic gap into a bigger outage.
            scale = 1.0
        else:
            n_assets = result["n_assets"]
            max_pairs = n_assets * (n_assets - 1) / 2
            high_pair_fraction = (
                result["n_high_correlation_pairs"] / max_pairs if max_pairs > 0 else 0.0
            )
            scale = 1.0 - min(self.max_correlation_shrink, high_pair_fraction * self.max_correlation_shrink)

        self._cached_corr_scale = scale
        self._cached_at_n_rows = n_rows
        return scale


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
    if model == "composite":
        return CompositeSizer(
            target_annual_vol=target_annual_vol,
            vol_lookback_days=vol_lookback_days,
            max_leverage=max_leverage,
        )
    if model == "fixed":
        return FixedSizer()
    raise ValueError(f"Unknown position_sizing_model: {model}")
