"""Phase 4 orchestration: forecast + risk state + personality context -> frozen TradePlan.

This is the only place the LLM forecast (vinu_research.forecast_skill) is combined with
Phase 1's deterministic risk math (vinu_tools.compute.risk) and Phase 2's personality/
shock-clustering angles (vinu-initial-analysis, read via ResearchTools) into a single,
machine-evaluable TradePlan. Consumers (e.g. vinu-agent's TradePlanTool) only ever read the
frozen artifact produced here over HTTP (see server/routes_trade_plan.py) -- they never call
the LLM themselves, keeping Rule 10 ("no LLM outside vinu-research") intact.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np

from vinu_tools.compute.risk import (
    expected_move_from_vol,
    garch_volatility,
    historical_cvar,
    historical_var,
    kelly_optimal_fraction,
)

from vinu_research.calibration import CalibrationGate, CalibrationTracker
from vinu_research.config import ResearchConfig, TradeScoreThresholds
from vinu_research.forecast_skill import ForecastSkillConfig, generate_forecast
from vinu_research.gates.trade_score_gate import (
    TIER_SIZE_MULTIPLIER,
    check_trade_score_gate,
    tier_meets_minimum,
)
from vinu_research.market_regime_analogue import get_market_regime_stats_for_today
from vinu_research.market_state import MarketState
from vinu_research import maturity_assessor
from vinu_research.models import (
    AngleCalibrationEntry,
    Artifact,
    ArtifactStatus,
    CalibrationEntry,
    ContingencyRule,
    EntryDecision,
    Forecast,
    InvalidationCondition,
    RiskBand,
    SignalEntry,
    TradeAction,
    TradePlan,
    TradeScoreResult,
)
from vinu_research.storage.strategy_store import SqliteStrategyStore
from vinu_research.tools import ResearchTools
from vinu_research.trade_score_calibration import load_active_thresholds, record_trade_score_outcome

logger = logging.getLogger(__name__)

_DEFAULT_LOOKBACK_DAYS = 252
_MIN_OBSERVATIONS = 20


class TradePlanApprovalError(Exception):
    """Raised when a frozen trade plan fails its approval gate or is already frozen."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons) or "trade plan approval rejected")


