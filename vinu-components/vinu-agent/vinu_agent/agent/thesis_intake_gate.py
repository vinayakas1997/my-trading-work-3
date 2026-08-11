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

LOG = logging.getLogger(__name__)

# Provisional, not tuned -- same "flag it, don't pretend it's settled"
# discipline as every other un-pinned threshold across this build (N/K
# caps elsewhere, completeness tolerance, PBO bands, rebalance-protect
# gain, shock debounce).
NEAR_DUPLICATE_THRESHOLD = 0.5
K_CAP_DEFAULT = 3

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
    ) -> None:
        self._reader = hypothesis_reader
        self._ticker_ledger = ticker_ledger_store
        self._threshold = near_duplicate_threshold
        self._k_cap = k_cap

    def check(self, ticker: str, thesis_text: str) -> ThGateResult:
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
            count = self._ticker_ledger.count_events(ticker, event_type=CANDIDATE_PROPOSED_EVENT_TYPE)
        except Exception as exc:
            LOG.warning("K-cap lookup failed for %s, defaulting to allow: %s", ticker, exc)
            return ThGateResult(True, "passed THGATE (K-cap check failed, defaulted to allow)")

        if count >= self._k_cap:
            return ThGateResult(
                False, f"ticker at distinct-candidate cap ({count}/{self._k_cap}) this cycle",
            )

        return ThGateResult(True, "passed THGATE")
