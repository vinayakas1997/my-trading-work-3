"""Planner triage (Phase 9 scheduler-wiring, New-talk-agents/new-thinking/
new-restructure/phases/phase-9-scheduler-wiring/): the deterministic half
of the Planner role described in mermaid-explanation.md's Section 2
("ticker/strategy fit triage" ahead of `idea_generator`). Same shape as
`thesis_intake_gate.py`'s THGATE applied to the watchlist entry point
instead of the human-theory one: cheap, deterministic checks decide
WHETHER and WHAT to propose. `idea_generator` (real, in `teams/research/`)
is a separate, downstream LLM step this module never calls itself -- see
`agent/scheduler_workers.py` for that wiring.

Shares THGATE's own K-cap counter -- `CANDIDATE_PROPOSED_EVENT_TYPE` is a
generic `TickerLedger` event_type, not a Thesis-Intake-only store, exactly
as `thesis_intake_gate.py`'s own comment already states ("the shared
counter both this gate and (eventually) a watchlist-side writer query").
This module is that watchlist-side writer -- closes the Phase 6 follow-up
("candidate_proposed events from the watchlist/Planner side aren't
wired").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from vinu_research.models import ArtifactStatus

from .thesis_intake_gate import CANDIDATE_PROPOSED_EVENT_TYPE, K_CAP_DEFAULT

LOG = logging.getLogger(__name__)

# Every status except DECAYED/DISABLED -- mermaid-explanation.md's Planner
# section: triage "must span every non-terminal state (CREATED, BENCHING,
# ACTIVE, MONITORING), not ACTIVE alone." PEND/PENDBLOCK postdate that doc
# (Phase 2/3) but are non-terminal by the same logic -- a candidate
# awaiting funding or held by the Kill Switch is still "already in flight."
NON_TERMINAL_STATUSES = [
    ArtifactStatus.CREATED, ArtifactStatus.BENCHING, ArtifactStatus.PEND,
    ArtifactStatus.PENDBLOCK, ArtifactStatus.ACTIVE, ArtifactStatus.MONITORING,
]


class ArtifactReader(Protocol):
    def list_artifacts_for_symbol(self, symbol: str, statuses: list[Any] | None = None) -> list[Any]: ...


class HypothesisReader(Protocol):
    def query_by_symbol(self, ticker: str) -> list[dict[str, Any]]: ...


class TickerLedgerCounter(Protocol):
    def count_events(self, ticker: str, *, event_type: str | None = None) -> int: ...
    def add_event(self, ticker: str, stage: str, event_type: str, text: str, *, ref_id: str = "", source: str = "watchlist") -> Any: ...


def _default_recipes() -> list[str]:
    try:
        from vinu_research.generator import list_recipes
        return list_recipes()
    except Exception:
        LOG.warning("could not load real sweep recipes -- Planner triage will report none available")
        return []


@dataclass
class PlannerTriageResult:
    ticker: str
    should_propose: bool
    reason: str
    recipe_name: str = ""
    prior_rejections: list[str] = field(default_factory=list)


class PlannerTriage:
    """The triage half of mermaid-explanation.md's Planner (Section 2) --
    `idea_generator` (real, in `teams/research/`) is the idea-shaping
    half, invoked separately (see `agent/scheduler_workers.py`), never
    from here."""

    def __init__(
        self,
        strategy_store: ArtifactReader,
        hypothesis_reader: HypothesisReader,
        ticker_ledger_store: TickerLedgerCounter,
        *,
        k_cap: int = K_CAP_DEFAULT,
        recipes: list[str] | None = None,
    ) -> None:
        self._strategy_store = strategy_store
        self._hypothesis_reader = hypothesis_reader
        self._ticker_ledger = ticker_ledger_store
        self._k_cap = k_cap
        self._recipes = recipes if recipes is not None else _default_recipes()

    def check(self, ticker: str) -> PlannerTriageResult:
        """Fail-closed direction here is toward SKIPPING on any lookup
        failure -- same cost-only category as Phase 0's RunLog trigger and
        THGATE's own near-duplicate check, not a safety gate: the worst
        case of a wrongly-skipped ticker is one missed proposal this
        cycle, picked up again next cycle, never a funding/execution risk."""
        ticker = ticker.upper()

        try:
            count = self._ticker_ledger.count_events(ticker, event_type=CANDIDATE_PROPOSED_EVENT_TYPE)
        except Exception as exc:
            LOG.warning("Planner K-cap lookup failed for %s, defaulting to skip: %s", ticker, exc)
            return PlannerTriageResult(ticker, False, f"K-cap lookup failed, defaulting to skip: {exc}")

        if count >= self._k_cap:
            return PlannerTriageResult(
                ticker, False, f"ticker at distinct-candidate cap ({count}/{self._k_cap}) this cycle",
            )

        try:
            existing = self._strategy_store.list_artifacts_for_symbol(ticker, statuses=NON_TERMINAL_STATUSES)
        except Exception as exc:
            LOG.warning("Planner artifact lookup failed for %s, defaulting to skip: %s", ticker, exc)
            return PlannerTriageResult(ticker, False, f"artifact lookup failed, defaulting to skip: {exc}")

        try:
            prior = self._hypothesis_reader.query_by_symbol(ticker)
        except Exception as exc:
            LOG.warning("HypothesisRegistry consult failed for %s, proceeding without it: %s", ticker, exc)
            prior = []
        prior_rejections = [
            (h.get("invalidation_reason") or h.get("thesis", ""))
            for h in prior if h.get("status") == "rejected"
        ]

        if not self._recipes:
            return PlannerTriageResult(ticker, False, "no sweep recipes available")

        # Deterministic, provisional rotation -- guarantees a DIFFERENT
        # recipe than however many non-terminal artifacts already exist
        # for this ticker, without needing a stored "recipe used" field on
        # Artifact (none exists). Flagged first-pass, same category as
        # every other un-pinned heuristic across this build: real angle-
        # characteristic-driven recipe matching is idea_generator's own
        # LLM job downstream, per mermaid-explanation.md's Planner section
        # ("Idea shaping... tied explicitly to the angle characteristics
        # that motivated it") -- this hook only has to pick a reasonable
        # starting point, not the final answer.
        recipe_name = self._recipes[len(existing) % len(self._recipes)]

        return PlannerTriageResult(
            ticker, True,
            f"{len(existing)} non-terminal artifact(s) already in flight, "
            f"{len(prior_rejections)} prior rejected hypothesis/es on record",
            recipe_name=recipe_name,
            prior_rejections=prior_rejections,
        )

    def on_propose(self, ticker: str, result: PlannerTriageResult, *, ref_id: str = "") -> None:
        """Best-effort write of the shared K-cap counter's write side --
        THGATE's own read side already queries this same event_type."""
        try:
            self._ticker_ledger.add_event(
                ticker.upper(), "planner", CANDIDATE_PROPOSED_EVENT_TYPE,
                f"triage proposed recipe={result.recipe_name}: {result.reason}",
                ref_id=ref_id, source="watchlist",
            )
        except Exception:
            LOG.exception("failed to write candidate_proposed TickerLedger event for %s, continuing without it", ticker)
