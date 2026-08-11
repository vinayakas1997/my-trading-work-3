"""Significance Triage (Phase 7, New-talk-agents/new-thinking/
new-restructure/phases/phase-7-significance-triage/): actively decides,
unprompted, whether an already-completed autonomous decision is routine
(skip) or unusual enough to surface to a human now. Distinct from
`audit/research_digest.py`'s passive replay-on-ask shape.

Never blocks anything -- every event this module reacts to has already
happened by the time a flag is raised (02-guard-rail.md). Delivery reuses
the existing Discord/Telegram channel wiring
(`vinu_agent/channels/discord.py`, `telegram.py`) -- no new polling
endpoint.

Three concrete pattern detectors ship now:

1. `detect_repeated_rejection_pattern` -- repeated risk_gatekeeper
   REJECTED verdicts for the same ticker. Original Phase 7 detector.
2. `detect_large_funding_pattern` -- a single capital_allocator funding
   decision at or above a dollar threshold. The threshold has NO default
   pinned in this module -- callers must pass in
   `TradingMandate.load().max_order_value` (broker/mandate.py), the one
   dollar ceiling this project has already decided on and the user
   already committed to. Reusing it here is not the same as inventing a
   second, ungrounded number.
3. `detect_thesis_contradiction_pattern` -- a position closed in a way
   that contradicts its original thesis (`broker/debrief.py`'s own
   `conclusion="contradicts"` judgment, sign-of-realized-P&L -- the only
   real signal that exists; no magnitude/"expected decay" baseline is
   stored anywhere in this project to compare against, so this stays a
   coarser signal than the plan's "surprising rather than expected decay"
   language implies. Flagged here, not silently pretended away.) `min_count`
   defaults to 1 -- there is no basis for a repeated-count threshold here
   the way there is for rejections, so every contradiction is significant
   by default rather than inventing a count.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from vinu_infra.sqlite import SQLiteBackend

LOG = logging.getLogger(__name__)

# Provisional, not tuned -- same "flag it, don't pretend it's settled"
# discipline as every other un-pinned threshold across this build.
REJECTED_PATTERN_MIN_COUNT = 3
REJECTED_PATTERN_WINDOW_HOURS = 24.0
LARGE_FUNDING_WINDOW_HOURS = 24.0
THESIS_CONTRADICTION_WINDOW_HOURS = 24.0
THESIS_CONTRADICTION_MIN_COUNT = 1

_AMOUNT_RE = re.compile(r"amount=([0-9.]+)")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_flag_id() -> str:
    return uuid.uuid4().hex[:12]


def _hours_ago_iso(hours: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - hours * 3600))


# ---------------------------------------------------------------------------
# Flag storage
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS significance_flags (
    flag_id       TEXT PRIMARY KEY,
    ticker        TEXT NOT NULL,
    reason        TEXT NOT NULL,
    detail        TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    responded_at  TEXT NOT NULL DEFAULT '',
    response_text TEXT NOT NULL DEFAULT '',
    resolved      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_significance_flags_ticker ON significance_flags(ticker);
CREATE INDEX IF NOT EXISTS idx_significance_flags_resolved ON significance_flags(resolved);
"""


@dataclass
class SignificanceFlag:
    flag_id: str
    ticker: str
    reason: str
    detail: str
    created_at: str
    responded_at: str = ""
    response_text: str = ""
    resolved: bool = False

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "SignificanceFlag":
        return cls(
            flag_id=row["flag_id"], ticker=row["ticker"], reason=row["reason"], detail=row["detail"],
            created_at=row["created_at"], responded_at=row.get("responded_at", ""),
            response_text=row.get("response_text", ""), resolved=bool(row.get("resolved", 0)),
        )


class SignificanceFlagStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def create_flag(self, ticker: str, reason: str, detail: str) -> SignificanceFlag:
        flag = SignificanceFlag(
            flag_id=_new_flag_id(), ticker=ticker.upper(), reason=reason, detail=detail, created_at=_now(),
        )
        self.upsert(
            "significance_flags",
            {
                "flag_id": flag.flag_id, "ticker": flag.ticker, "reason": flag.reason,
                "detail": flag.detail, "created_at": flag.created_at,
                "responded_at": "", "response_text": "", "resolved": 0,
            },
            conflict_columns=["flag_id"],
        )
        return flag

    def get_flag(self, flag_id: str) -> SignificanceFlag | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM significance_flags WHERE flag_id = ?", (flag_id,)).fetchone()
        return SignificanceFlag.from_row(dict(row)) if row else None

    def mark_responded(self, flag_id: str, response_text: str) -> SignificanceFlag | None:
        """A flag with NO response ever, forever, is not an error state
        (02-guard-rail.md) -- this method is the only thing that ever
        changes `resolved`; nothing times out or retries on its own."""
        flag = self.get_flag(flag_id)
        if flag is None:
            return None
        conn = self._get_conn()
        now = _now()
        conn.execute(
            "UPDATE significance_flags SET responded_at = ?, response_text = ?, resolved = 1 WHERE flag_id = ?",
            (now, response_text, flag_id),
        )
        conn.commit()
        flag.responded_at = now
        flag.response_text = response_text
        flag.resolved = True
        return flag

    def response_rate(self) -> dict[str, Any]:
        """Alert-fatigue measurement, from day one (02-guard-rail.md) --
        the raw signal for whether the threshold needs tightening later,
        not a guess."""
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM significance_flags").fetchone()[0]
        responded = conn.execute("SELECT COUNT(*) FROM significance_flags WHERE resolved = 1").fetchone()[0]
        rate = (responded / total) if total else None
        return {"total": total, "responded": responded, "rate": rate}


# ---------------------------------------------------------------------------
# Pattern detection -- queries TickerLedger directly, never a separate
# counter (02-guard-rail.md, same discipline as Phase 6's shared K-cap).
# ---------------------------------------------------------------------------

class TickerLedgerCounter(Protocol):
    def count_events(
        self, ticker: str, *, stage: str | None = None, event_type: str | None = None, since: str | None = None,
    ) -> int: ...


def detect_repeated_rejection_pattern(
    ticker: str,
    ticker_ledger_store: TickerLedgerCounter,
    *,
    min_count: int = REJECTED_PATTERN_MIN_COUNT,
    window_hours: float = REJECTED_PATTERN_WINDOW_HOURS,
) -> dict[str, Any] | None:
    count = ticker_ledger_store.count_events(
        ticker, stage="risk_gatekeeper", event_type="REJECTED", since=_hours_ago_iso(window_hours),
    )
    if count >= min_count:
        return {"ticker": ticker.upper(), "count": count, "window_hours": window_hours}
    return None


class TickerLedgerReader(Protocol):
    def get_events(self, ticker: str) -> list[Any]: ...


def detect_large_funding_pattern(
    ticker: str,
    ticker_ledger_store: TickerLedgerReader,
    *,
    threshold: float,
    window_hours: float = LARGE_FUNDING_WINDOW_HOURS,
) -> dict[str, Any] | None:
    """`threshold` has no default -- pass `TradingMandate.load().
    max_order_value` (see module docstring). Reads capital_allocator's
    "funded" TickerLedger events directly (`capital_allocator_hook.py`
    writes `text=f"...amount={amount}"`, no separate numeric column
    exists -- parsed back out here rather than adding a migration for a
    single detector's convenience)."""
    since = _hours_ago_iso(window_hours)
    for event in ticker_ledger_store.get_events(ticker):
        if event.stage != "capital_allocator" or event.event_type != "funded":
            continue
        if event.timestamp < since:
            continue
        match = _AMOUNT_RE.search(event.text)
        if not match:
            continue
        amount = float(match.group(1))
        if amount >= threshold:
            return {
                "ticker": ticker.upper(), "amount": amount, "threshold": threshold,
                "window_hours": window_hours, "ledger_id": event.ledger_id,
            }
    return None


