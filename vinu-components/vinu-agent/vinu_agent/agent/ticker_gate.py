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
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Protocol

from .. import config as _config_module
from ..storage.ticker_ledger import TickerLedgerStore
from ..storage.ticker_snapshots import TickerSnapshotStore
from ..storage.ticker_summaries import TickerSummaryStore

LOG = logging.getLogger(__name__)


class RunLogReader(Protocol):
    def latest_run_id(self, ticker: str) -> str | None: ...


class AngleCoverageReader(Protocol):
    def coverage(self, ticker: str) -> tuple[int, int]:
        """Returns (angles_with_data, angle_count)."""
        ...


class HttpAngleCoverageReader:
    """Real transport for the angle-coverage gate -- thin wrapper around
    `angles_tool.fetch_full_angle_coverage`, kept as its own class (rather
    than calling the function directly from RunLogTrigger) so tests can
    inject a fake exactly like RunLogReader/HttpRunLogReader above.

    The real starting condition for comprehension (2026-09-23, by
    explicit direction): every one of the 28 real angles must be
    fetchable at EVERY one of its own declared `time_formats`, not just
    `1D` -- this is what Step 13's `angle_synthesizer` now actually
    reads once comprehension runs, so the gate deciding WHEN to start
    has to match what comprehension will actually use, not a narrower
    single-timeframe proxy for it. See missing-pieces-of-system/
    angle-comprehension-hierarchy/01-plan.md Step 14."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url or _config_module.load_config().services.get(
            "vinu_initial_analysis", "http://localhost:8083"
        )

    def coverage(self, ticker: str) -> tuple[int, int]:
        from ..tools.angles_tool import fetch_full_angle_coverage
        return fetch_full_angle_coverage(self._base_url, ticker)


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
        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            _h = _iah() or None
        except Exception:
            _h = None

        resp = httpx.get(
            f"{self._base_url}/v1/stage1/vinu-initial-analysis/latest-run/{ticker.upper()}",
            headers=_h,
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
        ticker_snapshot_store: TickerSnapshotStore | None = None,
        angle_coverage_reader: AngleCoverageReader | None = None,
        min_angle_coverage_fraction: float = 0.0,
        max_angle_coverage_deferrals: int = 3,
    ) -> None:
        self._reader = run_log_reader
        self._summaries = ticker_summary_store
        self._ledger = ticker_ledger_store
        # Optional: None keeps every existing caller/test that constructs a
        # RunLogTrigger without one working unchanged -- the dated snapshot
        # is additive, not a required dependency of this trigger's core job.
        self._snapshots = ticker_snapshot_store
        # Angle-comprehension coverage gate (missing-pieces-of-system/
        # angle-comprehension-hierarchy/): None or fraction<=0.0 ships
        # inert, identical to pre-existing behavior -- a `should_refresh`
        # result fires the Summary Agent (7 real cluster-synthesis LLM
        # calls) the instant it's returned, same as before this gate
        # existed.
        self._angle_coverage_reader = angle_coverage_reader
        self._min_coverage_fraction = min_angle_coverage_fraction
        self._max_coverage_deferrals = max_angle_coverage_deferrals

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

    def _defer_for_low_angle_coverage(
        self, ticker: str, result: RunLogTriggerResult,
    ) -> RunLogTriggerResult | None:
        """Returns a should_refresh=False result if comprehension should
        wait for more angles to finish, or None if it's clear to proceed
        (either coverage is high enough, or this ticker has already been
        deferred `max_angle_coverage_deferrals` times in the last 24h and
        waiting further risks stalling it indefinitely -- e.g. one angle
        that's genuinely broken and will never report data again)."""
        try:
            with_data, total = self._angle_coverage_reader.coverage(ticker)
        except Exception as exc:  # noqa: BLE001 -- fail OPEN: don't let a
            # transport failure on this deterministic pre-check silently
            # block comprehension forever (distinct from check()'s
            # RunLogReader failure above, which fails closed -- there, a
            # failure means "don't even know if anything changed"; here,
            # we already know something changed, and the worse outcome is
            # never comprehending this ticker at all, not comprehending it
            # slightly early).
            LOG.warning("angle coverage check failed for %s, proceeding without it: %s", ticker, exc)
            return None

        fraction = (with_data / total) if total else 1.0
        if fraction >= self._min_coverage_fraction:
            return None

        since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        deferred_recently = self._ledger.count_events(
            ticker, stage="runlog_trigger", event_type="angle_comprehension_deferred", since=since,
        )
        if deferred_recently >= self._max_coverage_deferrals:
            LOG.warning(
                "angle coverage for %s still below threshold after %d deferrals in the last 24h "
                "(%d/%d, %.0f%% < %.0f%% required) -- proceeding anyway rather than stalling "
                "comprehension indefinitely",
                ticker, deferred_recently, with_data, total, fraction * 100, self._min_coverage_fraction * 100,
            )
            return None

        self._ledger.add_event(
            ticker=ticker,
            stage="runlog_trigger",
            event_type="angle_comprehension_deferred",
            text=(
                f"deferring angle comprehension: {with_data}/{total} angles ready "
                f"({fraction:.0%} < {self._min_coverage_fraction:.0%} required)"
            ),
            ref_id=result.new_run_id or "",
            source="watchlist",
        )
        return RunLogTriggerResult(should_refresh=False, new_run_id=result.new_run_id)

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

        if self._angle_coverage_reader is not None and self._min_coverage_fraction > 0.0:
            deferred = self._defer_for_low_angle_coverage(ticker, result)
            if deferred is not None:
                return deferred

        return self._run_and_persist(ticker, summary_agent_fn, result.new_run_id)

    def force_refresh(
        self,
        ticker: str,
        summary_agent_fn: Callable[[str], tuple[str, dict[str, Any]]],
    ) -> RunLogTriggerResult:
        """The manual override for the angle-coverage gate above: run
        comprehension right now, regardless of whether vinu-initial-
        analysis reports a new run_id and regardless of real angle
        coverage. For a human (or another system) who has decided
        waiting isn't worth it for this one ticker right now -- the
        automatic path (refresh_if_stale) is unaffected, still deferring
        by default. Logged as a distinct ledger event type
        (angle_comprehension_forced), never mistaken in the audit trail
        for the automatic 24h-deferral-cap proceed-anyway path."""
        try:
            new_run_id = self._reader.latest_run_id(ticker) or ""
        except Exception as exc:  # noqa: BLE001 -- best-effort: a forced
            # run shouldn't fail just because the run_id lookup itself
            # failed; persist under an empty run_id rather than abort.
            LOG.warning("RunLog lookup failed during forced refresh for %s, proceeding without it: %s", ticker, exc)
            new_run_id = ""

        self._ledger.add_event(
            ticker=ticker,
            stage="runlog_trigger",
            event_type="angle_comprehension_forced",
            text=f"angle comprehension forced (manual override), run_id={new_run_id or 'unknown'}",
            ref_id=new_run_id,
            source="watchlist",
        )
        return self._run_and_persist(ticker, summary_agent_fn, new_run_id)

    def _run_and_persist(
        self,
        ticker: str,
        summary_agent_fn: Callable[[str], tuple[str, dict[str, Any]]],
        new_run_id: str,
    ) -> RunLogTriggerResult:
        summary_text, meta = summary_agent_fn(ticker)
        angles_with_data = int(meta.get("angles_with_data", 0))
        angle_count = int(meta.get("angle_count", 0))
        low_trust = list(meta.get("low_trust_angles") or [])
        angle_digest = meta.get("angle_digest") or {}
        cluster_digest = meta.get("cluster_digest") or {}
        cross_cluster = meta.get("cross_cluster") or {}
        cluster_anomalies = meta.get("cluster_anomalies") or {}
        self._summaries.upsert_summary(
            ticker,
            summary_text,
            angles_with_data=angles_with_data,
            angle_count=angle_count,
            source_run_id=new_run_id or "",
            angle_digest=angle_digest,
            cluster_digest=cluster_digest,
            cross_cluster=cross_cluster,
            cluster_anomalies=cluster_anomalies,
        )
        if self._snapshots is not None:
            try:
                self._snapshots.record_daily_snapshot(
                    ticker,
                    summary=summary_text,
                    angle_digest=angle_digest,
                    angles_with_data=angles_with_data,
                    angle_count=angle_count,
                    source_run_id=new_run_id or "",
                )
            except Exception as exc:  # noqa: BLE001 -- best-effort, never blocks the refresh
                LOG.warning("Daily snapshot write failed for %s: %s", ticker, exc)
        coverage_note = ""
        if angle_count and angles_with_data == 0:
            # A summary with zero grounded angles reads as success
            # downstream (planner triages it like any other). Flag it
            # loudly instead: fail-open for the pipeline, fail-loud in
            # the audit trail.
            coverage_note = " WARNING: 0 angles with data — thin/failed upstream fetch, treat downstream verdicts as provisional"
            LOG.warning(
                "summary for %s has 0/%d angles with data (run %s)%s",
                ticker, angle_count, new_run_id, coverage_note,
            )
        trust_note = ""
        if low_trust:
            # Calibration Tracker overlay (decision 08): low-trust angles
            # named explicitly so future triage/research can see what the
            # summary was told to down-weight.
            trust_note = f" low-trust angles: {','.join(low_trust)}"
        self._ledger.add_event(
            ticker=ticker,
            stage="summary_agent",
            event_type="summary_refreshed",
            text=f"summary refreshed from run {new_run_id} ({angles_with_data}/{angle_count} angles with data){coverage_note}{trust_note}",
            ref_id=new_run_id or "",
            source="watchlist",
        )
        return RunLogTriggerResult(should_refresh=True, new_run_id=new_run_id)


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
