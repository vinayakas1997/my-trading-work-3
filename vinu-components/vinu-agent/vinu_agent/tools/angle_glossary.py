"""Condensed, per-angle glossary blurbs -- what a raw angle_digest line
like `patchtst.direction: up` doesn't tell the model on its own: what the
angle actually measures, how much to trust it, and any real gotcha
(e.g. an angle whose `model_backend` is always a fallback proxy, never
the real pretrained model).

Real gap this closes: `vinu-initial-analysis/vinu_initial_analysis/
catalog/angles.yaml` has a real `title`/`purpose` per angle, but nothing
that reaches an LLM prompt (`angles_tool.py`'s digest, any team's
prompt.md) ever read it -- the model had to guess what a proprietary
name like `shock_personality` or `tips_regime_aware_transformer` meant
purely from its own pretraining. See `missing-pieces-of-system/
angle-comprehension-hierarchy/00-explanation.md` and its `angle-reference/`
folder (this module's real source material -- each blurb here is the
condensed version drafted in that folder's per-angle .md file).

Deliberately NOT injected into every prompt automatically (that would
reproduce the same "flat, always-paid" problem the comprehension-hierarchy
work is trying to get away from) -- see `ExplainAngleTool` in
`angles_tool.py`, which makes this genuinely on-demand: a specialist
only pays the token cost when it actually calls this, for an angle it
doesn't already recognize.
"""

from __future__ import annotations

