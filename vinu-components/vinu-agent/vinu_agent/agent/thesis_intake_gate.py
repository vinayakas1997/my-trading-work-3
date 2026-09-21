"""THGATE (Phase 6, New-talk-agents/new-thinking/new-restructure/phases/
phase-6-thesis-intake/) -- the cost-control gate ahead of Thesis Intake
itself, same shape as Phase 0's change-gate (GATE) applied to a different
question: cheap, deterministic, no LLM call. Only "no duplicate AND under
budget" reaches Thesis Intake (an LLM call).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from vinu_research.models import ArtifactStatus

LOG = logging.getLogger(__name__)

# Every status except DECAYED/DISABLED -- mermaid-explanation.md's Planner
# section: triage "must span every non-terminal state (CREATED, BENCHING,
# ACTIVE, MONITORING), not ACTIVE alone." PEND/PENDBLOCK postdate that doc
# (Phase 2/3) but are non-terminal by the same logic -- a candidate
# awaiting funding or held by the Kill Switch is still "already in flight."
# Shared here (not in planner_triage_hook.py, which imports it from this
# module) since thesis_intake_gate.py's own K-cap check needs it too, once
# a real strategy_store is provided -- see ThesisIntakeGate.__init__.
NON_TERMINAL_STATUSES = [
    ArtifactStatus.CREATED, ArtifactStatus.BENCHING, ArtifactStatus.PEND,
    ArtifactStatus.PENDBLOCK, ArtifactStatus.ACTIVE, ArtifactStatus.MONITORING,
]

# Provisional, not tuned -- same "flag it, don't pretend it's settled"
# discipline as every other un-pinned threshold across this build (N/K
# caps elsewhere, completeness tolerance, PBO bands, rebalance-protect
# gain, shock debounce).
NEAR_DUPLICATE_THRESHOLD = 0.5
K_CAP_DEFAULT = 3

# Real bug, found live 2026-09-21 (missing-pieces-of-system/
# startegy-enhancer/00-explanation.md section 1): this K-cap's count_events()
# call never passed `since=`, so the count was all-time/lifetime with no
# reset -- a ticker with 3 real candidate_proposed events, ever (rejected,
# expired, or successful), was silently locked out of ever getting another
# proposal again, despite the check's own name ("...cap... this cycle")
# implying a live, resettable limit. K_CAP_WINDOW_DAYS makes it one --
# provisional, not tuned, same disclaimer as K_CAP_DEFAULT itself; a real
# per-candidate "is it still genuinely open" count (01-plan.md's Option B)
# would be the more correct fix but needs a real run_id->artifact_id join
# that doesn't exist yet (see 02-implementation.md) -- this rolling window
# is the honest, buildable fix available today.
K_CAP_WINDOW_DAYS = 7


def _k_cap_window_since() -> str:
    import time

    return time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - K_CAP_WINDOW_DAYS * 86400)
    )

# The TickerLedger event_type a "worth checking" hand-off writes -- the
# shared counter both this gate and (eventually) a watchlist-side writer
# query, so there is exactly one source of truth for "how many distinct
# candidates has this ticker had this cycle," not a separate counter per
# entry point. See 01-plan.md.
CANDIDATE_PROPOSED_EVENT_TYPE = "candidate_proposed"


def jaccard_similarity(a: str, b: str) -> float:
    """The stated, testable near-duplicate definition (02-guard-rail.md:
    'not a vague LLM judgment call') -- token-overlap on lowercased,
    whitespace-split words. Deliberately simple and deterministic: THGATE
    runs before any LLM call exists to judge similarity with."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


class HypothesisReader(Protocol):
    def query_by_symbol(self, ticker: str) -> list[dict[str, Any]]: ...


class TickerLedgerCounter(Protocol):
    def count_events(self, ticker: str, *, event_type: str | None = None) -> int: ...


@dataclass
class ThGateResult:
    allowed: bool
    reason: str
    matched_hypothesis_id: str | None = None
    matched_thesis: str | None = None


class ThesisIntakeGate:
    def __init__(
        self,
        hypothesis_reader: HypothesisReader,
        ticker_ledger_store: TickerLedgerCounter,
        *,
        near_duplicate_threshold: float = NEAR_DUPLICATE_THRESHOLD,
        k_cap: int = K_CAP_DEFAULT,
        strategy_store: Any = None,
    ) -> None:
        self._reader = hypothesis_reader
        self._ticker_ledger = ticker_ledger_store
        self._threshold = near_duplicate_threshold
        self._k_cap = k_cap
        # Real fix, 2026-09-21 (missing-pieces-of-system/startegy-enhancer/
        # 02-implementation.md): when provided, the K-cap counts real,
        # currently non-terminal artifacts for the ticker -- same shape
        # planner_triage_hook.py's PlannerTriage now uses -- instead of a
        # rolling time window over ticker_ledger events. Optional (default
        # None) so the one existing caller (submit_thesis_tool.py) opts in
        # explicitly rather than this silently changing behavior for any
        # other untouched caller; falls back to the time-window count when
        # not provided.
        self._strategy_store = strategy_store

    def check(self, ticker: str, thesis_text: str, human_priority: bool = False) -> ThGateResult:
        """Fail-closed direction here is toward ALLOWING through to
        Thesis Intake on either lookup failing -- this is a cost gate, not
        a safety gate (unlike Phase 3's Kill Switch check): the worst case
        of a false "allow" is one avoidable LLM call, the same category as
        Phase 0's RunLog trigger. Blocking a human's legitimate submission
        because of a transient DB error would be the worse outcome here,
        matching this gate's own guard rail: 'too strict and the gate
        saves nothing.'"""
        ticker = ticker.upper()

        try:
            existing = self._reader.query_by_symbol(ticker)
        except Exception as exc:
            LOG.warning("Near-duplicate lookup failed for %s, defaulting to allow: %s", ticker, exc)
            existing = []

        for h in existing:
            sim = jaccard_similarity(thesis_text, h.get("thesis", ""))
            if sim >= self._threshold:
                return ThGateResult(
                    allowed=False,
                    reason=(
                        f"near-duplicate of existing theory "
                        f"(similarity={sim:.2f} >= threshold {self._threshold})"
                    ),
                    matched_hypothesis_id=h.get("hypothesis_id"),
                    matched_thesis=h.get("thesis"),
                )

        try:
            if self._strategy_store is not None:
                count = len(self._strategy_store.list_artifacts_for_symbol(ticker, statuses=NON_TERMINAL_STATUSES))
                window_note = "currently non-terminal"
            else:
                count = self._ticker_ledger.count_events(
                    ticker, event_type=CANDIDATE_PROPOSED_EVENT_TYPE, since=_k_cap_window_since(),
                )
                window_note = f"in the last {K_CAP_WINDOW_DAYS} days"
        except Exception as exc:
            LOG.warning("K-cap lookup failed for %s, defaulting to allow: %s", ticker, exc)
            return ThGateResult(True, "passed THGATE (K-cap check failed, defaulted to allow)")

        # Human priority (07 No.7): human theories bypass K-cap, never blocked
        # by machine proposal count. Duplicate check above still applies.
        if count >= self._k_cap and not human_priority:
            return ThGateResult(
                False, f"ticker at distinct-candidate cap ({count}/{self._k_cap}) {window_note}",
            )
        if count >= self._k_cap and human_priority:
            return ThGateResult(True, "passed THGATE (human priority bypasses K-cap)")

        return ThGateResult(True, "passed THGATE")