async def fetch_risk_state(
    tools: ResearchTools,
    symbol: str,
    lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Phase 1 risk state for `symbol`: conditional vol, VaR/CVaR, expected move, Kelly fraction.

    Reuses `ResearchTools.get_benchmark_data`, which already fetches candles from
    vinu-stock-price and reduces them to a daily-returns series.
    """
    to_date = datetime.now(timezone.utc).date()
    from_date = to_date - timedelta(days=lookback_days)
    returns_series = await tools.get_benchmark_data(symbol, str(from_date), str(to_date))
    if returns_series is None or len(returns_series) < _MIN_OBSERVATIONS:
        return {"status": "insufficient_data"}

    returns = returns_series.values.astype(float)

    vol_path, alpha, beta, omega = garch_volatility(returns, fit=True, time_format="1D")
    valid_vol = vol_path[~np.isnan(vol_path)]
    annualized_volatility = (
        float(valid_vol[-1]) if len(valid_vol) > 0 else float(np.std(returns, ddof=1) * np.sqrt(252))
    )
    daily_volatility = annualized_volatility / np.sqrt(252)

    var_95 = historical_var(returns, confidence_level=0.95)
    cvar_95 = historical_cvar(returns, confidence_level=0.95)
    expected_move_1d_pct = expected_move_from_vol(daily_volatility, confidence=0.68)

    wins = returns[returns > 0]
    losses = returns[returns < 0]
    win_rate = float(len(wins) / len(returns)) if len(returns) else 0.0
    avg_win = float(np.mean(wins)) if len(wins) else 0.0
    avg_loss = float(abs(np.mean(losses))) if len(losses) else 0.0
    kelly_fraction = kelly_optimal_fraction(win_rate, avg_win, avg_loss) if avg_loss > 0 else 0.0

    return {
        "status": "ok",
        "annualized_volatility": annualized_volatility,
        "daily_volatility": daily_volatility,
        "garch_alpha": float(alpha),
        "garch_beta": float(beta),
        "garch_persistence": float(alpha + beta),
        "var_95_daily": var_95,
        "cvar_95_daily": cvar_95,
        "expected_move_1d_pct": expected_move_1d_pct,
        "win_rate": win_rate,
        "kelly_fraction": kelly_fraction,
        "n_observations": int(len(returns)),
    }


async def fetch_options_context(tools: ResearchTools, symbol: str) -> dict[str, Any]:
    """High-expectations spec #7: live options-implied volatility context
    for `symbol`, via ResearchTools.get_options_snapshot (routed to
    vinu-agent's tools/options_tool.fetch_chain over HTTP -- see that
    method's docstring for why). Same fail-open shape as fetch_risk_state:
    `{"status": "unavailable"}` on any missing/empty/malformed data, never
    raises -- a missing options chain (illiquid or non-optionable symbol)
    just means compute_trade_score's options-aware adjustments are skipped,
    not that authoring breaks.

    Extracts exactly the 3 scalar fields actually consumed downstream:
    - atm_iv: implied vol of the contract(s) nearest the median strike in
      the nearest expiration (a proxy -- fetch_chain has no underlying
      price to find the true at-the-money strike from).
    - iv_skew: avg put IV minus avg call IV in that expiration (positive =
      puts pricier, the usual "crash risk premium" skew).
    - days_to_nearest_expiry.
    """
    snapshot = await tools.get_options_snapshot(symbol)
    if not snapshot or snapshot.get("status") != "ok":
        return {"status": "unavailable"}
    contracts = snapshot.get("contracts") or []
    rows = [
        c for c in contracts
        if c.get("expiration") and c.get("implied_volatility") is not None and c.get("strike") is not None
    ]
    if not rows:
        return {"status": "unavailable"}

    nearest_expiration = min(c["expiration"] for c in rows)
    same_expiry = [c for c in rows if c["expiration"] == nearest_expiration]

    strikes = sorted(float(c["strike"]) for c in same_expiry)
    median_strike = strikes[len(strikes) // 2]
    atm_contract = min(same_expiry, key=lambda c: abs(float(c["strike"]) - median_strike))
    atm_iv = float(atm_contract["implied_volatility"])

    call_ivs = [float(c["implied_volatility"]) for c in same_expiry if c.get("type") == "C"]
    put_ivs = [float(c["implied_volatility"]) for c in same_expiry if c.get("type") == "P"]
    iv_skew = (sum(put_ivs) / len(put_ivs) - sum(call_ivs) / len(call_ivs)) if call_ivs and put_ivs else 0.0

    try:
        days_to_nearest_expiry = (datetime.strptime(nearest_expiration, "%Y-%m-%d").date() - datetime.now(timezone.utc).date()).days
    except ValueError:
        days_to_nearest_expiry = None

    return {
        "status": "ok",
        "atm_iv": atm_iv,
        "iv_skew": iv_skew,
        "days_to_nearest_expiry": days_to_nearest_expiry,
        "nearest_expiration": nearest_expiration,
    }


async def fetch_personality_features(tools: ResearchTools, symbol: str) -> dict[str, Any]:
    """Phase 2 personality/shock-clustering context for `symbol` (latest row of each angle)."""
    personality_rows, cluster_rows = await asyncio.gather(
        tools.get_angle_rows("shock_personality", symbol),
        tools.get_angle_rows("shock_clustering", symbol),
    )
    return {
        "shock_personality": personality_rows[-1] if personality_rows else {},
        "shock_clustering": cluster_rows[-1] if cluster_rows else {},
    }


_REGIME_FAVORS_DIRECTION = {"bull": "long", "bear": "short"}


async def fetch_current_regime(tools: ResearchTools, symbol: str) -> str | None:
    """The regime_analysis angle's `current_regime` row's `regime` field
    (bull/bear/high_vol/sideways), or None when no such row exists. A
    second, cheap already-computed-row read alongside fetch_angle_signals'
    own regime_analysis fetch below -- not new computation, same posture
    this file already takes toward angle reads elsewhere. Raises on fetch
    failure (matches fetch_debate_signal's own pattern) -- caught at the
    call site in author_trade_plan, not here."""
    regime_rows = await tools.get_angle_rows("regime_analysis", symbol)
    current_regime_row = next((r for r in regime_rows if r.get("metric") == "current_regime"), None)
    return current_regime_row.get("regime") if current_regime_row else None


def _regime_size_multiplier(current_regime: str | None, direction: str, bound: float) -> float:
    """Position-size tilt from current regime vs. this trade's direction --
    mirrors vinu-portfolio/service.py's _regime_alignment_multiplier (same
    "bounded tilt, not a hard switch" shape, same default bound), giving
    regime a second, direct channel into sizing independent of its existing
    one-vote-among-many confluence signal (see the current_regime_alignment
    SignalEntry in fetch_angle_signals below, which is unchanged by this).

    bull+long or bear+short (trading with the regime) -> sized up.
    bull+short or bear+long (trading against it) -> sized down.
    high_vol -> always sized down regardless of direction -- unlike
    vinu-portfolio's YAML strategies, nothing else in this pipeline already
    self-suppresses for high volatility.
    sideways / unmapped / unknown regime -> neutral, no directional edge
    either way (matches vinu-portfolio's own high_vol-is-neutral reasoning,
    applied here to the regime that has no long/short bias instead).
    """
    if direction not in ("long", "short") or bound <= 0:
        return 1.0
    if current_regime == "high_vol":
        return 1.0 - bound
    favored = _REGIME_FAVORS_DIRECTION.get(current_regime or "")
    if favored is None:
        return 1.0
    return 1.0 + bound if direction == favored else 1.0 - bound


def _screener_rank_size_multiplier(percentile: float | None, bound: float) -> float:
    """Position-size tilt from a symbol's percentile rank in vinu-screener's
    latest run (1.0 = top of the ranked list, near 0.0 = bottom) -- same
    linear-map shape as vinu-portfolio's _outcome_confidence_multiplier
    (service.py:718-723): neutral at the midpoint (0.5), scaled toward
    1.0+bound at the top and 1.0-bound at the bottom. None (screener
    unreachable, symbol not in this run's top-N, or the tilt disabled via
    bound<=0) is neutral -- no signal either way, not a penalty."""
    if percentile is None or bound <= 0:
        return 1.0
    return 1.0 + bound * (2 * percentile - 1)


async def fetch_angle_signals(tools: ResearchTools, symbol: str, direction: str) -> list[SignalEntry]:
    """The signal ledger used to draw on only 2 of ~28 available angles
    (shock_personality/shock_clustering, via fetch_personality_features
    above) -- every other angle only reached the forecast as one collapsed
    free-text summary string, never as a structured SignalEntry feeding
    _confluence_score. This adds a small, deliberately-bounded set of
    additional angles using the same already-generic
    tools.get_angle_rows(angle_name, symbol) fetch_personality_features
    itself uses (and loop.py already uses for 4 more angles elsewhere) --
    reading already-computed stored rows, not new computation, so this is
    called unconditionally, not behind an opt-in flag.

    Each angle's absence or fetch failure produces zero signals from that
    angle and never blocks the others (asyncio.gather(..., return_exceptions
    =True)), matching the fail-open pattern already used for Phase 4/5's
    optional data sources elsewhere in this module. `direction` is the
    forecast's already-decided direction (this fetch happens after
    generate_forecast), used only to score regime alignment -- it can never
    change what direction was picked.
    """
    results = await asyncio.gather(
        tools.get_angle_rows("trend_lifecycle", symbol),
        tools.get_angle_rows("regime_analysis", symbol),
        tools.get_angle_rows("backtesting_44_metrics", symbol),
        return_exceptions=True,
    )
    trend_rows, regime_rows, backtest_rows = (
        r if not isinstance(r, BaseException) else [] for r in results
    )
    signals: list[SignalEntry] = []

    lifecycle_row = next((r for r in trend_rows if r.get("type") == "lifecycle"), None)
    if lifecycle_row:
        stage = lifecycle_row.get("stage")
        bullish_stage = stage == "uptrend"
        bearish_stage = stage == "downtrend"
        if (bullish_stage and direction == "long") or (bearish_stage and direction == "short"):
            signals.append(SignalEntry(
                signal="trend_lifecycle_stage", direction="supporting", strength=0.6,
                source="trend_lifecycle", detail=f"stage={stage}",
            ))
        elif (bearish_stage and direction == "long") or (bullish_stage and direction == "short"):
            signals.append(SignalEntry(
                signal="trend_lifecycle_stage", direction="contradicting", strength=0.6,
                source="trend_lifecycle", detail=f"stage={stage}",
            ))

    current_regime_row = next((r for r in regime_rows if r.get("metric") == "current_regime"), None)
    if current_regime_row:
        regime = current_regime_row.get("regime")
        bullish_regime = regime == "bull"
        bearish_regime = regime == "bear"
        if (bullish_regime and direction == "long") or (bearish_regime and direction == "short"):
            signals.append(SignalEntry(
                signal="current_regime_alignment", direction="supporting", strength=0.5,
                source="regime_analysis", detail=f"regime={regime}",
            ))
        elif (bearish_regime and direction == "long") or (bullish_regime and direction == "short"):
            signals.append(SignalEntry(
                signal="current_regime_alignment", direction="contradicting", strength=0.5,
                source="regime_analysis", detail=f"regime={regime}",
            ))

    backtest_row = backtest_rows[-1] if backtest_rows else None
    if backtest_row:
        win_rate = backtest_row.get("win_rate")
        if isinstance(win_rate, (int, float)):
            if win_rate > 0.55:
                signals.append(SignalEntry(
                    signal="backtested_win_rate", direction="supporting",
                    strength=min(float(win_rate), 1.0), source="backtesting_44_metrics",
                    detail=f"win_rate={win_rate:.2f}",
                ))
            elif win_rate < 0.45:
                signals.append(SignalEntry(
                    signal="backtested_win_rate", direction="contradicting",
                    strength=min(1.0 - float(win_rate), 1.0), source="backtesting_44_metrics",
                    detail=f"win_rate={win_rate:.2f}",
                ))
        profit_factor = backtest_row.get("profit_factor")
        if isinstance(profit_factor, (int, float)):
            if profit_factor > 1.5:
                signals.append(SignalEntry(
                    signal="backtested_profit_factor", direction="supporting", strength=0.5,
                    source="backtesting_44_metrics", detail=f"profit_factor={profit_factor:.2f}",
                ))
            elif profit_factor < 1.0:
                signals.append(SignalEntry(
                    signal="backtested_profit_factor", direction="contradicting", strength=0.5,
                    source="backtesting_44_metrics", detail=f"profit_factor={profit_factor:.2f}",
                ))

    return signals


_DEBATE_PRESET_NAME = "investment_committee"


# Conviction-tier keyword sets for the debate's free-text verdict, checked
# strongest-first. Same "don't over-engineer LLM-output parsing" posture as
# the rest of this module's free-text handling -- a simple keyword tier, not
# an LLM-based sentiment score. Reused by fetch_debate_signal (entry-time
# weighting) and the in-trade thesis re-check (orchestrator.py), so both
# consumers of a debate verdict agree on what "strong" means.
_STRONG_CONVICTION_PHRASES = ("strongly", "high conviction", "clear")
_WEAK_CONVICTION_PHRASES = ("leaning", "slightly", "modest", "low conviction")


def debate_conviction_strength(text_lower: str) -> float:
    """1.0 for strong conviction language, 0.4 for weak/hedged language,
    else 0.7 (a plain, unqualified "bullish"/"bearish"/"neutral" with no
    intensity marker either way)."""
    if any(p in text_lower for p in _STRONG_CONVICTION_PHRASES):
        return 1.0
    if any(p in text_lower for p in _WEAK_CONVICTION_PHRASES):
        return 0.4
    return 0.7


async def fetch_debate_signal(
    tools: ResearchTools, symbol: str, direction: str, weight: float = 1.0,
) -> SignalEntry | None:
    """The investment_committee swarm debate (vinu-agent's bull_advocate ->
    bear_advocate -> risk_officer, opt-in via VINU_AGENT_DEBATE_MODE=full)
    used to run and record its run_id purely for traceability -- nothing
    ever read its verdict back into a trade decision. This opportunistically
    checks for a recently COMPLETED debate for `symbol` and folds its
    outcome in as one more signal; it never blocks waiting for one, since
    the debate is asynchronous (a separate background thread in a different
    service) while authoring is a synchronous, later cycle.

    Parses the risk_officer task's free-text result for bullish/bearish/
    neutral (simple keyword match, same "don't over-engineer LLM-output
    parsing" posture as the rest of this module's free-text handling) --
    falls back to the run's overall final_report if no risk_officer task is
    present. None (fail-open) when no completed run exists, the fetch
    fails, or the text matches none of the three keywords.

    `strength` used to be a flat 0.5 regardless of how strongly the text
    read, so a multi-agent committee synthesis counted the same as any
    single raw angle signal in _confluence_score's strength-sum
    (gates/trade_score_gate.py). Now derived from debate_conviction_strength
    and scaled by `weight` (config.debate_signal_weight) -- no change to
    _confluence_score itself, just a truthful per-signal strength.
    """
    run = await tools.get_latest_debate_run(_DEBATE_PRESET_NAME, symbol)
    if run is None:
        return None
    risk_officer_task = next(
        (t for t in run.get("tasks", []) if t.get("agent_name") == "risk_officer"), None,
    )
    text = (risk_officer_task["result"] if risk_officer_task else run.get("final_report", "")) or ""
    text_lower = text.lower()
    strength = debate_conviction_strength(text_lower) * weight
    if "bullish" in text_lower:
        bullish_verdict, bearish_verdict = True, False
    elif "bearish" in text_lower:
        bullish_verdict, bearish_verdict = False, True
    elif "neutral" in text_lower:
        return SignalEntry(
            signal="investment_committee_debate", direction="neutral", strength=strength,
            source=_DEBATE_PRESET_NAME, detail=text[:200],
        )
    else:
        return None

    # Cross-referenced against THIS plan's own direction, same as
    # fetch_angle_signals' regime-alignment signal above -- a "bearish"
    # verdict supports a short trade and contradicts a long one, never an
    # absolute label independent of what the trade actually is.
    if (bullish_verdict and direction == "long") or (bearish_verdict and direction == "short"):
        verdict_direction = "supporting"
    else:
        verdict_direction = "contradicting"
    return SignalEntry(
        signal="investment_committee_debate", direction=verdict_direction, strength=strength,
        source=_DEBATE_PRESET_NAME, detail=text[:200],
    )


def _build_risk_band(
    risk_state: dict[str, Any],
    personality: dict[str, Any],
    options_context: dict[str, Any] | None = None,
) -> RiskBand:
    if risk_state.get("status") != "ok":
        return RiskBand()

    vol = risk_state["annualized_volatility"]
    var_95 = abs(risk_state["var_95_daily"])
    kelly = risk_state["kelly_fraction"]
    # how-to-make-it-live.md #17: carry CVaR + daily vol onto the frozen plan so
    # the live entry path can gate/scale on them. Stored as positive fractions.
    cvar_95 = abs(float(risk_state.get("cvar_95_daily", 0.0) or 0.0))
    daily_vol = abs(float(risk_state.get("daily_volatility", 0.0) or 0.0))

    # Half-Kelly, capped at 10% of portfolio per position -- avoids full-Kelly's
    # well-known overbetting under estimation error.
    max_position_size_pct = min(max(kelly * 0.5, 0.0), 0.10)
    max_portfolio_risk_pct = min(var_95 * 2, 0.05)

    cluster_members = (personality.get("shock_clustering") or {}).get("cluster_members") or []
    max_cluster_exposure_pct = 0.15 if cluster_members else 0.25

    # High-expectations spec #6/#8: expected_drawdown, GARCH-based by
    # default. 1.5x is a documented heuristic (CVaR is a 1-day tail loss; a
    # drawdown typically compounds over several adverse days).
    expected_drawdown = cvar_95 * 1.5

    # High-expectations spec #7: when options-IV context is available
    # (config.options_iv_enabled), blend in the options-market-implied
    # near-term move as an independent volatility estimate alongside the
    # GARCH-based one -- simple average, a documented heuristic, not a
    # fitted blend weight.
    if options_context and options_context.get("status") == "ok":
        atm_iv = options_context.get("atm_iv")
        days = options_context.get("days_to_nearest_expiry")
        if isinstance(atm_iv, (int, float)) and isinstance(days, (int, float)) and days > 0:
            implied_move = float(atm_iv) * float(np.sqrt(days / 365.0))
            expected_drawdown = (expected_drawdown + implied_move) / 2.0

    return RiskBand(
        max_position_size_pct=max_position_size_pct,
        max_portfolio_risk_pct=max_portfolio_risk_pct,
        var_95_limit=var_95,
        max_leverage=1.0,
        max_cluster_exposure_pct=max_cluster_exposure_pct,
        volatility_band_upper=vol * 1.5,
        volatility_band_lower=vol * 0.5,
        cvar_95_limit=cvar_95,
        daily_vol=daily_vol,
        expected_drawdown=expected_drawdown,
    )


def _build_contingency_rules(
    risk_state: dict[str, Any],
    personality: dict[str, Any],
) -> list[ContingencyRule]:
    rules = [
        ContingencyRule(
            metric="drawdown_pct",
            operator=">=",
            threshold=0.05,
            action="reduce_position",
            action_params={"reduce_by_pct": 0.5},
        ),
    ]

    if risk_state.get("status") == "ok":
        # realized_vol_ratio = live realized vol / this plan's GARCH-forecast vol at
        # freeze time -- a live-vs-forecast divergence, not a re-derivation of GARCH.
        rules.append(
            ContingencyRule(
                metric="realized_vol_ratio",
                operator=">=",
                threshold=1.5,
                action="tighten_stop",
                action_params={"tighten_by_pct": 0.3},
            )
        )

    cluster_members = (personality.get("shock_clustering") or {}).get("cluster_members") or []
    if cluster_members:
        rules.append(
            ContingencyRule(
                metric="shock_cluster_correlation",
                operator=">=",
                threshold=0.7,
                action="reduce_position",
                action_params={"reduce_by_pct": 0.3},
            )
        )

    return rules


def _build_invalidation_conditions(
    risk_state: dict[str, Any],
    forecast: Forecast,
) -> list[InvalidationCondition]:
    conditions = [
        InvalidationCondition(
            metric="gap_against_position_pct",
            operator=">=",
            threshold=0.02,
            action="exit",
        ),
        InvalidationCondition(
            metric="unrealized_pnl_pct",
            operator="<=",
            threshold=-0.08,
            action="exit",
        ),
    ]

    if forecast.magnitude_std > 0:
        conditions.append(
            InvalidationCondition(
                metric="realized_move_vs_forecast_std",
                operator=">=",
                threshold=2.0,
                action="exit",
            )
        )

    if forecast.horizon_days > 0:
        conditions.extend([
            InvalidationCondition(
                metric="probability_of_failure",
                operator=">=",
                threshold=0.3,
                action="trim",
                action_params={"reduce_by_pct": 0.5},
                condition="P_failure >= 0.3",
            ),
            InvalidationCondition(
                metric="probability_of_failure",
                operator=">=",
                threshold=0.6,
                action="exit",
                action_params={"reason": "high_probability_failure"},
                condition="P_failure >= 0.6",
            ),
        ])

    return conditions


def _build_signal_ledger(
    risk_state: dict[str, Any],
    personality: dict[str, Any],
    forecast: Forecast,
) -> list[SignalEntry]:
    """High-expectations spec #4: a structured supporting/contradicting
    signal ledger alongside the free-text Forecast.reasoning, derived from
    the same risk_state/personality data _build_risk_band and
    _build_contingency_rules already read -- no new data sources."""
    signals: list[SignalEntry] = []

    if risk_state.get("status") == "ok":
        win_rate = float(risk_state.get("win_rate", 0.0) or 0.0)
        if win_rate > 0.55:
            signals.append(SignalEntry(
                signal="historical_win_rate", direction="supporting",
                strength=min(win_rate, 1.0), source="fetch_risk_state",
                detail=f"win_rate={win_rate:.2f}",
            ))
        elif win_rate < 0.45 and win_rate > 0:
            signals.append(SignalEntry(
                signal="historical_win_rate", direction="contradicting",
                strength=min(1.0 - win_rate, 1.0), source="fetch_risk_state",
                detail=f"win_rate={win_rate:.2f}",
            ))

        persistence = float(risk_state.get("garch_persistence", 0.0) or 0.0)
        if persistence > 0.9:
            signals.append(SignalEntry(
                signal="elevated_vol_persistence", direction="contradicting",
                strength=min(persistence, 1.0), source="fetch_risk_state",
                detail=f"garch_persistence={persistence:.2f}",
            ))

    cluster_members = (personality.get("shock_clustering") or {}).get("cluster_members") or []
    if cluster_members:
        signals.append(SignalEntry(
            signal="shock_cluster_correlation", direction="contradicting",
            strength=0.5, source="shock_clustering",
            detail=f"{len(cluster_members)} correlated symbol(s)",
        ))

    gap_fill_rate = (personality.get("shock_personality") or {}).get("gap_fill_rate")
    gap_fill_mean = gap_fill_rate.get("mean") if isinstance(gap_fill_rate, dict) else None
    if isinstance(gap_fill_mean, (int, float)):
        if gap_fill_mean >= 0.5:
            signals.append(SignalEntry(
                signal="gap_fill_rate", direction="supporting",
                strength=min(float(gap_fill_mean), 1.0), source="shock_personality",
                detail=f"gap_fill_rate={gap_fill_mean:.2f}",
            ))
        else:
            signals.append(SignalEntry(
                signal="gap_fill_rate", direction="contradicting",
                strength=min(1.0 - float(gap_fill_mean), 1.0), source="shock_personality",
                detail=f"gap_fill_rate={gap_fill_mean:.2f}",
            ))

    if forecast.confidence > 0:
        if forecast.confidence >= 0.5:
            signals.append(SignalEntry(
                signal="forecast_confidence", direction="supporting",
                strength=min(forecast.confidence, 1.0), source="forecast_skill",
                detail=f"confidence={forecast.confidence:.2f}",
            ))
        else:
            signals.append(SignalEntry(
                signal="forecast_confidence", direction="contradicting",
                strength=min(1.0 - forecast.confidence, 1.0), source="forecast_skill",
                detail=f"confidence={forecast.confidence:.2f}",
            ))

    return signals


def _build_entry_checklist(forecast: Forecast, risk_state: dict[str, Any]) -> list[dict[str, str]]:
    """Populates TradePlan.entry_checklist (declared in models.py, never
    filled in before this phase). Same dict shape vinu-agent's
    trade_plan_tool._build_structured_plan already uses for its own
    entry_rules ({"condition","status","source"}) so the two are mergeable
    -- see `extra_checklist_entries` on author_trade_plan below."""
    checklist = [
        {
            "condition": f"forecast_direction == '{forecast.direction}'",
            "status": "met" if forecast.direction in ("long", "short") else "pending",
            "source": "forecast_skill",
        },
        {
            "condition": "risk_state_available",
            "status": "met" if risk_state.get("status") == "ok" else "pending",
            "source": "fetch_risk_state",
        },
        {
            "condition": "forecast_confidence_above_0.5",
            "status": "met" if forecast.confidence >= 0.5 else "caution",
            "source": "forecast_skill",
        },
    ]
    return checklist


def _build_exit_checklist(invalidation_conditions: list[InvalidationCondition]) -> list[dict[str, str]]:
    """Populates TradePlan.exit_checklist from the same invalidation
    conditions already frozen onto the plan -- not a new rule source."""
    return [
        {"condition": c.condition, "action": c.action, "source": "invalidation_conditions"}
        for c in invalidation_conditions
    ]


def _derive_entry_decision(forecast: Forecast, trade_score: TradeScoreResult | None = None) -> str:
    """High-expectations spec #11: WAIT is a first-class decision, not just
    the absence of BUY/SELL. `trade_score` is optional so this works before
    Phase 3's gate exists; once wired, a watch/no_trade tier forces WAIT
    regardless of raw forecast confidence."""
    if trade_score is not None and trade_score.tier in ("watch", "no_trade"):
        return EntryDecision.WAIT.value
    if forecast.direction not in ("long", "short") or forecast.confidence < 0.5:
        return EntryDecision.WAIT.value
    return EntryDecision.SHORT.value if forecast.direction == "short" else EntryDecision.BUY.value


_SUMMARY_CONTEXT_MAX_CHARS = 2000
_ANGLE_DIGEST_MAX_ANGLES = 30


def _bound_angle_digest(angle_digest: Any) -> dict[str, Any]:
    """Defense-in-depth re-application of vinu_agent.tools.angles_tool's own
    bounds -- summary_context crosses a process/repo boundary (vinu-agent's
    stored digest -> vinu-research's forecast prompt), so this doesn't trust
    the caller already enforced them. No per-angle field cap (matches
    angles_tool.build_angle_digest): an early cap risks dropping an angle's
    actual signal fields behind whatever happened to come first in its row."""
    if not isinstance(angle_digest, dict):
        return {}
    bounded: dict[str, Any] = {}
    for name, fields in angle_digest.items():
        if len(bounded) >= _ANGLE_DIGEST_MAX_ANGLES:
            break
        if not isinstance(fields, dict):
            continue
        bounded[str(name)] = dict(fields)
    return bounded


def _normalize_summary_context(summary_context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate + truncate the Summary Agent context for the forecast prompt.

    Fail-open: missing/empty/error summaries return None (caller falls back
    to risk + shock rows only). Overlong summaries are truncated at a
    sentence boundary to bound prompt tokens.
    """
    if not isinstance(summary_context, dict):
        return None
    summary = str(summary_context.get("summary") or "").strip()
    if not summary or summary.lower().startswith("analysis unavailable"):
        return None
    if len(summary) > _SUMMARY_CONTEXT_MAX_CHARS:
        cut = summary[:_SUMMARY_CONTEXT_MAX_CHARS]
        # Prefer a sentence boundary so we don't hand the LLM a half-sentence.
        last_period = max(cut.rfind(". "), cut.rfind(".\n"))
        summary = cut[: last_period + 1] if last_period > 0 else cut
    return {
        "summary": summary,
        "source_run_id": str(summary_context.get("source_run_id") or ""),
        "angles_with_data": summary_context.get("angles_with_data", "?"),
        "angle_count": summary_context.get("angle_count", 28),
        "angle_digest": _bound_angle_digest(summary_context.get("angle_digest")),
    }


async def author_trade_plan(
    symbol: str,
    timeframe: str,
    config: ResearchConfig,
    tools: ResearchTools,
    llm_client: Any | None = None,
    summary_context: dict[str, Any] | None = None,
    extra_checklist_entries: dict[str, list[dict[str, str]]] | None = None,
    market_state: MarketState | None = None,
    trade_score_config: TradeScoreThresholds | None = None,
) -> TradePlan:
    """Author a complete TradePlan: forecast, sizing, risk bands, contingency + invalidation rules.

    Every contingency/invalidation rule is a metric/operator/threshold triple (see
    ContingencyRule/InvalidationCondition in models.py) so Phase 6 can evaluate it against
    live data without interpreting free text -- this is the completeness bar plan.md's
    "Warning for whoever implements Phase 4" requires.

    `summary_context` is the Summary Agent's stored read (summary +
    source_run_id + angles_with_data/angle_count), passed through from
    vinu-agent's TradePlanTool. Optional -- None preserves the previous
    risk + 2-shock-angles behavior exactly.

    `extra_checklist_entries` merges caller-computed checklist rows (e.g.
    vinu-agent's trade_plan_tool._build_structured_plan's own entry_rules/
    exit_rules) into the frozen plan's entry_checklist/exit_checklist at
    authoring time -- a single freeze, no re-freeze race. Shape:
    {"entry_rules": [...], "exit_rules": [...]}, same dict rows
    _build_structured_plan already produces.

    `market_state` feeds Phase 3's Trade Score gate's regime_fit_score (from
    market_state.market_regime_stats, Phase 4) and ev_score's cost estimate
    (from market_state.liquidity). None is fully supported -- those
    sub-scores just default to their fail-open values (see
    gates/trade_score_gate.py).
    """
    symbol = symbol.upper()
    summary_ctx = _normalize_summary_context(summary_context)
    logger.info("[%s %s] Authoring trade plan: fetching risk state + personality context", symbol, timeframe)
    fetches: list[Any] = [fetch_risk_state(tools, symbol), fetch_personality_features(tools, symbol)]
    if config.options_iv_enabled:
        fetches.append(fetch_options_context(tools, symbol))
    fetch_results = await asyncio.gather(*fetches, return_exceptions=True)
    risk_state = fetch_results[0] if not isinstance(fetch_results[0], BaseException) else {"status": "insufficient_data"}
    personality = fetch_results[1] if not isinstance(fetch_results[1], BaseException) else {}
    options_context: dict[str, Any] = {"status": "unavailable"}
    if config.options_iv_enabled:
        result = fetch_results[2]
        if isinstance(result, BaseException):
            logger.debug("[%s %s] Options context fetch failed: %s", symbol, timeframe, result)
        else:
            options_context = result
    logger.info("[%s %s] Risk state status=%s", symbol, timeframe, risk_state.get("status"))

    # High-expectations spec, step 3 of 00-maturity-agentic-system-
    # explanation.md: "wire MaturityAssessor's output into trade-plan
    # authoring's prompt first." Opt-in (off by default, see config.py),
    # local/cheap (no external API call), and fails open like every other
    # optional prompt-context addition in this function -- a
    # maturity-context failure must never break trade-plan authoring.
    maturity_context = None
    if config.maturity_tier_enabled:
        try:
            strategy_store = SqliteStrategyStore(config.data_root / "strategy_store.db")
            assessment = maturity_assessor.assess(
                strategy_store, config.agent_data_root,
                mature_min_trades=config.trade_score_calibration_min_sample,
            )
            maturity_context = assessment.as_prompt_dict()
        except Exception as e:
            logger.debug("[%s %s] MaturityAssessor fetch failed, continuing without it: %s", symbol, timeframe, e)

    forecast = await generate_forecast(
        symbol, personality, risk_state, config, llm_client,
        summary_context=summary_ctx, maturity_context=maturity_context,
    )
    logger.info(
        "[%s %s] Forecast: direction=%s magnitude_std=%.4f",
        symbol, timeframe, forecast.direction, forecast.magnitude_std,
    )

    risk_bands = _build_risk_band(risk_state, personality, options_context)
    contingency_rules = _build_contingency_rules(risk_state, personality)
    invalidation_conditions = _build_invalidation_conditions(risk_state, forecast)
    forecast.signals = _build_signal_ledger(risk_state, personality, forecast)
    try:
        forecast.signals = forecast.signals + await fetch_angle_signals(tools, symbol, forecast.direction)
    except Exception as e:
        logger.debug("[%s %s] fetch_angle_signals failed, continuing without it: %s", symbol, timeframe, e)
    if config.debate_signal_enabled:
        try:
            debate_signal = await fetch_debate_signal(
                tools, symbol, forecast.direction, weight=config.debate_signal_weight,
            )
            if debate_signal is not None:
                forecast.signals = forecast.signals + [debate_signal]
        except Exception as e:
            logger.debug("[%s %s] fetch_debate_signal failed, continuing without it: %s", symbol, timeframe, e)
    logger.info(
        "[%s %s] Trade plan authored: %d contingency rule(s), %d invalidation condition(s)",
        symbol, timeframe, len(contingency_rules), len(invalidation_conditions),
    )

    entry_checklist = _build_entry_checklist(forecast, risk_state)
    exit_checklist = _build_exit_checklist(invalidation_conditions)
    if extra_checklist_entries:
        entry_checklist = entry_checklist + list(extra_checklist_entries.get("entry_rules") or [])
        exit_checklist = exit_checklist + list(extra_checklist_entries.get("exit_rules") or [])

    # High-expectations spec #6/#7: Phase 4's whole-market regime analogue
    # and Phase 5's options-IV context, both opt-in (off by default -- see
    # config.py) and both merged into a copy of the caller's market_state
    # (or a fresh one), never mutating the caller's object in place.
    market_state_updates: dict[str, Any] = {}
    if config.regime_analogue_enabled:
        try:
            from vinu_research.storage.market_regime_history import MarketRegimeHistoryStore

            history_store = MarketRegimeHistoryStore(config.data_root / "market_regime_history.db")
            regime_stats = await get_market_regime_stats_for_today(
                tools, benchmark_symbol=config.regime_analogue_benchmark_symbol,
                history_store=history_store,
            )
        except Exception as e:
            logger.debug("[%s %s] Market regime analogue fetch failed: %s", symbol, timeframe, e)
            regime_stats = {}
        if regime_stats:
            market_state_updates["market_regime_stats"] = regime_stats
    if config.options_iv_enabled and options_context.get("status") == "ok":
        market_state_updates["options"] = options_context
    if market_state_updates:
        base_state = market_state or MarketState(symbol=symbol)
        market_state = MarketState(**{**base_state.to_dict(), **market_state_updates})

    # High-expectations spec #14: compute the Trade Score off the risk band
    # already built above (it needs risk_bands.expected_drawdown/
    # cvar_95_limit for its risk_score/ev_score, not the position size), then
    # scale max_position_size_pct by the tier multiplier -- hooks into the
    # single existing half-Kelly path instead of adding a second sizing
    # calculation. Authoring never blocks on a low tier (that's
    # approve_trade_plan's job, via check_trade_score_gate below); a
    # no_trade-tier plan still gets a frozen record, just at 0 size.
    #
    # Self-calibrating TradeScore weights (high-expectations follow-up): an
    # explicit caller-supplied trade_score_config (tests, other callers)
    # passes straight through unchanged -- only the default/unforced path
    # resolves through the calibration store, which itself returns the
    # plain TradeScoreThresholds() defaults until a calibration has
    # actually been approved/applied. Identical behavior to today until
    # that happens.
    if trade_score_config is None:
        trade_score_config = load_active_thresholds()
    trade_score_verdict = check_trade_score_gate(
        forecast, risk_bands, market_state, trade_score_config,
    )
    trade_score = trade_score_verdict.result
    size_multiplier = TIER_SIZE_MULTIPLIER.get(trade_score.tier, 0.0)
    # Regime router (high-expectations follow-up): a second, direct channel
    # for current_regime to affect this plan beyond its existing single
    # confluence-score vote -- see _regime_size_multiplier's own docstring.
    # Fail-open to a neutral 1.0 on any fetch problem, same posture as
    # every other optional data source in this function.
    try:
        current_regime = await fetch_current_regime(tools, symbol)
    except Exception as e:
        logger.debug("[%s %s] fetch_current_regime failed, continuing without it: %s", symbol, timeframe, e)
        current_regime = None
    regime_size_mult = _regime_size_multiplier(current_regime, forecast.direction, config.regime_size_tilt_bound)
    # Screener-rank sizing tilt (a second, independent optional channel --
    # see _screener_rank_size_multiplier's own docstring): ships inert,
    # the fetch is only ever attempted when an operator has explicitly
    # configured screener_ranker_id. Fail-open to a neutral 1.0 on any
    # fetch problem, same posture as the regime fetch immediately above.
    screener_percentile = None
    if config.screener_ranker_id:
        try:
            screener_percentile = await tools.fetch_screener_rank_percentile(config.screener_ranker_id, symbol)
        except Exception as e:
            logger.debug(
                "[%s %s] fetch_screener_rank_percentile failed, continuing without it: %s", symbol, timeframe, e,
            )
            screener_percentile = None
    screener_rank_mult = _screener_rank_size_multiplier(screener_percentile, config.screener_rank_size_tilt_bound)
    risk_bands.max_position_size_pct *= size_multiplier * regime_size_mult * screener_rank_mult
    trade_score.reasons.append(
        f"regime_size_multiplier={regime_size_mult:.2f} (regime={current_regime or 'unknown'})"
    )
    trade_score.reasons.append(
        f"screener_rank_size_multiplier={screener_rank_mult:.2f} "
        f"(percentile={screener_percentile if screener_percentile is not None else 'unranked'})"
    )

    entry_decision = _derive_entry_decision(forecast, trade_score)

    return TradePlan(
        symbol=symbol,
        timeframe=timeframe,
        direction=forecast.direction,
        position_size_pct=risk_bands.max_position_size_pct,
        risk_bands=risk_bands,
        contingency_rules=contingency_rules,
        invalidation_conditions=invalidation_conditions,
        forecast=forecast,
        entry_checklist=entry_checklist,
        exit_checklist=exit_checklist,
        entry_decision=entry_decision,
        trade_score=trade_score,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def freeze_trade_plan(
    store: SqliteStrategyStore,
    plan: TradePlan,
    summary_context: dict[str, Any] | None = None,
) -> Artifact:
    """Persist `plan` as a new CREATED Artifact(type="trade_plan"). Not yet tradeable."""
    # Stage A (A9 -- daily_stock_analysis's mandatory-invalidation-conditions
    # rule, see other-repos-world/comprison-other-vinu/04-daily_stock_analysis.md):
    # a trade plan with no way to be proven wrong is one vinu-live's
    # orchestrator will hold open indefinitely on the time-stop alone.
    # `_build_invalidation_conditions` currently always returns >= 2 (the
    # first two are unconditional), so this is a belt-and-suspenders guard
    # against a future refactor accidentally making every condition
    # conditional -- fail closed at freeze time, not silently later.
    if not plan.invalidation_conditions:
        raise ValueError(
            f"trade plan for {plan.symbol} has no invalidation conditions -- "
            "refusing to freeze a plan that can never be invalidated"
        )
    artifact = Artifact.create(
        type_="trade_plan",
        name=f"trade_plan_{plan.symbol}_{plan.timeframe}",
        universe=[plan.symbol],
    )
    if isinstance(summary_context, dict):
        normalized = _normalize_summary_context(summary_context)
        if normalized is not None:
            awd = normalized.get("angles_with_data", "?")
            ac = normalized.get("angle_count", 28)
            artifact.origin_angles = [f"summary_{awd}_of_{ac}"]
    artifact.trade_plan_data = plan.to_json()
    saved = store.upsert_artifact(artifact)
    logger.info("[%s] Froze trade plan artifact_id=%s (status=%s)", plan.symbol, saved.artifact_id, saved.status)
    return saved


def approve_trade_plan(
    store: SqliteStrategyStore,
    artifact_id: str,
    config: ForecastSkillConfig | None = None,
    *,
    force: bool = False,
    approver: str = "",
) -> Artifact:
    """Promote a frozen trade plan to ACTIVE, gated by CalibrationGate (fail-closed).

    The calibration tracker is always rebuilt from persisted entries (`load_calibration_tracker`)
    -- never a fresh empty one -- so approval reflects Phase 7's real realized-outcome history,
    not whatever the caller happened to construct.

    Once ACTIVE, a trade plan is immutable -- a revision requires authoring and freezing a
    new artifact, not mutating this one.

    force=True (Stage 0, G2b, research-discussion-v1/complete-plan/
    01-native-gaps.md): an explicit human override that bypasses whichever
    check would otherwise reject -- mirrors vinu_research.promotion's
    existing `/artifacts/{id}/promote?force=true` pattern, same "human
    accountability, not a silent bypass" posture the user chose for this
    (2026-09-10): `approver` is required whenever force is used and is
    logged with the override, not merged into the ordinary approval log
    line, so a forced approval is always distinguishable from a gate-
    cleared one after the fact.
    """
    if force and not approver:
        raise ValueError("approver is required when force=True")
    artifact = store.get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"no artifact with id {artifact_id}")
    if artifact.type != "trade_plan":
        raise ValueError(f"artifact {artifact_id} is not a trade_plan (type={artifact.type})")
    if artifact.status == ArtifactStatus.ACTIVE:
        raise TradePlanApprovalError(
            ["trade plan is already frozen ACTIVE; revisions require authoring a new version"]
        )

    # High-expectations spec #14: re-check the Trade Score tier frozen onto
    # this plan at authoring time. Re-derived from the plan's own JSON, not
    # recomputed -- recomputing would need the same market_state the
    # authoring call had (regime_fit_score in particular isn't reconstructable
    # from the frozen plan alone), so this trusts the tier author_trade_plan()
    # already computed and attached. None (a plan frozen before this phase
    # existed) is treated as "no score to check" -- fail-open for old plans,
    # matching every other "never backfilled" field in this file.
    if artifact.trade_plan_data:
        plan_for_score_check = TradePlan.from_json(artifact.trade_plan_data)
        if plan_for_score_check.trade_score is not None:
            tier = plan_for_score_check.trade_score.tier
            # Same calibrated-thresholds resolution author_trade_plan() itself
            # uses (line ~862 above) -- a fresh plain TradeScoreThresholds()
            # here would silently diverge from authoring's own gate the
            # moment tier-cutoff calibration is added (trade_score_calibration.
            # py deliberately never touches min_tradeable_tier yet, which is
            # the only reason this was harmless until now).
            if not tier_meets_minimum(tier, load_active_thresholds().min_tradeable_tier):
                reasons = [
                    f"trade score tier {tier!r} "
                    f"({plan_for_score_check.trade_score.total_score:.1f}) is below the "
                    "minimum tradeable tier -- refusing to approve a plan the Trade Score "
                    "gate already rejected at authoring time"
                ]
                if not force:
                    logger.warning("[%s] Approval REJECTED: %s", artifact_id, "; ".join(reasons))
                    raise TradePlanApprovalError(reasons)
                logger.warning(
                    "[%s] Approval FORCED by %s despite: %s",
                    artifact_id, approver, "; ".join(reasons),
                )

    tracker = load_calibration_tracker(store, artifact_id, config)

    if not tracker.entries:
        # Stage 0 (G2a bootstrap fix, research-discussion-v1/complete-plan/
        # 01-native-gaps.md): calibration_entries are only ever written by
        # vinu-live's feedback_loop.py after a position closes -- which
        # requires this exact artifact to already be ACTIVE. Checking
        # CalibrationGate on a fresh trade plan (zero entries, always)
        # therefore made approval unsatisfiable for every trade plan ever
        # authored, not just hard to automate -- confirmed 2026-09-10.
        # On a first-ever approval, trust the symbol's own ACTIVE strategy
        # artifact instead: it already cleared vinu_research.promotion.
        # meets_promotion_bar() (deflated Sharpe / holdout / stress / PBO)
        # to get there, which is a real, upstream statistical validation --
        # not a rubber stamp. If the symbol has no ACTIVE strategy backing
        # it at all, still fail closed; there is no statistical basis to
        # approve on.
        symbol = artifact.universe[0] if artifact.universe else ""
        has_active_strategy = any(
            a.type == "strategy"
            for a in store.list_artifacts_for_symbol(symbol, statuses=[ArtifactStatus.ACTIVE])
        )
        if not has_active_strategy:
            reasons = [
                f"no calibration history yet for this trade plan, and no ACTIVE "
                f"strategy artifact for {symbol} to bootstrap approval from"
            ]
            if not force:
                logger.warning("[%s] Approval REJECTED: %s", artifact_id, "; ".join(reasons))
                raise TradePlanApprovalError(reasons)
            logger.warning(
                "[%s] Approval FORCED by %s despite: %s",
                artifact_id, approver, "; ".join(reasons),
            )
        artifact.status = ArtifactStatus.ACTIVE
        saved = store.upsert_artifact(artifact)
        if force:
            logger.info("[%s] Approved (forced by %s) -- trade plan is now ACTIVE", artifact_id, approver)
        else:
            logger.info(
                "[%s] Approved via strategy-bootstrap (no calibration history yet, "
                "%s has an ACTIVE strategy artifact) -- trade plan is now ACTIVE",
                artifact_id, symbol,
            )
        return saved

    gate = CalibrationGate(tracker, min_window=tracker.config.min_calibration_window)
    result = gate.check()
    if not result.passed:
        if not force:
            logger.warning("[%s] Approval REJECTED: %s", artifact_id, "; ".join(result.reasons))
            raise TradePlanApprovalError(result.reasons)
        logger.warning(
            "[%s] Approval FORCED by %s despite: %s",
            artifact_id, approver, "; ".join(result.reasons),
        )

    artifact.status = ArtifactStatus.ACTIVE
    saved = store.upsert_artifact(artifact)
    if force and not result.passed:
        logger.info("[%s] Approved (forced by %s) -- trade plan is now ACTIVE", artifact_id, approver)
    else:
        logger.info("[%s] Approved -- trade plan is now ACTIVE", artifact_id)
    return saved


def record_realized_outcome(
    store: SqliteStrategyStore,
    artifact_id: str,
    actual_return_pct: float,
    config: ForecastSkillConfig | None = None,
) -> CalibrationEntry:
    """Score a closed trade-plan position's realized return against its frozen forecast and
    persist the result -- Phase 7's write path into Phase 4's calibration gate. Reuses
    `CalibrationTracker.add_entry`'s scoring exactly rather than recomputing Brier/directional/
    magnitude-error inline here.

    Also fans the SAME scored outcome out to one AngleCalibrationEntry per
    entry in `artifact.origin_angles` -- the real per-angle calibration
    tracker (previously nonexistent, confirmed by reading this whole
    module and calibration.py directly: nothing anywhere was keyed by
    angle name). Never a second, independently-computed score -- every
    angle attributed to this artifact gets the identical
    directional_correct/brier_score/magnitude_error this one real close
    produced. Empty `origin_angles` (every artifact whose research pass
    didn't report angle usage, or that predates this field) means no
    per-angle entries are written -- silently, not an error, since most
    artifacts genuinely have no attribution data.
    """
    artifact = store.get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"no artifact with id {artifact_id}")
    if not artifact.trade_plan_data:
        raise ValueError(f"artifact {artifact_id} has no trade_plan_data")

    plan = TradePlan.from_json(artifact.trade_plan_data)
    if plan.forecast is None:
        raise ValueError(f"trade plan for {artifact_id} has no forecast to score")

    tracker = CalibrationTracker(artifact_id, config)
    entry = tracker.add_entry(plan.forecast, actual_return_pct)
    saved = store.append_calibration_entry(entry)

    # Self-calibrating TradeScore weights (high-expectations follow-up):
    # this closed trade's frozen trade_score sub-scores, joined to the same
    # actual_return_pct just scored above -- the input the calibration
    # scan later correlates against. Best-effort (never raises), same
    # posture as record_trade_score_outcome's own docstring.
    record_trade_score_outcome(plan.trade_score, plan.direction, actual_return_pct)

    for angle_name in artifact.origin_angles:
        angle_entry = AngleCalibrationEntry(
            angle_name=angle_name,
            artifact_id=artifact_id,
            forecast_direction=entry.forecast_direction,
            actual_return_pct=entry.actual_return_pct,
            forecast_magnitude_pct=entry.forecast_magnitude_pct,
            brier_score=entry.brier_score,
            directional_correct=entry.directional_correct,
            magnitude_error=entry.magnitude_error,
            timestamp=entry.timestamp,
        )
        store.append_angle_calibration_entry(angle_entry)

    logger.info(
        "[%s] Recorded realized outcome: actual_return_pct=%.4f (attributed to %d angle(s))",
        artifact_id, actual_return_pct, len(artifact.origin_angles),
    )
    return saved


def update_in_trade_action(
    store: SqliteStrategyStore, artifact_id: str, action: str,
) -> Artifact | None:
    """Persist vinu-live's continuous re-scoring outcome (HOLD/ADD/REDUCE/
    EXIT, high-expectations spec #10/#11) back onto the frozen TradePlan.
    `TradePlan.in_trade_action` was previously write-only in name --
    the field existed on the schema since Phase 1 but nothing ever called a
    setter for it; vinu-live's classify_action() only ever annotated an
    ephemeral per-cycle dict, never persisted. This closes that loop.

    Fails open (returns None, logs, never raises) on a missing artifact or
    unparseable JSON -- this is telemetry, not something that should be
    able to break vinu-live's cycle if the write fails for any reason. Mirrors
    record_realized_outcome's load/mutate/save shape.
    """
    if action not in (a.value for a in TradeAction):
        logger.warning("[%s] Refusing to persist unrecognized in_trade_action %r", artifact_id, action)
        return None
    try:
        artifact = store.get_artifact(artifact_id)
        if artifact is None or not artifact.trade_plan_data:
            logger.warning("[%s] Cannot persist in_trade_action: artifact or trade_plan_data missing", artifact_id)
            return None
        plan = TradePlan.from_json(artifact.trade_plan_data)
        plan.in_trade_action = action
        artifact.trade_plan_data = plan.to_json()
        store.upsert_artifact(artifact)
        return artifact
    except Exception:
        logger.exception("[%s] Failed to persist in_trade_action=%s, continuing without it", artifact_id, action)
        return None


def load_calibration_tracker(
    store: SqliteStrategyStore,
    artifact_id: str,
    config: ForecastSkillConfig | None = None,
) -> CalibrationTracker:
    """Reconstruct a CalibrationTracker from persisted `calibration_entries` rows."""
    tracker = CalibrationTracker(artifact_id, config)
    tracker.load_entries(store.get_calibration_entries(artifact_id))
    return tracker
