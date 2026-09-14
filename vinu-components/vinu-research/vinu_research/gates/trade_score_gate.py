"""High-expectations spec #14: a calibrated composite "Trade Score" with
tiers (>110 strong, 90-110 moderate, 70-90 watch, <70 no_trade), following
this package's existing gate convention (CalibrationGate in calibration.py,
check_correlation_gate in gates/correlation_gate.py): a verdict dataclass
carrying a pass/fail bool + the numeric signal(s) that drove it + `reasons`,
computed by a plain function from domain inputs + a config threshold, with
an explicit fail-open/closed choice documented per sub-score below.

Sub-score weights/thresholds are an initial heuristic, not a statistically
calibrated model -- same caveat the high-expectations spec itself makes
about its own point system ("the exact scoring system would need to be
statistically calibrated rather than arbitrarily chosen, but the framework
is useful"). Revisit once enough closed trade-plan outcomes exist to fit
these against realized returns (see calibration.py's real, outcome-based
CalibrationTracker for the pattern to follow).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vinu_research.config import TradeScoreThresholds
from vinu_research.models import Forecast, RiskBand, TradeScoreResult

# Ordering used to compare a computed tier against config.min_tradeable_tier.
_TIER_ORDER = {"no_trade": 0, "watch": 1, "moderate": 2, "strong": 3}


@dataclass
class TradeScoreVerdict:
    eligible: bool
    result: TradeScoreResult
    reasons: list[str] = field(default_factory=list)


def _confluence_score(forecast: Forecast, config: TradeScoreThresholds) -> float:
    """0..confluence_max from the structured signal ledger (Forecast.signals,
    Phase 2). Fail-open to a neutral half-score when there are no signals at
    all yet (e.g. a plan authored before Phase 2 populated the ledger) --
    absence of evidence isn't evidence of a bad trade."""
    if not forecast.signals:
        return config.confluence_max / 2.0
    support = sum(s.strength for s in forecast.signals if s.direction == "supporting")
    contradict = sum(s.strength for s in forecast.signals if s.direction == "contradicting")
    total = support + contradict
    if total <= 0:
        return config.confluence_max / 2.0
    ratio = (support - contradict) / total  # in [-1, 1]
    return max(0.0, (ratio + 1.0) / 2.0 * config.confluence_max)


def _ev_score(forecast: Forecast, risk_band: RiskBand, market_state: Any, config: TradeScoreThresholds) -> float:
    """0..ev_max from expected value net of costs. Costs come from
    market_state.liquidity's cost_bps when available, else config's
    default -- fail-open to the default, never to zero cost. High-
    expectations spec #7: when market_state.options carries an ATM IV
    (Phase 5, opt-in), that's added as an extra uncertainty cost -- the
    options market's own priced-in near-term volatility is an independent
    signal on top of the GARCH-based risk_band, not a replacement for it."""
    cost_bps = config.default_cost_bps
    iv_uncertainty = 0.0
    if market_state is not None:
        liquidity = getattr(market_state, "liquidity", None) or {}
        cost_bps = liquidity.get("cost_bps", config.default_cost_bps)
        options = getattr(market_state, "options", None) or {}
        atm_iv = options.get("atm_iv")
        if isinstance(atm_iv, (int, float)):
            # config.iv_uncertainty_weight is a documented heuristic scaling
            # ATM IV into an EV-reducing cost, not a fitted coefficient.
            iv_uncertainty = float(atm_iv) * config.iv_uncertainty_weight
    cost = float(cost_bps) / 10_000.0 + iv_uncertainty
    expected_loss = risk_band.expected_drawdown or risk_band.cvar_95_limit
    ev_net = forecast.confidence * forecast.magnitude_pct - (1.0 - forecast.confidence) * expected_loss - cost
    # config.ev_full_score_pct is the net-EV level treated as a "full score"
    # trade -- an explicit, documented heuristic, not a fitted threshold.
    scaled = (ev_net / config.ev_full_score_pct) * config.ev_max if config.ev_full_score_pct else 0.0
    return max(0.0, min(config.ev_max, scaled))


def _risk_score(risk_band: RiskBand, config: TradeScoreThresholds) -> float:
    """0..risk_max, inverse of expected_drawdown/cvar_95_limit -- same
    linear-combination style as comparison.py's RankedCandidate.risk_score.
    Fail-open to a neutral half-score when neither is computed (0.0 = "not
    computed", same convention RiskBand's fields already use)."""
    downside = risk_band.expected_drawdown or risk_band.cvar_95_limit
    if downside <= 0:
        return config.risk_max / 2.0
    return max(0.0, config.risk_max * (1.0 - min(downside / config.risk_full_loss_pct, 1.0)))


def _regime_fit_score(market_state: Any, config: TradeScoreThresholds) -> float:
    """0..regime_fit_max from Phase 4's market-wide regime analogue engine's
    aggregate positive_ratio. Explicitly 0 (not skipped) when unavailable --
    see get_market_regime_stats in market_regime_analogue.py."""
    if market_state is None:
        return 0.0
    stats = getattr(market_state, "market_regime_stats", None) or {}
    positive_ratio = stats.get("positive_ratio")
    if not isinstance(positive_ratio, (int, float)):
        return 0.0
    return max(0.0, min(config.regime_fit_max, float(positive_ratio) * config.regime_fit_max))


