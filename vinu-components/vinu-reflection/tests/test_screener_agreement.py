"""Tests for analyses I and X (screener ranker / rule agreement with the
main pipeline)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vinu_agent.agent.thesis_intake_gate import CANDIDATE_PROPOSED_EVENT_TYPE
from vinu_agent.storage.ticker_ledger import TickerLedgerStore
from vinu_screener.audit.watch_history import WatchAuditStore
from vinu_screener.rankers.churn import ChurnEvent, RankerChurnStore
from vinu_screener.rankers.config import HardFilterConfig, RankerConfig
from vinu_screener.rankers.store import RankerStore

from vinu_reflection.reflection import screener_agreement


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _propose_candidate(ticker_ledger: TickerLedgerStore, symbol: str, at: float) -> None:
    # add_event() always timestamps with "now" -- these tests need
    # specific historical timestamps to land inside/outside the
    # agreement window, so write the row directly instead.
    ts = datetime.fromtimestamp(at, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ticker_ledger.upsert(
        "ticker_ledger",
        {
            "ledger_id": f"led_{symbol}_{at}",
            "ticker": symbol.upper(),
            "timestamp": ts,
            "stage": "planner",
            "event_type": CANDIDATE_PROPOSED_EVENT_TYPE,
            "text": "proposed",
            "ref_id": "",
            "source": "test",
        },
        conflict_columns=["ledger_id"],
    )


def _seed_ranker(ranker_store: RankerStore, ranker_id: str) -> None:
    ranker_store.upsert_ranker(
        RankerConfig(
            ranker_id=ranker_id, universe=("AAPL", "MSFT"), factors=(), top_n=20,
            hard_filter=HardFilterConfig(),
        )
    )


class TestScreenerAgreementRun:
    def test_no_data_returns_no_findings(self, data_root):
        RankerStore(str(data_root / "screener" / "screener_rankers.db"))
        RankerChurnStore(str(data_root / "screener" / "screener_ranker_churn.db"))
        WatchAuditStore(str(data_root / "screener" / "screener_audit.db"))
        TickerLedgerStore(data_root / "agent" / "ticker_ledger.db")
        findings = screener_agreement.run(
            {"vinu_screener": data_root / "screener", "vinu_agent": data_root / "agent"}
        )
        assert findings == []

    def test_ranker_agreement_drop_is_flagged(self, data_root):
        ranker_store = RankerStore(str(data_root / "screener" / "screener_rankers.db"))
        churn_store = RankerChurnStore(str(data_root / "screener" / "screener_ranker_churn.db"))
        ticker_ledger = TickerLedgerStore(data_root / "agent" / "ticker_ledger.db")
        _seed_ranker(ranker_store, "core_starter")

        now = time.time()
        events = []
        # 30 reference "entered" events, all agreed (pipeline proposed too).
        for i in range(30):
            at = now - 100_000 + i * 100
            events.append(ChurnEvent("core_starter", f"REF{i}", "entered", at, to_rank=1))
            _propose_candidate(ticker_ledger, f"REF{i}", at)
        # 10 recent "entered" events, none agreed.
        for i in range(10):
            at = now - 1000 + i * 10
            events.append(ChurnEvent("core_starter", f"CUR{i}", "entered", at, to_rank=1))
        churn_store.record(events)

        findings = screener_agreement.run(
            {"vinu_screener": data_root / "screener", "vinu_agent": data_root / "agent"}
        )
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_key == "core_starter"
        assert finding.metric_name == "agreement_rate"
        assert finding.primary_metric == pytest.approx(-1.0)  # 0% vs 100%
        assert finding.psi > 0.25

    def test_rule_fire_agreement_evaluated_independently(self, data_root):
        RankerStore(str(data_root / "screener" / "screener_rankers.db"))
        RankerChurnStore(str(data_root / "screener" / "screener_ranker_churn.db"))
        watch_store = WatchAuditStore(str(data_root / "screener" / "screener_audit.db"))
        ticker_ledger = TickerLedgerStore(data_root / "agent" / "ticker_ledger.db")

        now = time.time()
        for i in range(30):
            at = now - 100_000 + i * 100
            watch_store.record_fire("breakout_rule", f"REF{i}", now=at)
            _propose_candidate(ticker_ledger, f"REF{i}", at)
        for i in range(10):
            at = now - 1000 + i * 10
            watch_store.record_fire("breakout_rule", f"CUR{i}", now=at)

        findings = screener_agreement.run(
            {"vinu_screener": data_root / "screener", "vinu_agent": data_root / "agent"}
        )
        assert len(findings) == 1
        assert findings[0].scope_key == "breakout_rule"
        assert findings[0].primary_metric == pytest.approx(-1.0)

    def test_below_evidence_minimum_is_skipped(self, data_root):
        ranker_store = RankerStore(str(data_root / "screener" / "screener_rankers.db"))
        churn_store = RankerChurnStore(str(data_root / "screener" / "screener_ranker_churn.db"))
        WatchAuditStore(str(data_root / "screener" / "screener_audit.db"))
        TickerLedgerStore(data_root / "agent" / "ticker_ledger.db")
        _seed_ranker(ranker_store, "core_starter")

        now = time.time()
        churn_store.record(
            [ChurnEvent("core_starter", f"SYM{i}", "entered", now + i) for i in range(5)]
        )

        findings = screener_agreement.run(
            {"vinu_screener": data_root / "screener", "vinu_agent": data_root / "agent"}
        )
        assert findings == []
