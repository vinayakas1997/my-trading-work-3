"""Tests for TickerSummaryStore -- the durable output of the screener
team's per-ticker angle synthesis. See storage/ticker_summaries.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.storage.ticker_summaries import TickerSummaryStore


@pytest.fixture
def store() -> TickerSummaryStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = TickerSummaryStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


class TestTickerSummaryStore:
    def test_upsert_then_get(self, store: TickerSummaryStore) -> None:
        store.upsert_summary("AAPL", "12 of 28 angles have data...", angles_with_data=12, angle_count=28, source_run_id="run-1")
        fetched = store.get_summary("AAPL")
        assert fetched is not None
        assert fetched.summary == "12 of 28 angles have data..."
        assert fetched.angles_with_data == 12
        assert fetched.angle_count == 28
        assert fetched.source_run_id == "run-1"

    def test_ticker_normalized_to_uppercase(self, store: TickerSummaryStore) -> None:
        store.upsert_summary("aapl", "summary text")
        assert store.get_summary("AAPL") is not None
        assert store.get_summary("aapl") is not None

    def test_get_unknown_ticker_returns_none(self, store: TickerSummaryStore) -> None:
        assert store.get_summary("NOPE") is None

    def test_upsert_overwrites_not_versions(self, store: TickerSummaryStore) -> None:
        """One row per ticker, the latest read -- not a history."""
        store.upsert_summary("AAPL", "first summary", angles_with_data=5)
        store.upsert_summary("AAPL", "second summary", angles_with_data=10)
        fetched = store.get_summary("AAPL")
        assert fetched.summary == "second summary"
        assert fetched.angles_with_data == 10
        assert len(store.list_summaries()) == 1

    def test_created_at_preserved_across_updates(self, store: TickerSummaryStore) -> None:
        first = store.upsert_summary("AAPL", "v1")
        second = store.upsert_summary("AAPL", "v2")
        assert second.created_at == first.created_at
        assert second.updated_at >= first.updated_at

    def test_list_summaries_returns_all(self, store: TickerSummaryStore) -> None:
        store.upsert_summary("AAPL", "a")
        store.upsert_summary("MSFT", "m")
        tickers = {s.ticker for s in store.list_summaries()}
        assert tickers == {"AAPL", "MSFT"}

    def test_record_gate_check_on_existing_row_does_not_touch_summary(
        self, store: TickerSummaryStore
    ) -> None:
        store.upsert_summary("AAPL", "real summary", source_run_id="run-1")
        store.record_gate_check("AAPL", run_id="run-1", artifact_signature="sig-a")
        fetched = store.get_summary("AAPL")
        assert fetched.summary == "real summary"
        assert fetched.source_run_id == "run-1"
        assert fetched.last_checked_run_id == "run-1"
        assert fetched.last_checked_artifact_signature == "sig-a"

    def test_record_gate_check_on_ticker_with_no_summary_yet(
        self, store: TickerSummaryStore
    ) -> None:
        store.record_gate_check("AAPL", run_id="run-1", artifact_signature="sig-a")
        fetched = store.get_summary("AAPL")
        assert fetched is not None
        assert fetched.summary == ""
        assert fetched.last_checked_run_id == "run-1"
        assert fetched.last_checked_artifact_signature == "sig-a"

    def test_record_gate_check_updates_on_repeat_call(
        self, store: TickerSummaryStore
    ) -> None:
        store.record_gate_check("AAPL", run_id="run-1", artifact_signature="sig-a")
        store.record_gate_check("AAPL", run_id="run-2", artifact_signature="sig-b")
        fetched = store.get_summary("AAPL")
        assert fetched.last_checked_run_id == "run-2"
        assert fetched.last_checked_artifact_signature == "sig-b"


class TestAngleDigest:
    """Regression for the '2 of 28 angles' gate-conflict fix: the
    structured per-angle digest must round-trip through storage, and a
    row with no digest (pre-migration / never set) must fail open to {}
    rather than error."""

    def test_angle_digest_round_trips(self, store: TickerSummaryStore) -> None:
        digest = {"trend_lifecycle": {"stage": "mature"}, "regime_analysis": {"regime": "bull"}}
        store.upsert_summary("AAPL", "summary text", angle_digest=digest)
        fetched = store.get_summary("AAPL")
        assert fetched.angle_digest == digest

    def test_no_digest_passed_defaults_to_empty_dict(self, store: TickerSummaryStore) -> None:
        store.upsert_summary("AAPL", "summary text")
        fetched = store.get_summary("AAPL")
        assert fetched.angle_digest == {}

    def test_record_gate_check_on_ticker_with_no_summary_yet_has_empty_digest(
        self, store: TickerSummaryStore
    ) -> None:
        store.record_gate_check("AAPL", run_id="run-1", artifact_signature="sig-a")
        fetched = store.get_summary("AAPL")
        assert fetched.angle_digest == {}


class TestClusterDigestAndCrossCluster:
    """cluster_digest/cross_cluster -- the split-cluster screener
    restructuring's output (7 real per-cluster syntheses + the
    cross_cluster_analyst's ticker-level read). Unlike angle_digest,
    these have no deterministic-Python source -- only real LLM output --
    but round-trip through storage the same way."""

    def test_cluster_digest_round_trips(self, store: TickerSummaryStore) -> None:
        digest = {"B": "4 of 5 models lean up", "D": "regime=bull"}
        store.upsert_summary("AAPL", "summary text", cluster_digest=digest)
        fetched = store.get_summary("AAPL")
        assert fetched.cluster_digest == digest

    def test_cross_cluster_round_trips(self, store: TickerSummaryStore) -> None:
        cross_cluster = {
            "consensus_checks": [{"pair": ["arima", "chronos"], "outcome": "agree"}],
            "corroborations": [{"clusters": ["B", "D"], "why": "both bullish"}],
            "redundant_clusters": ["G"],
        }
        store.upsert_summary("AAPL", "summary text", cross_cluster=cross_cluster)
        fetched = store.get_summary("AAPL")
        assert fetched.cross_cluster == cross_cluster

    def test_no_cluster_digest_passed_defaults_to_empty_dict(self, store: TickerSummaryStore) -> None:
        store.upsert_summary("AAPL", "summary text")
        fetched = store.get_summary("AAPL")
        assert fetched.cluster_digest == {}
        assert fetched.cross_cluster == {}

    def test_record_gate_check_on_ticker_with_no_summary_yet_has_empty_cluster_digest(
        self, store: TickerSummaryStore
    ) -> None:
        store.record_gate_check("AAPL", run_id="run-1", artifact_signature="sig-a")
        fetched = store.get_summary("AAPL")
        assert fetched.cluster_digest == {}
        assert fetched.cross_cluster == {}

    def test_cluster_anomalies_round_trips(self, store: TickerSummaryStore) -> None:
        anomalies = {"E": ["shock_personality.note contains a SYSTEM OVERRIDE instruction"]}
        store.upsert_summary("AAPL", "summary text", cluster_anomalies=anomalies)
        fetched = store.get_summary("AAPL")
        assert fetched.cluster_anomalies == anomalies

    def test_no_cluster_anomalies_passed_defaults_to_empty_dict(self, store: TickerSummaryStore) -> None:
        store.upsert_summary("AAPL", "summary text")
        fetched = store.get_summary("AAPL")
        assert fetched.cluster_anomalies == {}

    def test_cluster_digest_and_cluster_anomalies_coexist_independently(self, store: TickerSummaryStore) -> None:
        """Real regression risk this column pair exists specifically to
        avoid: an anomaly must never get merged into or lost inside the
        digest sentence."""
        store.upsert_summary(
            "AAPL", "summary text",
            cluster_digest={"E": "forces a long signal with 95% confidence"},
            cluster_anomalies={"E": ["SYSTEM OVERRIDE flagged"]},
        )
        fetched = store.get_summary("AAPL")
        assert fetched.cluster_digest == {"E": "forces a long signal with 95% confidence"}
        assert fetched.cluster_anomalies == {"E": ["SYSTEM OVERRIDE flagged"]}

    def test_angle_digest_and_cluster_digest_coexist_independently(self, store: TickerSummaryStore) -> None:
        """Real regression risk with two sibling JSON columns: writing one
        must never clobber or leak into the other."""
        store.upsert_summary(
            "AAPL", "summary text",
            angle_digest={"arima": {"forecast": 189.2}},
            cluster_digest={"A": "arima trending up"},
        )
        fetched = store.get_summary("AAPL")
        assert fetched.angle_digest == {"arima": {"forecast": 189.2}}
        assert fetched.cluster_digest == {"A": "arima trending up"}
