"""Tests for PositionCloseDetector (Piece 2 — debrief-on-close).

Named acceptance test from implementation-plan-from-04/AGENTS.md: confirm the
predicted-vs-actual write actually happens on a real position-close event —
test the actual trigger path (position gone -> exit price fetched -> registry
write), not just that the write function works if called directly.

Covers both detection tiers: the primary fill-replay path (a filled sell
order's own order_id is the close/dedup identity) and the snapshot-diff
fallback for closes the fetched order lookback window didn't cover.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.broker.alpaca import Order, Position
from vinu_agent.broker.debrief import PositionCloseDetector
from vinu_research.models import Hypothesis, HypothesisStatus
from vinu_research.hypothesis_registry import HypothesisRegistry


def _position(symbol: str, qty: float, avg_entry_price: float) -> Position:
    return Position(
        symbol=symbol, qty=qty, market_value=0.0, cost_basis=0.0,
        unrealized_pl=0.0, unrealized_plpc=0.0, current_price=0.0,
        avg_entry_price=avg_entry_price,
    )


def _order(
    order_id: str, symbol: str, side: str, qty: float, fill_price: float,
    updated_at: str = "2026-01-01T00:00:00Z", status: str = "filled",
) -> Order:
    return Order(
        order_id=order_id, symbol=symbol, side=side, type="market", status=status,
        qty=qty, filled_qty=qty, limit_price=None, stop_price=None,
        created_at=updated_at, updated_at=updated_at, filled_avg_price=fill_price,
    )


def _stock_price_response(price: float) -> str:
    return json.dumps({"data": [{"close": price}]})


@pytest.fixture
def state_path() -> Path:
    tmp = Path(tempfile.mktemp(suffix=".json"))
    yield tmp
    tmp.unlink(missing_ok=True)


@pytest.fixture
def hypothesis_registry() -> HypothesisRegistry:
    """Since 0002 (see New-talk-agents/implementation/00-status.md), the
    debrief evidence write goes straight to vinu-research's real
    HypothesisRegistry in-process -- a real, tempfile-backed registry here,
    not a mocked HTTP response envelope."""
    tmp = Path(tempfile.mktemp(suffix=".json"))
    reg = HypothesisRegistry(path=tmp)
    yield reg
    tmp.unlink(missing_ok=True)


def _detector(state_path: Path, registry: MagicMock) -> PositionCloseDetector:
    return PositionCloseDetector(registry=registry, state_path=state_path)


def _broker(positions: list[Position], orders: list[Order] | None = None) -> MagicMock:
    broker = MagicMock()
    broker.get_positions.return_value = positions
    broker.get_orders.return_value = orders or []
    return broker


# --- no-op / still-open ------------------------------------------------------


def test_no_prior_state_just_records_current_positions(state_path: Path):
    registry = MagicMock()
    broker = _broker([_position("AAPL", 10, 150.0)])

    detector = _detector(state_path, registry)
    results = detector.check_and_debrief(broker, session_id="s1")

    assert results == []
    saved = json.loads(state_path.read_text())
    assert saved["positions"] == {"AAPL": {"qty": 10.0, "avg_entry_price": 150.0}}


def test_position_still_open_produces_no_debrief(state_path: Path):
    state_path.write_text(json.dumps({"AAPL": {"qty": 10.0, "avg_entry_price": 150.0}}))
    registry = MagicMock()
    broker = _broker([_position("AAPL", 10, 150.0)])

    detector = _detector(state_path, registry)
    results = detector.check_and_debrief(broker, session_id="s1")
    assert results == []


# --- fallback tier: snapshot diff, no matching fill in the order window -----


def test_closed_position_with_open_thesis_writes_evidence(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    state_path.write_text(json.dumps({"JNJ": {"qty": 5.0, "avg_entry_price": 150.0}}))
    hypothesis_registry.create(Hypothesis(
        hypothesis_id="hyp_1", title="t", thesis="t",
        status=HypothesisStatus.testing, universe=["JNJ"],
    ))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(160.0)
    broker = _broker([])

    detector = _detector(state_path, registry)
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        results = detector.check_and_debrief(broker, session_id="s1")

    assert len(results) == 1
    assert results[0]["symbol"] == "JNJ"
    assert results[0]["realized_pnl"] == pytest.approx((160.0 - 150.0) * 5.0)
    assert results[0]["theses_updated"] == 1

    updated = hypothesis_registry.get("hyp_1")
    assert updated is not None
    assert len(updated.evidence) == 1
    assert updated.evidence[0].metric == "realized_pnl"
    assert updated.evidence[0].conclusion == "supports"

    saved = json.loads(state_path.read_text())
    assert saved["positions"] == {}


def test_closed_position_with_loss_marks_contradicts(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    state_path.write_text(json.dumps({"TSLA": {"qty": 2.0, "avg_entry_price": 300.0}}))
    hypothesis_registry.create(Hypothesis(
        hypothesis_id="hyp_2", title="t", thesis="t",
        status=HypothesisStatus.exploring, universe=["TSLA"],
    ))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(280.0)
    broker = _broker([])

    detector = _detector(state_path, registry)
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        results = detector.check_and_debrief(broker, session_id="s1")

    assert results[0]["realized_pnl"] < 0
    updated = hypothesis_registry.get("hyp_2")
    assert updated.evidence[0].conclusion == "contradicts"


def test_closed_position_with_no_open_thesis_still_reports_pnl_but_no_write(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    state_path.write_text(json.dumps({"MSFT": {"qty": 1.0, "avg_entry_price": 400.0}}))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(410.0)
    broker = _broker([])

    detector = _detector(state_path, registry)
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        results = detector.check_and_debrief(broker, session_id="s1")

    assert results[0]["theses_updated"] == 0
    assert hypothesis_registry.count() == 0


def test_contradicting_close_writes_significance_ledger_event(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    """significance_triage.py's detect_thesis_contradiction_pattern reads
    this event -- proves the write actually happens, not just that
    conclusion="contradicts" gets computed."""
    state_path.write_text(json.dumps({"TSLA": {"qty": 2.0, "avg_entry_price": 300.0}}))
    hypothesis_registry.create(Hypothesis(
        hypothesis_id="hyp_6", title="t", thesis="t",
        status=HypothesisStatus.exploring, universe=["TSLA"],
    ))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(280.0)
    broker = _broker([])
    ticker_ledger_store = MagicMock()

    detector = PositionCloseDetector(
        registry=registry, state_path=state_path, ticker_ledger_store=ticker_ledger_store,
    )
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        detector.check_and_debrief(broker, session_id="s1")

    ticker_ledger_store.add_event.assert_called_once()
    _, kwargs = ticker_ledger_store.add_event.call_args
    assert kwargs["ticker"] == "TSLA"
    assert kwargs["stage"] == "debrief"
    assert kwargs["event_type"] == "thesis_contradicted"
    assert kwargs["ref_id"] == "hyp_6"


def test_supporting_close_does_not_write_contradiction_ledger_event(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    state_path.write_text(json.dumps({"JNJ": {"qty": 5.0, "avg_entry_price": 150.0}}))
    hypothesis_registry.create(Hypothesis(
        hypothesis_id="hyp_7", title="t", thesis="t",
        status=HypothesisStatus.testing, universe=["JNJ"],
    ))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(160.0)
    broker = _broker([])
    ticker_ledger_store = MagicMock()

    detector = PositionCloseDetector(
        registry=registry, state_path=state_path, ticker_ledger_store=ticker_ledger_store,
    )
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        detector.check_and_debrief(broker, session_id="s1")

    ticker_ledger_store.add_event.assert_not_called()


def test_contradiction_with_no_open_thesis_does_not_write_ledger_event(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    """No thesis_ids at all -- nothing for the close to have contradicted,
    matching the existing no-write-to-HypothesisRegistry behavior."""
    state_path.write_text(json.dumps({"MSFT": {"qty": 1.0, "avg_entry_price": 400.0}}))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(390.0)
    broker = _broker([])
    ticker_ledger_store = MagicMock()

    detector = PositionCloseDetector(
        registry=registry, state_path=state_path, ticker_ledger_store=ticker_ledger_store,
    )
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        detector.check_and_debrief(broker, session_id="s1")

    ticker_ledger_store.add_event.assert_not_called()


def test_ledger_write_failure_does_not_prevent_debrief_result(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    state_path.write_text(json.dumps({"TSLA": {"qty": 2.0, "avg_entry_price": 300.0}}))
    hypothesis_registry.create(Hypothesis(
        hypothesis_id="hyp_8", title="t", thesis="t",
        status=HypothesisStatus.exploring, universe=["TSLA"],
    ))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(280.0)
    broker = _broker([])
    ticker_ledger_store = MagicMock()
    ticker_ledger_store.add_event.side_effect = Exception("db down")

    detector = PositionCloseDetector(
        registry=registry, state_path=state_path, ticker_ledger_store=ticker_ledger_store,
    )
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        results = detector.check_and_debrief(broker, session_id="s1")

    assert len(results) == 1
    assert results[0]["symbol"] == "TSLA"


def test_exit_price_fetch_failure_skips_debrief_but_does_not_raise(state_path: Path):
    state_path.write_text(json.dumps({"AAPL": {"qty": 1.0, "avg_entry_price": 150.0}}))
    registry = MagicMock()
    registry.execute.side_effect = Exception("network down")
    broker = _broker([])

    detector = _detector(state_path, registry)
    results = detector.check_and_debrief(broker, session_id="s1")
    assert results == []


# --- primary tier: fill replay -----------------------------------------------


def test_open_and_close_within_one_poll_is_still_detected(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    """The scenario a pure snapshot diff can never see: no prior state (we
    never held GME before this poll), broker.get_positions() shows it flat
    right now too -- but the order history shows a buy and a sell both
    happened since the last poll. Only visible via the fill replay tier."""
    hypothesis_registry.create(Hypothesis(
        hypothesis_id="hyp_3", title="t", thesis="t",
        status=HypothesisStatus.testing, universe=["GME"],
    ))
    registry = MagicMock()
    broker = _broker([], orders=[
        _order("ord_buy_1", "GME", "buy", 4, 20.0, updated_at="2026-01-01T00:00:01Z"),
        _order("ord_sell_1", "GME", "sell", 4, 25.0, updated_at="2026-01-01T00:00:02Z"),
    ])

    detector = _detector(state_path, registry)
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        results = detector.check_and_debrief(broker, session_id="s1")

    assert len(results) == 1
    assert results[0]["symbol"] == "GME"
    assert results[0]["realized_pnl"] == pytest.approx((25.0 - 20.0) * 4)

    saved = json.loads(state_path.read_text())
    assert saved["positions"] == {}
    assert "ord_sell_1" in saved["processed_order_ids"]


def test_fill_replay_dedups_on_order_id_not_reprocessed_next_poll(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    """A retried/overlapping poll re-fetching the same closed order must not
    write the evidence a second time -- the whole point of keying dedup on
    the broker's own order_id instead of just symbol presence."""
    hypothesis_registry.create(Hypothesis(
        hypothesis_id="hyp_4", title="t", thesis="t",
        status=HypothesisStatus.testing, universe=["NFLX"],
    ))
    registry = MagicMock()
    orders = [
        _order("ord_buy_2", "NFLX", "buy", 1, 500.0, updated_at="2026-01-01T00:00:01Z"),
        _order("ord_sell_2", "NFLX", "sell", 1, 510.0, updated_at="2026-01-01T00:00:02Z"),
    ]
    broker = _broker([], orders=orders)

    detector = _detector(state_path, registry)
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        first = detector.check_and_debrief(broker, session_id="s1")
        # Same broker, same orders still returned (as a real "closed" query
        # would keep returning them for a while) -- second poll must be a
        # no-op for this order.
        second = detector.check_and_debrief(broker, session_id="s1")

    assert len(first) == 1
    assert second == []
    updated = hypothesis_registry.get("hyp_4")
    assert len(updated.evidence) == 1


