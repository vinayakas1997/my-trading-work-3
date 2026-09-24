"""Tests for SignalEvidenceStore -- Phase 2 of the must-condition +
supporting-indicator evidence design
(missing-pieces-of-system/new-theory-of-trading/01-planning.md,
Decisions 1, 2, 3, 7, 8)."""

from __future__ import annotations

from vinu_research.storage.signal_evidence_store import SignalEvidenceStore

_INDICATORS = {
    "shock_personality": {
        "status": "ok",
        "gap_fill_rate": 0.62,
        "vol_persistence": 0.31,
        "n_shocks": 14,
    },
    "chronos": {
        "status": "ok",
        "model_backend": "pretrained",
        "checkpoint": "amazon/chronos-t5-large",
        "median_forecast": [101.2, 101.5, 101.9, 102.1, 102.4],
        "p10_forecast": [100.1, 100.0, 99.8, 99.5, 99.2],
        "p90_forecast": [102.3, 103.0, 104.0, 104.7, 105.6],
    },
    "adx": 17.8,
}


def _store(tmp_path):
    return SignalEvidenceStore(tmp_path / "signal_evidence.db")


class TestRecordTrigger:
    def test_round_trip_preserves_heterogeneous_indicator_shapes(self, tmp_path):
        store = _store(tmp_path)
        store.record_trigger(
            "t-001", "AAPL", "2026-09-24T14:30:00+00:00",
            "sma5_cross_sma50", _INDICATORS,
            granularity="15min", policy_version="abc123",
        )
        row = store.get_trigger("t-001")
        assert row is not None
        assert row["symbol"] == "AAPL"
        assert row["granularity"] == "15min"
        assert row["policy_version"] == "abc123"
        assert row["must_condition"] == ["sma5_cross_sma50"]
        # No flattening anywhere -- each indicator's own natural shape
        # (a flat dict, a dict with nested lists, or a bare scalar) comes
        # back exactly as given, per Decision 3.
        assert row["indicators"]["shock_personality"] == _INDICATORS["shock_personality"]
        assert row["indicators"]["chronos"]["median_forecast"] == [101.2, 101.5, 101.9, 102.1, 102.4]
        assert row["indicators"]["adx"] == 17.8

    def test_multiple_must_conditions_stored_as_list(self, tmp_path):
        store = _store(tmp_path)
        store.record_trigger(
            "t-002", "MSFT", "2026-09-24T15:00:00+00:00",
            ["sma5_cross_sma50", "price_above_sma200"], {"adx": 21.0},
        )
        row = store.get_trigger("t-002")
        assert row["must_condition"] == ["sma5_cross_sma50", "price_above_sma200"]

    def test_outcome_fields_null_until_recorded(self, tmp_path):
        store = _store(tmp_path)
        store.record_trigger("t-003", "AAPL", "2026-09-24T14:30:00+00:00", "x", {"adx": 20.0})
        row = store.get_trigger("t-003")
        assert row["max_favorable_excursion"] is None
        assert row["max_adverse_excursion"] is None
        assert row["return_at_horizon"] is None
        assert row["outcome_recorded_at"] is None

    def test_unknown_trigger_id_returns_none(self, tmp_path):
        store = _store(tmp_path)
        assert store.get_trigger("does-not-exist") is None


class TestRecordOutcome:
    def test_outcome_fills_in_after_trigger(self, tmp_path):
        store = _store(tmp_path)
        store.record_trigger("t-004", "AAPL", "2026-09-24T14:30:00+00:00", "x", {"adx": 20.0})
        store.record_outcome(
            "t-004",
            max_favorable_excursion=0.031,
            max_adverse_excursion=-0.012,
            return_at_horizon=0.024,
        )
        row = store.get_trigger("t-004")
        assert row["max_favorable_excursion"] == 0.031
        assert row["max_adverse_excursion"] == -0.012
        assert row["return_at_horizon"] == 0.024
        assert row["outcome_recorded_at"] is not None

    def test_recording_outcome_twice_overwrites_not_errors(self, tmp_path):
        """Decision 1: the outcome horizon can be revisited without
        needing to re-record the trigger -- record_outcome must be safe
        to call again for the same trigger_id."""
        store = _store(tmp_path)
        store.record_trigger("t-005", "AAPL", "2026-09-24T14:30:00+00:00", "x", {"adx": 20.0})
        store.record_outcome("t-005", max_favorable_excursion=0.01, max_adverse_excursion=-0.01, return_at_horizon=0.005)
        store.record_outcome("t-005", max_favorable_excursion=0.05, max_adverse_excursion=-0.02, return_at_horizon=0.03)
        row = store.get_trigger("t-005")
        assert row["return_at_horizon"] == 0.03


class TestListingAndQuerying:
    def test_list_triggers_filters_by_symbol_and_orders_newest_first(self, tmp_path):
        store = _store(tmp_path)
        store.record_trigger("t-a", "AAPL", "2026-09-24T09:00:00+00:00", "x", {})
        store.record_trigger("t-b", "AAPL", "2026-09-24T10:00:00+00:00", "x", {})
        store.record_trigger("t-c", "MSFT", "2026-09-24T11:00:00+00:00", "x", {})

        aapl_rows = store.list_triggers(symbol="AAPL")
        assert [r["trigger_id"] for r in aapl_rows] == ["t-b", "t-a"]

    def test_list_triggers_does_not_include_indicators(self, tmp_path):
        store = _store(tmp_path)
        store.record_trigger("t-x", "AAPL", "2026-09-24T09:00:00+00:00", "x", {"adx": 20.0})
        rows = store.list_triggers(symbol="AAPL")
        assert "indicators" not in rows[0]

    def test_get_unresolved_triggers_only_returns_outcome_pending_rows(self, tmp_path):
        store = _store(tmp_path)
        store.record_trigger("t-old", "AAPL", "2026-09-01T00:00:00+00:00", "x", {})
        store.record_trigger("t-new", "AAPL", "2026-09-24T00:00:00+00:00", "x", {})
        store.record_outcome("t-new", max_favorable_excursion=0.01, max_adverse_excursion=-0.01, return_at_horizon=0.0)

        unresolved = store.get_unresolved_triggers("2026-09-24T23:59:59+00:00")
        ids = {r["trigger_id"] for r in unresolved}
        assert "t-old" in ids
        assert "t-new" not in ids

    def test_get_unresolved_triggers_respects_cutoff(self, tmp_path):
        store = _store(tmp_path)
        store.record_trigger("t-future", "AAPL", "2026-12-01T00:00:00+00:00", "x", {})
        unresolved = store.get_unresolved_triggers("2026-09-24T00:00:00+00:00")
        assert unresolved == []