def detect_thesis_contradiction_pattern(
    ticker: str,
    ticker_ledger_store: TickerLedgerCounter,
    *,
    min_count: int = THESIS_CONTRADICTION_MIN_COUNT,
    window_hours: float = THESIS_CONTRADICTION_WINDOW_HOURS,
) -> dict[str, Any] | None:
    """Reads `broker/debrief.py`'s `stage="debrief",
    event_type="thesis_contradicted"` events -- written there, not
    detected here, since debrief.py is the one place that already knows
    both the closed position's P&L and its original open hypothesis."""
    count = ticker_ledger_store.count_events(
        ticker, stage="debrief", event_type="thesis_contradicted", since=_hours_ago_iso(window_hours),
    )
    if count >= min_count:
        return {"ticker": ticker.upper(), "count": count, "window_hours": window_hours}
    return None


# ---------------------------------------------------------------------------
# Delivery -- reuses the existing channel wiring, one flag_id shared
# across every configured channel (02-guard-rail.md: "one logical
# notification, not one per channel").
# ---------------------------------------------------------------------------

class Channel(Protocol):
    async def send_message(self, chat_id: str, text: str) -> None: ...


@dataclass
class ChannelTarget:
    channel: Channel
    chat_id: str


def format_flag_message(flag: SignificanceFlag) -> str:
    return (
        f"[Significance Triage] {flag.reason} -- {flag.ticker}\n"
        f"{flag.detail}\n"
        f"flag_id: {flag.flag_id}"
    )


async def deliver_flag(flag: SignificanceFlag, targets: list[ChannelTarget]) -> None:
    """Best-effort per channel -- one channel failing must not prevent
    delivery through the others, and never raises back into the caller
    (informational only, see module docstring)."""
    text = format_flag_message(flag)
    for target in targets:
        try:
            await target.channel.send_message(target.chat_id, text)
        except Exception:
            LOG.exception("failed to deliver flag %s via a channel, continuing with the others", flag.flag_id)


# ---------------------------------------------------------------------------
# Closing the loop back -- a human's response becomes real evidence.
# ---------------------------------------------------------------------------

def record_human_override(
    research_api_url: str,
    hypothesis_id: str,
    flag_id: str,
    *,
    source: str,
    conclusion: str,
    reasoning: str,
    value: float = 0.0,
) -> bool:
    """The ONLY write path Phase 7 uses for a human's response to a flag.
    `source` has NO default -- omitting it is a TypeError, not a silent
    blank/wrong provenance tag (02-guard-rail.md, same rule as Phase 6's
    source="human"). `flag_id` becomes the evidence's real `ref_id` field
    (added to Evidence/AddEvidenceRequest alongside `source` this phase),
    linking the Planner's later pre-proposal consult straight back to the
    specific flag that prompted a human's correction.
    """
    if source != "human_override":
        raise ValueError(f"record_human_override only ever writes source='human_override', got {source!r}")

    try:
        from vinu_research.models import Evidence

        from ..broker.research_link import get_hypothesis_registry

        evidence = Evidence(
            run_id=0, iteration=0, metric="human_override", value=value,
            conclusion=conclusion, reasoning=reasoning, source=source, ref_id=flag_id,
        )
        h = get_hypothesis_registry().add_evidence(hypothesis_id, evidence)
        if h is not None:
            return True
        LOG.warning("in-process human-override write found no hypothesis %s, falling back to HTTP", hypothesis_id)
    except Exception:
        LOG.debug("in-process human-override write failed for hypothesis %s, falling back to HTTP", hypothesis_id, exc_info=True)

    try:
        import httpx

        resp = httpx.post(
            f"{research_api_url}/research/hypotheses/{hypothesis_id}/evidence",
            json={
                "metric": "human_override",
                "value": value,
                "conclusion": conclusion,
                "reasoning": reasoning,
                "source": source,
                "ref_id": flag_id,
            },
            timeout=15,
        )
        return resp.status_code == 200
    except Exception:
        LOG.exception("failed to record human override evidence for hypothesis %s (flag %s)", hypothesis_id, flag_id)
        return False
