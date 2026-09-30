"""Track 2 aggregate confidence engine -- the piece item #4 (simulator
sizing) and item #10 (cross-track disagreement) of
missing-pieces-of-system/new-theory-of-trading/system-wide-audit-and-
design/02-open-questions-strategy-and-simulation.md are both blocked on.

`SignalEvidenceStore` already records one raw row per must-condition
trigger (Track 1) plus every supporting indicator's raw snapshot, but by
its own explicit design ("no bucketing, no thresholds, no derived
columns anywhere in this module -- that's the analysis layer's job") it
never turns those rows into a number. This module is that analysis
layer, for exactly one question: "given everything on file for this
symbol+condition up to this instant, how much should that evidence be
trusted?"

Deliberately narrow, matching `signal_evidence_bridge.py`'s own
conservatism:
- Point-in-time safe. `as_of` (unix seconds, same convention item #22
  finding #3 threaded through vinu-strategy) filters to triggers whose
  outcome was *known* by that instant (`outcome_recorded_at <= as_of`),
  not merely triggered by it -- a trigger's own outcome isn't knowable
  until its recording horizon elapses, so including it earlier would be
  lookahead. Omitted `as_of` means "everything resolved so far,"
  matching every other as_of-less caller's existing behavior.
- The actual point-in-time cut and Laplace-smoothing math is delegated to
  `vinu_infra.evidence_confidence.summarize_resolved_triggers` -- the same
  function `vinu-simulator`'s `EvidenceConfidenceSizer` calls, so a
  backtest's per-day confidence number and this HTTP endpoint's number
  can never silently diverge into two independently-derived formulas.
  This module's own job is only the DB-specific part: fetching and
  filtering `SignalEvidenceStore`'s rows by symbol/must_condition.
- `insufficient_evidence` is an explicit flag (sample_size below
  `min_sample_size`, default 5), not a silently-still-returned number --
  a consumer (sizer, disagreement comparator) must decide what to do
  with too little evidence rather than unknowingly acting on it.
- Read-only. No new table -- this is a query over the store that
  already exists, mirroring how `candidate_graveyard.py` reads three
  existing stores rather than adding a fourth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vinu_infra.evidence_confidence import summarize_by_regime, summarize_resolved_triggers
from vinu_research.storage.signal_evidence_store import SignalEvidenceStore


def compute_track2_aggregate(
    symbol: str,
    must_condition: str,
    *,
    evidence_store: SignalEvidenceStore,
    as_of: int | None = None,
    min_sample_size: int = 5,
) -> dict[str, Any]:
    """Returns:
    {
        "symbol", "must_condition", "as_of",
        "sample_size": int,               # resolved triggers matching this condition, as of `as_of`
        "insufficient_evidence": bool,    # sample_size < min_sample_size
        "win_rate": float | None,         # raw, None if sample_size == 0
        "evidence_confidence": float | None,  # Laplace-smoothed win rate, None if sample_size == 0
        "avg_return_at_horizon": float | None,
        "days_since_last_trigger": int | None,
        # Regime-aware breakdown (A1 fix): same Laplace formula per
        # recorded regime bucket, each with its non-news-confounded
        # subset under "ex_news". Additive only -- every key above keeps
        # its exact prior meaning so existing consumers never change.
        "by_regime": {regime: {<summary keys>, "news_confounded": int, "ex_news": {<summary keys>}}},
        "news_confounded_total": int,     # confounded triggers across all buckets
    }
    """
    as_of_iso = (
        datetime.fromtimestamp(as_of, tz=timezone.utc).isoformat()
        if as_of is not None
        else None
    )
    reference_now = (
        datetime.fromtimestamp(as_of, tz=timezone.utc) if as_of is not None
        else None
    )

    triggers = evidence_store.list_triggers(symbol=symbol, limit=10_000)
    matching = [t for t in triggers if must_condition in t["must_condition"]]
    resolved = [
        t for t in matching
        if t.get("outcome_recorded_at") and t.get("return_at_horizon") is not None
    ]

    summary = summarize_resolved_triggers(
        resolved, as_of_iso=as_of_iso, reference_now=reference_now,
    )

    indicators_by_id = evidence_store.get_indicators_for_triggers(
        [t["trigger_id"] for t in resolved]
    )
    by_regime = summarize_by_regime(
        [(t, indicators_by_id.get(t["trigger_id"])) for t in resolved],
        as_of_iso=as_of_iso,
        reference_now=reference_now,
    )

    return {
        "symbol": symbol,
        "must_condition": must_condition,
        "as_of": as_of,
        "sample_size": summary["sample_size"],
        "insufficient_evidence": summary["sample_size"] < min_sample_size,
        "win_rate": summary["win_rate"],
        "evidence_confidence": summary["evidence_confidence"],
        "avg_return_at_horizon": summary["avg_return_at_horizon"],
        "days_since_last_trigger": summary["days_since_last_trigger"],
        "by_regime": by_regime,
        "news_confounded_total": sum(b["news_confounded"] for b in by_regime.values()),
    }
