"""Shared point-in-time evidence-confidence math -- item #4 and item #10
(missing-pieces-of-system/new-theory-of-trading/system-wide-audit-and-
design/02-open-questions-strategy-and-simulation.md). Used by both
vinu-research's `track2_aggregate.py` (reads `SignalEvidenceStore`
directly, same process) and vinu-simulator's `EvidenceConfidenceSizer`
(receives already-fetched, pre-filtered trigger data from its caller and
replays this same math once per backtest day, no network calls in the
simulation loop). One formula, every caller -- the same "single source of
truth" reason `vol_target_scale`/`kelly_fraction` already live in this
module's sibling `risk_math.py` rather than each service keeping its own
copy.

Confidence is Laplace-smoothed win rate ((wins + 1) / (n + 2)): with very
few historical triggers on file, a raw win rate of 100%/0% is noise, not a
real edge, so it's pulled toward a coin flip (0.5) until enough sample
exists to move it away -- a standard small-sample correction, not
invented numerology.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


UNKNOWN_REGIME = "unknown"


def regime_of(indicators: dict[str, Any] | None) -> str:
    """Regime label recorded with a trigger, or "unknown" when absent.

    The writer (`signal_evidence/compute.py`) records `indicators["regime"]`
    as a plain string (e.g. "bull"/"bear") only when a regime frame was
    available for that bar -- anything else (missing, None, non-string,
    blank) means "no regime on file", bucketed as unknown rather than
    dropped, so per-regime sample counts always reconcile with the overall
    aggregate.
    """
    regime = (indicators or {}).get("regime")
    if isinstance(regime, str) and regime.strip():
        return regime
    return UNKNOWN_REGIME


def is_news_confounded(indicators: dict[str, Any] | None) -> bool:
    """Whether a news event fell inside the confound window of this trigger.

    Shape contract with the writer: `indicators["news_confound"]` is a dict
    with an `occurred` bool (`{"occurred": False, ...}` when no article
    qualified). Missing or malformed entries count as not confounded --
    absence of evidence is not evidence of confounding.
    """
    confound = (indicators or {}).get("news_confound")
    return isinstance(confound, dict) and confound.get("occurred") is True


def summarize_by_regime(
    resolved_with_indicators: list[tuple[dict[str, Any], dict[str, Any] | None]],
    *,
    as_of_iso: str | None = None,
    reference_now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Partition resolved triggers by recorded regime, summarize each bucket
    with the same Laplace formula (`summarize_resolved_triggers` -- one
    formula, every caller), and additionally summarize each bucket's
    non-news-confounded subset under `ex_news`.

    Returns `{regime: {<summary keys>, "news_confounded": int,
    "ex_news": {<summary keys>}}}`. `news_confounded` is derived as
    full-bucket sample minus clean-bucket sample (both after the same
    point-in-time cut), so it is exact, never estimated. Buckets whose
    clean subset is empty still carry an `ex_news` zero-sample summary
    rather than a missing key, so consumers never guess the shape.
    """
    buckets: dict[str, list[tuple[dict[str, Any], dict[str, Any] | None]]] = {}
    for trigger, indicators in resolved_with_indicators:
        buckets.setdefault(regime_of(indicators), []).append((trigger, indicators))
    result: dict[str, dict[str, Any]] = {}
    for regime, pairs in buckets.items():
        triggers = [t for t, _ in pairs]
        clean = [t for t, ind in pairs if not is_news_confounded(ind)]
        full = summarize_resolved_triggers(
            triggers, as_of_iso=as_of_iso, reference_now=reference_now,
        )
        ex_news = summarize_resolved_triggers(
            clean, as_of_iso=as_of_iso, reference_now=reference_now,
        )
        full["news_confounded"] = full["sample_size"] - ex_news["sample_size"]
        full["ex_news"] = ex_news
        result[regime] = full
    return result


def laplace_smoothed_win_rate(wins: int, n: int) -> float:
    return (wins + 1) / (n + 2)


def summarize_resolved_triggers(
    resolved_triggers: list[dict[str, Any]],
    *,
    as_of_iso: str | None = None,
    reference_now: datetime | None = None,
) -> dict[str, Any]:
    """`resolved_triggers` must already be filtered to the right
    symbol/must_condition and to rows that actually have an outcome on
    file (`outcome_recorded_at` and `return_at_horizon` both set) -- this
    function only does the point-in-time cut and the statistics, not the
    symbol/condition matching. That matching is each caller's own
    data-access concern: a SQL WHERE clause for `track2_aggregate.py`, a
    dict lookup for `EvidenceConfidenceSizer`.

    `as_of_iso`, when given, additionally excludes any trigger whose
    outcome was recorded AFTER that instant -- a trigger's outcome isn't
    knowable until its recording horizon elapses, so including it earlier
    would be lookahead for a backtest replaying history.

    Returns `{"sample_size", "win_rate", "evidence_confidence",
    "avg_return_at_horizon", "days_since_last_trigger"}`; every value but
    `sample_size` is None when `sample_size == 0` -- a caller must decide
    what to do with zero evidence rather than silently getting a number
    computed from nothing.
    """
    resolved = resolved_triggers
    if as_of_iso is not None:
        resolved = [t for t in resolved if t["outcome_recorded_at"] <= as_of_iso]

    sample_size = len(resolved)
    if sample_size == 0:
        return {
            "sample_size": 0,
            "win_rate": None,
            "evidence_confidence": None,
            "avg_return_at_horizon": None,
            "days_since_last_trigger": None,
        }

    returns = [float(t["return_at_horizon"]) for t in resolved]
    wins = sum(1 for r in returns if r > 0)
    win_rate = wins / sample_size
    evidence_confidence = laplace_smoothed_win_rate(wins, sample_size)
    avg_return = sum(returns) / sample_size

    most_recent = max(resolved, key=lambda t: t["trigger_time"])
    most_recent_dt = datetime.fromisoformat(most_recent["trigger_time"])
    if most_recent_dt.tzinfo is None:
        most_recent_dt = most_recent_dt.replace(tzinfo=timezone.utc)
    now = reference_now or datetime.now(timezone.utc)
    days_since_last_trigger = (now - most_recent_dt).days

    return {
        "sample_size": sample_size,
        "win_rate": win_rate,
        "evidence_confidence": evidence_confidence,
        "avg_return_at_horizon": avg_return,
        "days_since_last_trigger": days_since_last_trigger,
    }
