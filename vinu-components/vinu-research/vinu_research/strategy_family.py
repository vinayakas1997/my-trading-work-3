"""Strategy-family classification for `Artifact.strategy_family` (B,
`missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-
pattern/25-A-Y-details/02-regime-risk-coverage.md`).

**Why this exists, and why it classifies `user_idea` and not
`signal_definition`**: B's design doc originally assumed `Artifact.type`/
`signal_definition` could derive a `strategy_family`. Checked both
directly: `Artifact.type` is a coarse kind flag (`"strategy"`/
`"trade_plan"`), not a style taxonomy; `signal_definition` has no real
writer anywhere -- every real `type="strategy"` artifact
(`service.py::_create_artifact_from_run`) leaves it at its dataclass
default, so it's empty for every artifact that exists today. There is no
existing categorical (or even free-text) field to derive a family from
retroactively -- a brand-new classification scheme, applied going
forward only, same "written once at creation, never backfilled" contract
`regime_tag`/`freeze_hash`/`timeframe` already established on `Artifact`.

`ResearchRunRecord.user_idea` is the field that's actually usable:
required on every real research run (or auto-proposed by
`ResearchService._propose_idea` when omitted -- never silently empty),
and short/descriptive by construction. Confirmed against every real
`user_idea` value in this codebase's own tests and non-LLM fallback
string ("SMA crossover", "momentum breakout", "mean reversion using
bollinger bands strategy", "Trend-following strategy for {stage}
stage...") -- concise strategy-concept phrases a keyword match can
reliably bucket, not free-form prose.

**The taxonomy, and why these 6 buckets**: grounded in the style
categories systematic-trading literature and multi-strategy funds
commonly use to group trading approaches (momentum/trend-following,
mean-reversion, breakout, volatility, statistical arbitrage /
relative-value, event-driven/macro) -- the same "research external
convention, pick something grounded, document the reasoning" resolution
`03-severity-and-trend.md`/`04-reference-baseline-config.md` already used
for the PSI-threshold questions. `unclassified` is a real, honest 7th
bucket -- for refresh/refine runs (`"Refresh {strategy_id}"`, `"Refine
existing strategy for {name}"`) that restate no style at all, not a
classifier failure to paper over.

Ordered so a phrase matching more than one family's keywords (e.g. a
breakout system that also mentions "trend") resolves deterministically --
first match in this list wins, not the reverse.
"""

from __future__ import annotations

# (family, keywords) -- ordered; first match wins, checked top to bottom.
# Keywords are matched as case-insensitive substrings, not whole-word
# tokens, deliberately: a short user_idea phrase ("SMA crossover") has no
# punctuation/stemming to rely on, and false-positive risk here is low
# (these terms are already strategy-specific vocabulary, not common
# English words) -- with one deliberate exception: bare "trend" is NOT a
# momentum keyword, because it's a substring of "counter-trend"/"counter
# trend" (a real mean-reversion synonym -- fading a trend), which would
# otherwise be misclassified as momentum by matching "trend" first.
# mean_reversion is checked first specifically so "counter-trend reversal"
# resolves correctly. "momentum breakout" (a real value seen in this
# codebase's own tests) resolves to momentum, not breakout, since momentum
# is checked before breakout -- a strategy's entry trigger (breakout) is
# treated as secondary to its stated style (momentum) when both appear.
_STRATEGY_FAMILIES: list[tuple[str, tuple[str, ...]]] = [
    (
        "mean_reversion",
        (
            "mean reversion", "mean-reversion", "reversion", "counter-trend",
            "counter trend", "oversold", "overbought", "bollinger", "rsi",
            "z-score", "zscore", "fade",
        ),
    ),
    (
        "momentum",
        (
            "momentum", "trend-following", "trend following",
            "moving average", "sma crossover", "ema crossover", "macd", "adx",
        ),
    ),
    (
        "breakout",
        ("breakout", "donchian", "range expansion", "opening range"),
    ),
    (
        "volatility",
        ("volatility", "vol targeting", "vol-targeting", "straddle", "garch", "vix"),
    ),
    (
        "stat_arb",
        (
            "pairs trading", "pairs", "spread trading", "cointegration",
            "arbitrage", "relative value", "relative-value", "stat arb",
            "statistical arbitrage",
        ),
    ),
    (
        "event_driven",
        ("earnings", "event-driven", "event driven", "macro", "fed announcement", "cpi release"),
    ),
]

UNCLASSIFIED = "unclassified"


def classify_strategy_family(user_idea: str | None) -> str:
    """Classify a research run's `user_idea` into one of the fixed style
    families above, or `UNCLASSIFIED` when no keyword matches (empty
    input included -- never raises)."""
    if not user_idea:
        return UNCLASSIFIED
    lowered = user_idea.lower()
    for family, keywords in _STRATEGY_FAMILIES:
        if any(keyword in lowered for keyword in keywords):
            return family
    return UNCLASSIFIED