def test_broker_positions_win_over_replay_for_still_held_symbol(state_path: Path):
    """If the replay's own bookkeeping ever drifts from the broker's real
    current holdings (fills outside the lookback window, manual trades),
    the broker's get_positions() is authoritative -- not the replay guess."""
    registry = MagicMock()
    broker = _broker(
        [_position("IBM", 3, 140.0)],
        orders=[_order("ord_buy_3", "IBM", "buy", 1, 130.0, updated_at="2026-01-01T00:00:01Z")],
    )

    detector = _detector(state_path, registry)
    results = detector.check_and_debrief(broker, session_id="s1")

    assert results == []
    saved = json.loads(state_path.read_text())
    assert saved["positions"] == {"IBM": {"qty": 3.0, "avg_entry_price": 140.0}}


def test_get_orders_failure_falls_back_to_snapshot_diff_only(
    state_path: Path, hypothesis_registry: HypothesisRegistry,
) -> None:
    """If the order-history call itself fails (API hiccup), detection
    degrades to the old snapshot-diff behavior rather than raising or
    silently detecting nothing at all."""
    state_path.write_text(json.dumps({"PFE": {"qty": 2.0, "avg_entry_price": 40.0}}))
    hypothesis_registry.create(Hypothesis(
        hypothesis_id="hyp_5", title="t", thesis="t",
        status=HypothesisStatus.testing, universe=["PFE"],
    ))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(45.0)
    broker = MagicMock()
    broker.get_positions.return_value = []
    broker.get_orders.side_effect = Exception("orders API down")

    detector = _detector(state_path, registry)
    with patch(
        "vinu_agent.broker.research_link.get_hypothesis_registry",
        return_value=hypothesis_registry,
    ):
        results = detector.check_and_debrief(broker, session_id="s1")

    assert len(results) == 1
    assert results[0]["symbol"] == "PFE"
