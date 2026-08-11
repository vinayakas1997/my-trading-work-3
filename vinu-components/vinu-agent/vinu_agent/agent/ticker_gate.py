"""Phase 0 pieces 2 and 3: the RunLog-driven trigger for the Summary
Agent, and the change-gate (GATE) ahead of the Planner. Neither is a team
and neither touches an LLM directly -- both are cheap, deterministic
checks that decide whether an LLM pass is even worth running, same
"Python hook beside a team, not a team itself" pattern as
broker/risk_gatekeeper_hook.py. See New-talk-agents/new-thinking/
new-restructure/phases/phase-0-foundation-plumbing/.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .. import config as _config_module
from ..storage.ticker_ledger import TickerLedgerStore
from ..storage.ticker_summaries import TickerSummaryStore

LOG = logging.getLogger(__name__)


class RunLogReader(Protocol):
    def latest_run_id(self, ticker: str) -> str | None: ...


class HttpRunLogReader:
    """Real transport: vinu-initial-analysis's
    GET /v1/stage1/vinu-initial-analysis/latest-run/{ticker} (added
    alongside this phase -- RunLog.get_runs(symbol=..., limit=1) already
    supported the query, the route was the only missing piece). Not a
    direct import of RunLog -- vinu-agent and vinu-initial-analysis run in
    separate containers with separate /data mounts in the real deployment,
    so there is no real filesystem path to RunLog's own SQLite file from
    here, HTTP is the only real transport."""

    def __init__(self, base_url: str | None = None, *, timeout: float = 10.0) -> None:
        self._base_url = (
            base_url or _config_module.load_config().services.get(
                "vinu_initial_analysis", "http://localhost:8083"
            )
        ).rstrip("/")
        self._timeout = timeout

    def latest_run_id(self, ticker: str) -> str | None:
        import httpx

        resp = httpx.get(
            f"{self._base_url}/v1/stage1/vinu-initial-analysis/latest-run/{ticker.upper()}",
            timeout=self._timeout,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return data.get("run_id")


@dataclass
class RunLogTriggerResult:
    should_refresh: bool
    new_run_id: str | None = None
    errored: bool = False


class RunLogTrigger:
    """Piece 2: 'is the underlying analysis stale for this ticker.'
    Answers that question only -- refresh_if_stale() is the one place that
    actually invokes the Summary Agent, and it does so at most once per
    call regardless of how many runs were missed (see
    test_multiple_missed_run_ids_trigger_summary_agent_once)."""

    def __init__(
        self,
        run_log_reader: RunLogReader,
        ticker_summary_store: TickerSummaryStore,
        ticker_ledger_store: TickerLedgerStore,
    ) -> None:
        self._reader = run_log_reader
        self._summaries = ticker_summary_store
        self._ledger = ticker_ledger_store

    def check(self, ticker: str) -> RunLogTriggerResult:
        ticker = ticker.upper()
        existing = self._summaries.get_summary(ticker)
        last_seen = existing.source_run_id if existing else ""

        try:
            latest = self._reader.latest_run_id(ticker)
        except Exception as exc:  # noqa: BLE001 -- any transport failure fails closed
            # Fail-closed direction: don't refresh. Logged as a DISTINCT
            # outcome from "genuinely no new run_id" so a real
            # vinu-initial-analysis outage doesn't silently read as
            # "nothing's changing anywhere" -- see 02-guard-rail.md.
            self._ledger.add_event(
                ticker=ticker,
                stage="runlog_trigger",
                event_type="check_failed",
                text=f"RunLog check failed, defaulting to no-refresh: {exc}",
                source="watchlist",
            )
            LOG.warning("RunLog trigger check failed for %s: %s", ticker, exc)
            return RunLogTriggerResult(should_refresh=False, errored=True)

        if not latest or latest == last_seen:
            return RunLogTriggerResult(should_refresh=False, new_run_id=latest)

        return RunLogTriggerResult(should_refresh=True, new_run_id=latest)

    def refresh_if_stale(
        self,
        ticker: str,
        summary_agent_fn: Callable[[str], tuple[str, dict[str, Any]]],
    ) -> RunLogTriggerResult:
        """summary_agent_fn(ticker) -> (summary_text, meta) where meta may
        carry 'angles_with_data'/'angle_count'. Called at most once per
        invocation -- exactly the count check() alone can't enforce, since
        a caller could otherwise call the Summary Agent itself after
        seeing should_refresh=True without going through here."""
        result = self.check(ticker)
        if not result.should_refresh:
            return result

        summary_text, meta = summary_agent_fn(ticker)
        self._summaries.upsert_summary(
            ticker,
            summary_text,
            angles_with_data=int(meta.get("angles_with_data", 0)),
            angle_count=int(meta.get("angle_count", 0)),
            source_run_id=result.new_run_id or "",
        )
        self._ledger.add_event(
            ticker=ticker,
            stage="summary_agent",
            event_type="summary_refreshed",
            text=f"summary refreshed from run {result.new_run_id}",
            ref_id=result.new_run_id or "",
            source="watchlist",
        )
        return result


class ArtifactStatusReader(Protocol):
    def list_artifacts_for_symbol(self, symbol: str) -> list[Any]: ...


def _artifact_signature(strategy_store: ArtifactStatusReader, ticker: str) -> str:
    """A short, order-independent fingerprint of every artifact's
    (artifact_id, status) for this ticker -- changes if and only if an
    artifact was added, removed, or transitioned status. Not a real
    business object, just a comparable snapshot; nothing downstream reads
    the hash itself."""
    artifacts = strategy_store.list_artifacts_for_symbol(ticker)
    parts = sorted(f"{a.artifact_id}:{a.status.value}" for a in artifacts)
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


@dataclass
class GateCheckResult:
    should_run: bool
    run_id_seen: str = ""
    artifact_signature: str = ""
    errored: bool = False


class ChangeGate:
    """Piece 3: 'has anything relevant to the Planner changed for this
    ticker.' Checks TWO independent signals -- TickerSummaryStore's
    source_run_id (the Summary Agent's data) and an artifact-status
    snapshot (via SqliteStrategyStore.list_artifacts_for_symbol) -- either
    one alone can trip a 'yes' (see test_gate_artifact_status_change_alone_
    returns_yes)."""

    def __init__(
        self,
        ticker_summary_store: TickerSummaryStore,
        strategy_store: ArtifactStatusReader,
        ticker_ledger_store: TickerLedgerStore,
    ) -> None:
        self._summaries = ticker_summary_store
        self._strategy_store = strategy_store
        self._ledger = ticker_ledger_store

    def check(self, ticker: str) -> GateCheckResult:
        ticker = ticker.upper()
        existing = self._summaries.get_summary(ticker)
        last_run_id = existing.last_checked_run_id if existing else ""
        last_sig = existing.last_checked_artifact_signature if existing else ""
        current_run_id = existing.source_run_id if existing else ""

        try:
            current_sig = _artifact_signature(self._strategy_store, ticker)
        except Exception as exc:  # noqa: BLE001
            # Fail-closed direction here is the OPPOSITE of RunLogTrigger's,
            # on purpose: skipping on a lookup error risks hiding a real
            # artifact-status change, a correctness risk, not just a cost
            # one -- see 02-guard-rail.md. Signature left as `last_sig`
            # (unchanged) so a later successful lookup that finds nothing
            # actually changed still correctly reports "no".
            self._ledger.add_event(
                ticker=ticker,
                stage="change_gate",
                event_type="lookup_failed",
                text=f"artifact status lookup failed, defaulting to yes: {exc}",
                source="watchlist",
            )
            LOG.warning("Change-gate artifact lookup failed for %s: %s", ticker, exc)
            return GateCheckResult(
                should_run=True, run_id_seen=current_run_id, artifact_signature=last_sig, errored=True
            )

        changed = current_run_id != last_run_id or current_sig != last_sig
        return GateCheckResult(
            should_run=changed, run_id_seen=current_run_id, artifact_signature=current_sig
        )

    def record_pass(self, ticker: str, result: GateCheckResult) -> None:
        """Call after a 'yes' result was actually acted on (Planner ran),
        so an immediate second check on the same, now-unchanged ticker
        returns 'no' -- see test_gate_state_updates_after_a_yes_pass."""
        self._summaries.record_gate_check(
            ticker.upper(), run_id=result.run_id_seen, artifact_signature=result.artifact_signature
        )


def run_gate_cycle(
    tickers: list[str],
    gate: ChangeGate,
    on_yes: Callable[[str, GateCheckResult], None],
) -> None:
    """Reference walk of the watchlist implementing the literal edge the
    design was redrawn to require (mermaid-explanation.md's Loop-
    termination pass): a "no" advances to the NEXT ticker via the loop's
    own `for`, never a re-check of the current one in the same pass. Any
    future real scheduler wiring this in should call this function (or
    keep this exact shape) rather than re-deriving the loop by hand."""
    for ticker in tickers:
        result = gate.check(ticker)
        if not result.should_run:
            continue
        on_yes(ticker, result)
        gate.record_pass(ticker, result)
