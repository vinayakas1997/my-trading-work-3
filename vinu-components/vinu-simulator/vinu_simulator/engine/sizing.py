from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd

from vinu_infra.evidence_confidence import summarize_resolved_triggers
from vinu_infra.risk_math import forecast_confidence_scale
from vinu_infra.risk_math import kelly_fraction as _kelly_fraction
from vinu_portfolio.circuit_breakers import compute_drawdown_action
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
        current_date: pd.Timestamp | None = None,
        evidence_triggers: dict[str, list[dict[str, Any]]] | None = None,
        regime: str | None = None,
        portfolio_value: float | None = None,
    ) -> np.ndarray:
        """`symbol_returns`, when given, is the backtest's own per-symbol
        daily-return history strictly before the current rebalance day
        (same point-in-time-safe cutoff as `realized_returns`) -- only
        `CompositeSizer` reads it today, for its correlation factor, and
        `EvidenceConfidenceSizer`, for per-symbol identity (its column
        order). `current_date`/`evidence_triggers` exist only for
        `EvidenceConfidenceSizer`. `regime` exists only for
        `RegimeAwareSizer` -- the current bar's regime label
        (`engine.regime.classify_regime`'s own point-in-time-safe
        output), precomputed once outside the loop. `portfolio_value`
        exists only for `DrawdownAwareSizer` -- this step's NAV before
        today's rebalance, so it can track its own running peak/start the
        same way `PortfolioDrawdownMonitor` does live. Every other sizer
        here accepts and ignores all five so the engine's one call site
        can pass them unconditionally without an isinstance check."""
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
        current_date: pd.Timestamp | None = None,
        evidence_triggers: dict[str, list[dict[str, Any]]] | None = None,
        regime: str | None = None,
        portfolio_value: float | None = None,
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
        current_date: pd.Timestamp | None = None,
        evidence_triggers: dict[str, list[dict[str, Any]]] | None = None,
        regime: str | None = None,
        portfolio_value: float | None = None,
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
        current_date: pd.Timestamp | None = None,
        evidence_triggers: dict[str, list[dict[str, Any]]] | None = None,
        regime: str | None = None,
        portfolio_value: float | None = None,
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
        current_date: pd.Timestamp | None = None,
        evidence_triggers: dict[str, list[dict[str, Any]]] | None = None,
        regime: str | None = None,
        portfolio_value: float | None = None,
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


def _as_of_iso(current_date: pd.Timestamp) -> str:
    ts = pd.Timestamp(current_date)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.isoformat()


class EvidenceConfidenceSizer(PositionSizer):
    """Scales each symbol's weight by Track 2's evidence-confidence for
    that symbol (system-wide-audit-and-design item #4/#10) -- unlike
    every other sizer in this file, this one scales per-symbol, not by a
    single portfolio-wide scalar, since evidence-confidence is inherently
    a per-symbol question (a strategy can have strong historical evidence
    on one name and none at all on another).

    Deliberately makes no network calls of its own: `evidence_triggers`
    (symbol -> pre-fetched, already-resolved trigger list, filtered to
    the strategy's `evidence_must_condition` by the caller) comes in
    through `size()` exactly the way `symbol_returns` already does for
    `CompositeSizer` -- this engine's whole discipline is "act only on
    data already handed to it," and threading in a live HTTP client here
    would be the first sizer in this file to break that.

    A symbol with no evidence on file, or fewer resolved triggers than
    `min_sample_size`, is left unscaled (factor 1.0) -- "no evidence yet"
    is not evidence the edge is bad, so it must never look like a
    conviction-driven size-down.

    Reuses `vinu_infra.risk_math.forecast_confidence_scale` unchanged for
    the actual scale factor, which only ever dampens (its ceiling is
    1.0) -- a high evidence-confidence keeps a symbol at its full
    strategy-assigned weight, it never grants leverage beyond that weight
    just because the evidence looks good. Only weak evidence
    (`evidence_confidence` well below 1.0) pulls a symbol's size down,
    toward `min_confidence_scale` as a floor, never to zero.
    """

    def __init__(self, min_confidence_scale: float = 0.5, min_sample_size: int = 5):
        self.min_confidence_scale = min_confidence_scale
        self.min_sample_size = min_sample_size

    def size(
        self,
        target_weights: np.ndarray,
        realized_returns: np.ndarray,
        *,
        symbol_returns: pd.DataFrame | None = None,
        current_date: pd.Timestamp | None = None,
        evidence_triggers: dict[str, list[dict[str, Any]]] | None = None,
        regime: str | None = None,
        portfolio_value: float | None = None,
    ) -> np.ndarray:
        if symbol_returns is None or current_date is None or not evidence_triggers:
            # No symbol identity, no point-in-time cutoff, or nothing to
            # look up -- fail open to unscaled, same posture as every
            # other sizer's "not enough context yet" branch.
            return target_weights

        as_of_iso = _as_of_iso(current_date)
        scale = np.ones(len(target_weights), dtype=np.float64)
        for i, ticker in enumerate(symbol_returns.columns):
            triggers = evidence_triggers.get(ticker)
            if not triggers:
                continue
            summary = summarize_resolved_triggers(triggers, as_of_iso=as_of_iso)
            if summary["sample_size"] < self.min_sample_size:
                continue
            scale[i] = forecast_confidence_scale(
                summary["evidence_confidence"], floor=self.min_confidence_scale,
            )
        return target_weights * scale


