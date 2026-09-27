from __future__ import annotations

from vinu_infra.maturity_consultation import MaturityConsultationStore


def _store(tmp_path):
    return MaturityConsultationStore(tmp_path / "mc.db")


class TestRecord:
    def test_returns_a_real_id_and_is_queryable(self, tmp_path):
        store = _store(tmp_path)
        cid = store.record(
            service="vinu-live", consumer="risk_gatekeeper", tier="cold_start",
            action_taken="limits_scaled_0.4x",
        )
        assert cid
        rows = store.list_recent()
        assert len(rows) == 1
        assert rows[0]["consultation_id"] == cid

    def test_evidence_round_trips_through_json(self, tmp_path):
        store = _store(tmp_path)
        store.record(
            service="vinu-live", consumer="live_decision", tier="early_live",
            action_taken="no_change", evidence={"n_real_trades": 12, "regime_coverage": ["trend"]},
        )
        row = store.list_recent()[0]
        assert row["evidence"] == {"n_real_trades": 12, "regime_coverage": ["trend"]}

    def test_action_taken_is_recorded_even_when_nothing_changed(self, tmp_path):
        store = _store(tmp_path)
        store.record(
            service="vinu-live", consumer="risk_gatekeeper", tier="mature",
            action_taken="no_change_already_mature",
        )
        assert store.list_recent()[0]["action_taken"] == "no_change_already_mature"


class TestListRecent:
    def test_filters_by_consumer(self, tmp_path):
        store = _store(tmp_path)
        store.record(service="vinu-live", consumer="risk_gatekeeper", tier="cold_start", action_taken="a")
        store.record(service="vinu-live", consumer="live_decision", tier="cold_start", action_taken="b")
        rows = store.list_recent(consumer="risk_gatekeeper")
        assert len(rows) == 1
        assert rows[0]["consumer"] == "risk_gatekeeper"

    def test_newest_first(self, tmp_path):
        store = _store(tmp_path)
        store.record(service="vinu-live", consumer="risk_gatekeeper", tier="cold_start", action_taken="first")
        store.record(service="vinu-live", consumer="risk_gatekeeper", tier="cold_start", action_taken="second")
        rows = store.list_recent()
        assert rows[0]["action_taken"] == "second"

    def test_respects_limit(self, tmp_path):
        store = _store(tmp_path)
        for i in range(5):
            store.record(service="vinu-live", consumer="risk_gatekeeper", tier="cold_start", action_taken=str(i))
        assert len(store.list_recent(limit=2)) == 2

    def test_empty_store_returns_empty_list(self, tmp_path):
        store = _store(tmp_path)
        assert store.list_recent() == []