def _tier_for(total_score: float, config: TradeScoreThresholds) -> str:
    if total_score > config.strong_threshold:
        return "strong"
    if total_score >= config.moderate_threshold:
        return "moderate"
    if total_score >= config.watch_threshold:
        return "watch"
    return "no_trade"


def _reward_risk_ratio(forecast: Forecast, risk_band: RiskBand) -> float | None:
    """forecast.magnitude_pct / risk_band.expected_drawdown, or None when
    expected_drawdown hasn't actually been computed (0.0 is RiskBand's
    "not computed" convention, same one _risk_score already fails open on).
    None here means "skip the veto", not "veto" -- matching this module's
    consistent fail-open-on-missing-data posture elsewhere (_confluence_
    score, _ev_score, _risk_score all fail open to a neutral value rather
    than penalize a plan for a field an earlier phase never populated)."""
    downside = risk_band.expected_drawdown
    if downside <= 0:
        return None
    return forecast.magnitude_pct / downside


def compute_trade_score(
    forecast: Forecast,
    risk_band: RiskBand,
    market_state: Any,
    config: TradeScoreThresholds | None = None,
) -> TradeScoreResult:
    """Composite 0..(confluence_max+ev_max+risk_max+regime_fit_max) score
    (defaults to 0..135, matching the high-expectations spec's own scale).
    `market_state` is `vinu_research.market_state.MarketState | None` --
    typed as Any here to avoid a hard import cycle risk; None is always a
    valid, fully-supported input (regime_fit_score simply becomes 0)."""
    config = config or TradeScoreThresholds()

    confluence = _confluence_score(forecast, config)
    ev = _ev_score(forecast, risk_band, market_state, config)
    risk = _risk_score(risk_band, config)
    regime_fit = _regime_fit_score(market_state, config)
    total = confluence + ev + risk + regime_fit
    tier = _tier_for(total, config)

    reasons = [
        f"confluence={confluence:.1f}/{config.confluence_max:.0f}",
        f"ev={ev:.1f}/{config.ev_max:.0f}",
        f"risk={risk:.1f}/{config.risk_max:.0f}",
        f"regime_fit={regime_fit:.1f}/{config.regime_fit_max:.0f}",
        f"total={total:.1f} -> tier={tier}",
    ]

    # High-expectations spec's asymmetry pillar: a hard veto, not just a
    # sub-score penalty -- an otherwise "strong" setup with poor reward:risk
    # must not trade. Forces the TIER itself to no_trade (not just gate
    # eligibility) so this is visible on the persisted TradePlan.trade_score,
    # not only in the ephemeral gate verdict.
    reward_risk = _reward_risk_ratio(forecast, risk_band)
    if reward_risk is not None and reward_risk < config.min_reward_risk_ratio:
        tier = "no_trade"
        reasons.append(
            f"reward:risk {reward_risk:.2f} below minimum {config.min_reward_risk_ratio:.2f} "
            f"-- tier forced to no_trade"
        )

    return TradeScoreResult(
        total_score=total,
        tier=tier,
        confluence_score=confluence,
        ev_score=ev,
        risk_score=risk,
        regime_fit_score=regime_fit,
        reasons=reasons,
    )


def tier_meets_minimum(tier: str, min_tier: str) -> bool:
    """Public tier-ordering comparison so callers outside this module (e.g.
    approve_trade_plan re-checking an already-frozen plan's trade_score.tier)
    don't need to reach into _TIER_ORDER directly."""
    return _TIER_ORDER.get(tier, 0) >= _TIER_ORDER.get(min_tier, 1)


def check_trade_score_gate(
    forecast: Forecast,
    risk_band: RiskBand,
    market_state: Any,
    config: TradeScoreThresholds | None = None,
) -> TradeScoreVerdict:
    """Fail-closed like CalibrationGate.check(): eligible=False when the
    computed tier is below config.min_tradeable_tier. Deliberately has no
    force/approver of its own -- approve_trade_plan() already validates and
    applies force/approver uniformly across every approval gate (this one
    and CalibrationGate), so duplicating that here would be a second,
    inconsistent place to bypass approval from.
    """
    config = config or TradeScoreThresholds()
    result = compute_trade_score(forecast, risk_band, market_state, config)
    eligible = tier_meets_minimum(result.tier, config.min_tradeable_tier)
    reasons = list(result.reasons)
    if not eligible:
        reasons.append(
            f"trade score tier {result.tier!r} ({result.total_score:.1f}) is below "
            f"minimum tradeable tier {config.min_tradeable_tier!r}"
        )
    return TradeScoreVerdict(eligible=eligible, result=result, reasons=reasons)


# Tier -> position-size multiplier, applied on top of the existing
# half-Kelly-capped-10% calc in trade_plan_authoring._build_risk_band --
# hooks into the single existing Kelly path rather than adding a third
# sizing implementation.
TIER_SIZE_MULTIPLIER: dict[str, float] = {
    "strong": 1.0,
    "moderate": 0.7,
    "watch": 0.4,
    "no_trade": 0.0,
}
