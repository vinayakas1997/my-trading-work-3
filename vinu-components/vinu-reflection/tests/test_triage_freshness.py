"""Tests for analysis R (Governance & Freshness) -- is the Planner ever
triaging against silently stale angle data. See
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/05-governance-freshness.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_infra.reflection import ReflectionStore, write_findings
from vinu_agent.storage.ticker_ledger import TickerLedgerStore

from vinu_reflection.reflection import triage_freshness


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _seed(ledger: TickerLedgerStore, *, ticker: str, stale: bool) -> None:
    from vinu_agent.agent.scheduler_workers import TRIAGE_FRESHNESS_FRESH, TRIAGE_FRESHNESS_STALE

    ledger.add_event(
        ticker=ticker, stage="planner_triage",
        event_type=TRIAGE_FRESHNESS_STALE if stale else TRIAGE_FRESHNESS_FRESH,
        text="x",
    )


class TestTriageFreshnessRun:
    def test_no_data_returns_no_findings(self, data_root):
        TickerLedgerStore(data_root / "ticker_ledger.db")
        findings = triage_freshness.run({"vinu_agent": data_root})
        assert findings == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        ledger = TickerLedgerStore(data_root / "ticker_ledger.db")
        for _ in range(10):
            _seed(ledger, ticker="AAPL", stale=False)

        findings = triage_freshness.run({"vinu_agent": data_root})
        assert findings == []

    def test_finds_rising_stale_fraction_system_wide(self, data_root):
        ledger = TickerLedgerStore(data_root / "ticker_ledger.db")
        # Reference window: 60 fresh triages.
        for _ in range(60):
            _seed(ledger, ticker="AAPL", stale=False)
        # Current window: 20 stale triages.
        for _ in range(20):
            _seed(ledger, ticker="MSFT", stale=True)

        findings = triage_freshness.run({"vinu_agent": data_root})
        by_scope = {(f.scope_type, f.scope_key): f for f in findings}
        assert ("system", "triage_freshness") in by_scope
        finding = by_scope[("system", "triage_freshness")]
        assert finding.analyst_name == "triage_freshness"
        assert finding.metric_name == "stale_fraction_trend"
        assert finding.signal_json["stale_fraction"] == pytest.approx(1.0)
        assert finding.signal_json["reference_stale_fraction"] == pytest.approx(0.0)
        assert finding.primary_metric == pytest.approx(1.0)

    def test_unknown_events_excluded_from_trend(self, data_root):
        from vinu_agent.agent.scheduler_workers import TRIAGE_FRESHNESS_UNKNOWN

        ledger = TickerLedgerStore(data_root / "ticker_ledger.db")
        for _ in range(15):
            _seed(ledger, ticker="AAPL", stale=False)
        for _ in range(1000):
            ledger.add_event(ticker="AAPL", stage="planner_triage", event_type=TRIAGE_FRESHNESS_UNKNOWN, text="x")

        findings = triage_freshness.run({"vinu_agent": data_root})
        # Only 15 real fresh/stale events exist -- still below the floor
        # despite 1000 unknown events, proving they aren't folded in.
        assert not any(f.scope_key == "triage_freshness" for f in findings)

    def test_repeat_offender_ticker_flagged(self, data_root):
        ledger = TickerLedgerStore(data_root / "ticker_ledger.db")
        for _ in range(3):
            _seed(ledger, ticker="AAPL", stale=True)
        _seed(ledger, ticker="AAPL", stale=False)
        _seed(ledger, ticker="MSFT", stale=True)  # only 1 -- not a repeat offender

        findings = triage_freshness.run({"vinu_agent": data_root})
        by_scope = {(f.scope_type, f.scope_key): f for f in findings}
        assert ("ticker", "AAPL") in by_scope
        assert ("ticker", "MSFT") not in by_scope
        finding = by_scope[("ticker", "AAPL")]
        assert finding.metric_name == "repeat_stale_triage_count"
        assert finding.signal_json["stale_count"] == 3
        assert finding.signal_json["total_triage_count"] == 4


class TestTriageFreshnessEndToEnd:
    def test_run_write_findings_round_trip(self, data_root):
        ledger = TickerLedgerStore(data_root / "ticker_ledger.db")
        reflection_store = ReflectionStore(data_root / "reflection.db")
        triage_freshness.seed_reference_config(reflection_store)

        for _ in range(60):
            _seed(ledger, ticker="AAPL", stale=False)
        for _ in range(20):
            _seed(ledger, ticker="MSFT", stale=True)

        findings = triage_freshness.run({"vinu_agent": data_root})
        written = write_findings(reflection_store, findings)
        assert len(written) >= 1

        belief = reflection_store.get_belief("triage_freshness", "system", "triage_freshness")
        assert belief is not None
        assert belief["severity"] == "significant"