ANGLE_GLOSSARY: dict[str, str] = {
    "arima": (
        "A classical statistical time-series forecast (ARIMA), not a neural "
        "model -- fits trend/autocorrelation patterns in recent closes. Read "
        "its forecast_price as a simple, interpretable baseline, not a "
        "sophisticated one; its 95% interval is its own honest uncertainty "
        "estimate."
    ),
    "backtesting_44_metrics": (
        "A backward-looking backtest scorecard (44+ real metrics: Sharpe, "
        "drawdown, win rate, VaR/CVaR) -- not a forecast. Tells you how a "
        "strategy/symbol has actually performed historically, useful "
        "evidence, never a signal about what happens next."
    ),
    "chronos": (
        "A general-purpose (not finance-specific) probabilistic forecasting "
        "model -- a comparison baseline, explicitly not this system's "
        "first-choice signal. Read its p10/median/p90 spread as a rough "
        "uncertainty band, and weight it below finance-specific angles like "
        "kronos."
    ),
    "dlinear": (
        "A simple, real (trained-from-scratch, not a big pretrained model) "
        "linear forecast -- splits price into trend + seasonal parts, sums "
        "them. Despite its simplicity, the source survey found this "
        "genuinely competitive on finance. Trust it roughly as much as the "
        "other from-scratch models in this cluster."
    ),
    "drawdown_deep_dive": (
        "A detailed look at this symbol's real historical drawdowns -- how "
        "deep, how long, how fast it recovered, and how much of it news "
        "explains. Backward-looking risk context, not a forecast; use it to "
        "calibrate how much a current move should worry you."
    ),
    "exponential_smoothing": (
        "A classical, \"essentially free\" statistical baseline -- weights "
        "recent prices more than old ones, fits a simple level+trend. No "
        "seasonal component (daily equity data has none). Treat as a cheap "
        "sanity-check baseline, not a sophisticated signal."
    ),
    "garch": (
        "Standard GARCH(1,1) -- forecasts next-period volatility, not "
        "direction. High persistence (alpha+beta close to 1) means today's "
        "volatility regime is likely to keep going, not mean-revert "
        "quickly. Same underlying fit shock_personality uses internally."
    ),
    "itransformer": (
        "A transformer that attends across this symbol's own OHLCV "
        "channels (not across other tickers -- no true cross-asset "
        "attention here despite the name's promise). Read direction from "
        "its close-channel forecast; the other channel forecasts are "
        "supporting detail, not independent signals."
    ),
    "kalman_filters": (
        "Important distinction: this is NOT a forecast -- it's a denoised "
        "estimate of the symbol's current underlying price level and trend "
        "(filters out noise from the raw close series). Use it to read "
        "\"where is this really trading right now,\" not \"where is it "
        "going.\""
    ),
    "kronos": (
        "The flagship finance-specific foundation model here -- pretrained "
        "on 12B real K-line records from 45 exchanges, this system's "
        "closest thing to a \"first-choice\" deep-learning signal (unlike "
        "chronos/timesfm, which are general-purpose comparison baselines). "
        "Check model_backend: if \"fallback_proxy,\" this is a weaker MLP "
        "substitute, not the real model."
    ),
    "lag_llama": (
        "Important: model_backend is ALWAYS \"fallback_proxy\" for this "
        "angle -- the real Lag-Llama model was never installable here, so "
        "this is a simple AR(5) statistical substitute, not the actual "
        "published model. Weigh accordingly, lower confidence than a "
        "genuinely pretrained angle."
    ),
    "lpatchtst": (
        "The single best-performing trained-from-scratch model in this "
        "system's own benchmark survey (57.7% directional accuracy, Sharpe "
        "~2.3) -- an LSTM + patch-transformer hybrid. Among its cluster, "
        "this is one to weight somewhat more, not equally with the weaker "
        "performers."
    ),
    "lstm": (
        "The classical recurrent neural baseline (single-layer LSTM) among "
        "this system's from-scratch models -- a well-known architecture, "
        "treat roughly as a competent generalist forecaster, not the "
        "strongest or weakest of its cluster."
    ),
    "moirai": (
        "Always a \"fallback_proxy\" here (simple AR(3)), never the real "
        "MOIRAI model -- and even the real model's key feature (attending "
        "across multiple tickers at once) can't work through this system's "
        "per-symbol interface anyway. Weight this low, closer to a generic "
        "statistical baseline than a foundation model."
    ),
    "moment": (
        "Always a \"fallback_proxy\" here -- the real MOMENT package "
        "couldn't even be installed in this environment. Also note: MOMENT "
        "is normally multi-task (classification, anomaly detection, "
        "forecasting); only the forecasting piece exists here at all, and "
        "even that isn't the real model."
    ),
    "news_price_causality": (
        "Tests whether news genuinely causes this symbol's price moves "
        "(Granger causality), not just correlates -- a low "
        "granger_causality_p_value means real statistical evidence, not "
        "just \"news and price both moved.\" Distinct from sentiment "
        "scoring elsewhere in the system."
    ),
    "patchtst": (
        "A patch-based transformer forecaster (splits price history into "
        "chunks, attends across them). Related to lpatchtst, which builds "
        "an LSTM hybrid on this same core -- the two aren't fully "
        "independent signals, keep that in mind if both agree."
    ),
    "peer_relative_strength": (
        "Continuous, ongoing co-movement/relative-strength vs. this "
        "symbol's real peer basket -- not the same as shock_clustering, "
        "which only looks at shock days specifically. Positive "
        "relative_return_20d means outperforming that peer over the last "
        "20 days."
    ),
    "pnl_attribution": (
        "This system's OWN real, closed-trade track record for this "
        "symbol -- not a general backtest like backtesting_44_metrics, "
        "this is what actually happened on real fills. Low trade_count "
        "means a wide, unreliable confidence interval; check it before "
        "trusting the win rate."
    ),
    "regime_analysis": (
        "Classifies the symbol into one of 4 real regimes (bull/bear/"
        "high_vol/sideways) right now, plus how it's historically "
        "performed in each. This is the same regime real trade-plan "
        "authoring uses to tilt position sizing -- a genuinely "
        "load-bearing angle, not decorative."
    ),
    "shock_clustering": (
        "Real, load-bearing angle -- cluster_members directly shrinks this "
        "system's real position-size cap and adds a real contingency rule "
        "if populated. Shock-day-only correlation, not a general one; "
        "distinct from peer_relative_strength's continuous version."
    ),
    "shock_personality": (
        "This symbol's own historical reaction pattern to shocks -- real, "
        "load-bearing angle (one of the original two the forecast prompt "
        "read exclusively before this system's angle-digest fix). High "
        "gap_fill_rate means gaps here tend to close; high vol_persistence "
        "means volatility regimes here are sticky, not mean-reverting."
    ),
    "tft": (
        "A quantile forecaster that also reports WHICH engineered features "
        "drove its own prediction (variable_selection_weights) -- the only "
        "angle in its cluster that self-explains its reasoning. A partial, "
        "lightweight version of the real TFT (no known-future/static "
        "covariates modeled)."
    ),
    "timer_timerxl": (
        "A real pretrained foundation model (84M params, 260B time points) "
        "in the normal case -- unlike its p10/p90 band, which is a "
        "post-hoc statistical add-on, not the model's own genuine "
        "uncertainty (contrast with timesfm, whose deciles ARE native "
        "model output)."
    ),
    "timesfm": (
        "General-purpose (not finance-specific) -- a comparison baseline "
        "like chronos, not this system's first-choice signal. Its 9 "
        "deciles ARE the model's genuine trained uncertainty output, not a "
        "post-hoc statistical band (contrast with timer_timerxl's p10/p90, "
        "which is bolted-on)."
    ),
    "tips_regime_aware_transformer": (
        "Its own name is misleading -- \"TIPS\" here is this angle's "
        "internal codename, not the inflation-protected bond. It "
        "self-detects momentum vs. mean-reversion regime (via lag-1 "
        "autocorrelation) and forecasts differently depending which -- "
        "related but distinct from the separate regime_analysis angle's "
        "4-regime classifier."
    ),
    "trend_lifecycle": (
        "Real, load-bearing angle -- stage directly feeds a real "
        "supporting/contradicting signal in real trade-plan authoring's "
        "signal ledger. Matches current price action against a library of "
        "historical peak/trough patterns (KNN) to classify what stage of a "
        "trend this symbol is in right now, and whether a reversal looks "
        "imminent."
    ),
    "trend_session_structure": (
        "A direct extension of trend_lifecycle -- takes the same "
        "peak/trough patterns and asks WHICH intraday session (premarket/"
        "regular/afterhours) they actually happen in. Intraday-only (not "
        "available at the 1D timeframe). Reads best paired with "
        "trend_lifecycle, not standalone."
    ),
}


def explain_angle(angle_name: str) -> str:
    """The glossary blurb for a real angle id, or an honest "no glossary
    entry" message for one not yet covered -- never raises, never
    invents an explanation for an angle this module doesn't actually
    know about."""
    return ANGLE_GLOSSARY.get(
        angle_name,
        f"No glossary entry for '{angle_name}' yet -- not one of the 28 "
        "angles this module currently covers.",
    )