# item #14A factor #2 (system-wide-audit-and-design/
# 02-open-questions-strategy-and-simulation.md): "a strategy that only
# works in low-vol regimes should shrink automatically as the regime
# shifts, not rely on the strategy author hard-coding that themselves."
# `engine.regime.classify_regime`'s labels, not reinvented here.
DEFAULT_REGIME_SCALE_MAP: dict[str, float] = {
    "high_vol": 0.5,
    "bear": 0.7,
    "bull": 1.0,
    "sideways": 1.0,
}


class RegimeAwareSizer(PositionSizer):
    """Scales the whole portfolio's weight by a single factor looked up
    from the current bar's regime label -- a portfolio-wide scalar, like
    `VolTargetSizer`/`CompositeSizer`, not per-symbol like
    `EvidenceConfidenceSizer`, since regime (bull/bear/high_vol/sideways)
    is a benchmark-level classification, not a per-symbol one.

    Makes no classification decisions of its own: `regime` is
    `engine.regime.classify_regime()`'s own point-in-time-safe label,
    computed once by the engine before the loop starts and passed in per
    step -- this sizer is a pure lookup table
    (`regime_scale_map.get(regime, default_scale)`), not a second,
    independently-derived regime rule.

    A bar with no regime available (no benchmark ticker in the price
    data, or the classifier hasn't warmed up yet) is left unscaled
    (factor 1.0) -- "unknown regime" must never be silently treated as
    the worst-case regime.
    """

    def __init__(
        self,
        regime_scale_map: dict[str, float] | None = None,
        default_scale: float = 1.0,
    ):
        self.regime_scale_map = regime_scale_map or dict(DEFAULT_REGIME_SCALE_MAP)
        self.default_scale = default_scale

    def size(
        self,
        target_weights: np.ndarray,
        realized_returns: np.ndarray,
        *,
        symbol_returns: pd.DataFrame | None = None,
        current_date: pd.Timestamp | None = None,
        evidence_triggers: dict[str, list[dict[str, Any]]] | None = None,
        regime: str | None = None,
        portfolio_value: float | None = None,
    ) -> np.ndarray:
        if regime is None:
            return target_weights
        scale = self.regime_scale_map.get(regime, self.default_scale)
        return target_weights * scale


# item #14A factor #3: ok -> 1.0 (full size), halve -> 0.5, flat/halt ->
# 0.0 (no new exposure) -- the exact mapping discussed and confirmed
# directly (2026-09-28), matching the live system's own stated intent
# literally rather than inventing a softer gradient.
DEFAULT_DRAWDOWN_ACTION_SCALE: dict[str, float] = {
    "ok": 1.0,
    "halve": 0.5,
    "flat": 0.0,
    "halt": 0.0,
}


