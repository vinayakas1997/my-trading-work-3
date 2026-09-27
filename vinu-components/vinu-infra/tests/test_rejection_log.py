from __future__ import annotations

from vinu_infra.rejection_log import RejectionRecord, record_rejection


def test_builds_the_full_shape_with_defaults() -> None:
    rec = record_rejection(
        "screener_symbol", "AAPL", "hard_filter", "hard_filter_bound",
        "price=3.2 < min_price=5.0",
    )
    assert rec.entity_type == "screener_symbol"
    assert rec.entity_id == "AAPL"
    assert rec.stage == "hard_filter"
    assert rec.rejection_category == "hard_filter_bound"
    assert rec.rejection_detail == "price=3.2 < min_price=5.0"
    assert rec.compared_against_id is None
    assert rec.timestamp  # a real ISO-8601 UTC string, not empty


def test_timestamp_defaults_to_utc_iso8601() -> None:
    rec = record_rejection("sweep_run", "run-1", "comparison", "worse_sharpe", "sharpe 0.4 < winner 1.1")
    assert "+00:00" in rec.timestamp or rec.timestamp.endswith("Z")


def test_compared_against_id_and_explicit_timestamp_are_passed_through() -> None:
    rec = record_rejection(
        "generation_candidate", "cand-2", "generation", "complexity_penalty", "score 0.3",
        compared_against_id="cand-1", timestamp="2026-01-01T00:00:00+00:00",
    )
    assert rec.compared_against_id == "cand-1"
    assert rec.timestamp == "2026-01-01T00:00:00+00:00"


def test_to_dict_round_trips_every_field() -> None:
    rec = record_rejection(
        "screener_symbol", "MSFT", "risk_veto", "risk_veto", "high_risk_flag",
        compared_against_id=None, timestamp="2026-01-01T00:00:00+00:00",
    )
    assert rec.to_dict() == {
        "entity_type": "screener_symbol",
        "entity_id": "MSFT",
        "stage": "risk_veto",
        "rejection_category": "risk_veto",
        "rejection_detail": "high_risk_flag",
        "compared_against_id": None,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }


def test_entity_type_is_not_a_closed_enum() -> None:
    """A future consumer can use a new entity_type without this module
    changing first -- deliberately not validated against a closed set."""
    rec = record_rejection("some_new_entity_kind", "x", "stage", "cat", "detail")
    assert rec.entity_type == "some_new_entity_kind"


def test_is_frozen() -> None:
    rec = RejectionRecord("t", "id", "s", "c", "d")
    try:
        rec.entity_id = "other"  # type: ignore[misc]
        assert False, "expected FrozenInstanceError"
    except Exception:
        pass
