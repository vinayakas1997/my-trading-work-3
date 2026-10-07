"""The order description matches what the paper account really returned (tests/fixtures/alpaca_order_lifecycle.json)."""

import json
from pathlib import Path

from vinu_agent.broker.order_config_alpaca import (
    CLOSED_STATUSES, OPEN_STATUSES, RESPONSE_FIELDS, missing_response_fields, observe,
)

FIX = json.loads((Path(__file__).parent / "fixtures" / "alpaca_order_lifecycle.json").read_text(encoding="utf-8"))


def test_the_documented_fields_are_exactly_what_the_broker_returned():
    for key in ("1_submit_response", "2_get_by_id_while_open", "6_get_by_id_after_cancel"):
        assert missing_response_fields(FIX[key]) == []
        assert set(FIX[key]) == set(RESPONSE_FIELDS), set(FIX[key]) ^ set(RESPONSE_FIELDS)


def test_an_order_sent_while_the_market_is_closed_is_open_and_unfilled():
    o = observe(FIX["2_get_by_id_while_open"])
    assert (o.status, o.is_open, o.is_closed) == ("accepted", True, False)
    assert o.filled_qty == 0 and o.filled_avg_price is None and o.closed_at is None and o.problems == ()
    assert o.client_order_id == FIX["client_order_id"] and o.order_id == FIX["1_submit_response"]["id"]


def test_a_cancelled_order_is_closed_with_its_timestamp():
    o = observe(FIX["6_get_by_id_after_cancel"])
    assert (o.status, o.is_open, o.is_closed) == ("canceled", False, True)
    assert o.closed_at and o.problems == ()


def test_inconsistent_responses_are_reported_not_trusted():
    base = dict(FIX["2_get_by_id_while_open"])
    assert any("filled_at is empty" in p for p in observe({**base, "status": "filled", "filled_qty": "1"}).problems)
    assert any("filled_avg_price" in p for p in observe({**base, "status": "filled", "filled_qty": "1", "filled_at": "x"}).problems)
    assert any("unknown status" in p for p in observe({**base, "status": "weird"}).problems)
    assert any("accepted but filled_qty" in p for p in observe({**base, "filled_qty": "1"}).problems)
    ok = observe({**base, "status": "filled", "filled_qty": "1", "filled_at": "t", "filled_avg_price": "779.3"})
    assert ok.is_closed and ok.problems == () and ok.filled_avg_price == 779.3


def test_open_and_closed_status_sets_do_not_overlap():
    assert not OPEN_STATUSES & CLOSED_STATUSES