class DrawdownAwareSizer(PositionSizer):
    """Scales the whole portfolio by a factor looked up from
    `vinu_portfolio.circuit_breakers.compute_drawdown_action` -- the same
    pure ok/halve/flat/halt threshold ladder `PortfolioDrawdownMonitor`
    uses live, extracted specifically so this sizer can reuse it without
    also reusing `update()`'s real HTTP halt call (which would risk
    halting real live trading from a backtest replaying synthetic data --
    the actual reason this wasn't already a drop-in, per item #14A's own
    finding).

    Tracks its own peak/start portfolio value across the backtest
    calendar, on this instance -- a fresh sizer is built per run (same as
    every other stateful sizer here), so there is no cross-run leakage,
    the same guarantee `PortfolioDrawdownMonitor.reset()` gives a live
    monitor between sessions.

    Once `halt` fires, per the confirmed design, it is NOT sticky --
    `compute_drawdown_action` is re-evaluated fresh every step from the
    tracked peak/start, so a recovery above the halt threshold on a later
    day returns to `ok` (or whichever rung the ladder currently sits at),
    exactly like every other bar-by-bar sizer in this file.
    """

    def __init__(
        self,
        drawdown_threshold: float = -0.20,
        halve_threshold: float = -0.10,
        flat_threshold: float = -0.15,
        abs_loss_threshold: float = 0.0,
        action_scale_map: dict[str, float] | None = None,
    ):
        self.drawdown_threshold = drawdown_threshold
        self.halve_threshold = halve_threshold
        self.flat_threshold = flat_threshold
        self.abs_loss_threshold = abs_loss_threshold
        self.action_scale_map = action_scale_map or dict(DEFAULT_DRAWDOWN_ACTION_SCALE)
        self._peak_value: float | None = None
        self._start_value: float | None = None

    def size(
        self,
        target_weights: np.ndarray,
        realized_returns: np.ndarray,
        *,
        symbol_returns: pd.DataFrame | None = None,
        current_date: pd.Timestamp | None = None,
        evidence_triggers: dict[str, list[dict[str, Any]]] | None = None,
        regime: str | None = None,
        portfolio_value: float | None = None,
    ) -> np.ndarray:
        if portfolio_value is None:
            # No NAV to track yet -- fail open, same posture as every
            # other "not enough context" branch in this file.
            return target_weights
        result = compute_drawdown_action(
            portfolio_value,
            peak_value=self._peak_value, start_value=self._start_value,
            threshold=self.drawdown_threshold, halve_threshold=self.halve_threshold,
            flat_threshold=self.flat_threshold, abs_loss_threshold=self.abs_loss_threshold,
        )
        self._peak_value = result["new_peak_value"]
        self._start_value = result["new_start_value"]
        scale = self.action_scale_map.get(result["action"], 1.0)
        return target_weights * scale


def build_position_sizer(
    model: str,
    target_annual_vol: float = 0.15,
    vol_lookback_days: int = 20,
    kelly_fraction: float = 0.25,
    kelly_lookback_days: int = 60,
    max_leverage: float = 1.0,
    evidence_min_confidence_scale: float = 0.5,
    evidence_min_sample_size: int = 5,
    regime_scale_map: dict[str, float] | None = None,
    regime_default_scale: float = 1.0,
    drawdown_threshold: float = -0.20,
    drawdown_halve_threshold: float = -0.10,
    drawdown_flat_threshold: float = -0.15,
    drawdown_abs_loss_threshold: float = 0.0,
    drawdown_action_scale_map: dict[str, float] | None = None,
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
    if model == "evidence_confidence":
        return EvidenceConfidenceSizer(
            min_confidence_scale=evidence_min_confidence_scale,
            min_sample_size=evidence_min_sample_size,
        )
    if model == "regime_aware":
        return RegimeAwareSizer(
            regime_scale_map=regime_scale_map,
            default_scale=regime_default_scale,
        )
    if model == "drawdown_aware":
        return DrawdownAwareSizer(
            drawdown_threshold=drawdown_threshold,
            halve_threshold=drawdown_halve_threshold,
            flat_threshold=drawdown_flat_threshold,
            abs_loss_threshold=drawdown_abs_loss_threshold,
            action_scale_map=drawdown_action_scale_map,
        )
    if model == "fixed":
        return FixedSizer()
    raise ValueError(f"Unknown position_sizing_model: {model}")
