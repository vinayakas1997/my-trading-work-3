"""Bridges Track 1's recorded must-condition trigger/outcome data
(SignalEvidenceStore) into HypothesisRegistry -- item #1 (system-wide-
audit-and-design/02-open-questions-strategy-and-simulation.md): Track 1's
signal_evidence angle already records exactly this data, but nothing
ever fed it back into the mechanism (HypothesisRegistry) that already
exists to answer "has this exact condition's evidence validated or
invalidated the hypothesis it belongs to." Item #7 (assumption decay) is
the same gap and is resolved as a side effect of this once it runs.

Deliberately conservative, matching the agreed design:
- Evidence-trail only, no automation. Every entry this writes uses
  `metric_kind="signal_evidence"`, so `HypothesisRegistry.add_evidence()`'s
  Sharpe-specific promotion math (best_sharpe tracking, the 0.3/0.5 status
  thresholds) never fires on it -- a human/agent reads the accumulated
  trail and decides; this never auto-validates or auto-rejects anything.
- Strict match only, no auto-create. A hypothesis is found via
  `query_by_symbol(symbol)`, filtered to an EXACT match on
  `signal_definition == must_condition`. No fuzzy matching, no creating a
  new hypothesis when nothing matches -- that's exactly the fragile-match
  risk item #16 finding #4 already names for a different call site; a
  symbol with no matching hypothesis is skipped and counted, not guessed
  at.
- One evidence entry per (symbol, must_condition) per call, summarizing
  every resolved trigger on file for that condition -- not one entry per
  individual trigger, which would make the evidence list grow unboundedly
  noisy under a recurring (e.g. daily) call cadence.

Run once per cycle over whatever ticker list the caller is already
iterating (e.g. vinu-agent's planner-worker, already processing the
screener-merged watchlist every cycle) -- not a new schedule of its own.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Evidence
from vinu_research.storage.signal_evidence_store import SignalEvidenceStore

LOG = logging.getLogger(__name__)

METRIC_KIND = "signal_evidence"


def _parse_utc(iso: str) -> datetime:
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _summarize_resolved_triggers(triggers: list[dict[str, Any]]) -> dict[str, Any] | None:
    """None when there is nothing with a real outcome yet on file -- a
    trigger recorded but not yet resolved (a live, still-open trigger, per
    SignalEvidenceStore's own docstring) carries no return_at_horizon to
    summarize."""
    resolved = [
        t for t in triggers
        if t.get("outcome_recorded_at") and t.get("return_at_horizon") is not None
    ]
    if not resolved:
        return None
    returns = [float(t["return_at_horizon"]) for t in resolved]
    avg_return = sum(returns) / len(returns)
    win_rate = sum(1 for r in returns if r > 0) / len(returns)
    most_recent = max(resolved, key=lambda t: t["trigger_time"])
    days_since_last_trigger = (datetime.now(timezone.utc) - _parse_utc(most_recent["trigger_time"])).days
    return {
        "count": len(returns),
        "avg_return_at_horizon": avg_return,
        "win_rate": win_rate,
        "days_since_last_trigger": days_since_last_trigger,
    }


def sync_signal_evidence_to_hypotheses(
    symbols: list[str],
    *,
    evidence_store: SignalEvidenceStore,
    hypothesis_registry: HypothesisRegistry,
) -> dict[str, list[str]]:
    """For each symbol, groups its recorded triggers by must_condition,
    summarizes each condition's resolved outcomes, and -- only when an
    exact-matching hypothesis exists -- appends one summary Evidence entry
    to it. Returns `{"updated": [...], "no_matching_hypothesis": [...],
    "no_resolved_triggers": [...]}` (symbol:condition pairs for the first,
    plain symbols for the other two) so a caller (or a test) can see what
    happened without re-deriving it from logs."""
    updated: list[str] = []
    no_matching_hypothesis: list[str] = []
    no_resolved_triggers: list[str] = []

    for symbol in symbols:
        triggers = evidence_store.list_triggers(symbol=symbol, limit=10_000)
        if not triggers:
            no_resolved_triggers.append(symbol)
            continue

        by_condition: dict[str, list[dict[str, Any]]] = {}
        for t in triggers:
            for condition in t["must_condition"]:
                by_condition.setdefault(condition, []).append(t)

        hypotheses = hypothesis_registry.query_by_symbol(symbol)
        symbol_matched = False
        symbol_had_resolved_evidence = False

        for condition, condition_triggers in by_condition.items():
            summary = _summarize_resolved_triggers(condition_triggers)
            if summary is None:
                continue
            symbol_had_resolved_evidence = True

            match = next((h for h in hypotheses if h.signal_definition == condition), None)
            if match is None:
                continue
            symbol_matched = True

            evidence = Evidence(
                run_id=METRIC_KIND,
                iteration=0,
                metric="avg_return_at_horizon",
                value=summary["avg_return_at_horizon"],
                conclusion="supports" if summary["avg_return_at_horizon"] > 0 else "contradicts",
                reasoning=(
                    f"{summary['count']} historical trigger(s) of '{condition}', "
                    f"{summary['win_rate']:.0%} positive, last fired "
                    f"{summary['days_since_last_trigger']} day(s) ago"
                ),
                metrics_snapshot=summary,
                metric_kind=METRIC_KIND,
            )
            result = hypothesis_registry.add_evidence(match.hypothesis_id, evidence)
            if result is not None:
                updated.append(f"{symbol}:{condition}")

        if not symbol_matched:
            if symbol_had_resolved_evidence:
                no_matching_hypothesis.append(symbol)
            else:
                no_resolved_triggers.append(symbol)

    if no_matching_hypothesis:
        LOG.info(
            "signal_evidence_bridge: %d symbol(s) had resolved evidence but no "
            "matching hypothesis (signal_definition mismatch or none exist): %s",
            len(no_matching_hypothesis), no_matching_hypothesis,
        )

    return {
        "updated": updated,
        "no_matching_hypothesis": no_matching_hypothesis,
        "no_resolved_triggers": no_resolved_triggers,
    }
