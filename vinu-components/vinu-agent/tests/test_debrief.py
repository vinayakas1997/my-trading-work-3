"""Tests for PositionCloseDetector (Piece 2 — debrief-on-close).

Named acceptance test from implementation-plan-from-04/AGENTS.md: confirm the
predicted-vs-actual write actually happens on a real position-close event —
test the actual trigger path (position gone -> exit price fetched -> registry
write), not just that the write function works if called directly.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.broker.alpaca import Position
from vinu_agent.broker.debrief import PositionCloseDetector


def _position(symbol: str, qty: float, avg_entry_price: float) -> Position:
    return Position(
        symbol=symbol, qty=qty, market_value=0.0, cost_basis=0.0,
        unrealized_pl=0.0, unrealized_plpc=0.0, current_price=0.0,
        avg_entry_price=avg_entry_price,
    )


def _stock_price_response(price: float) -> str:
    return json.dumps({"data": [{"close": price}]})


@pytest.fixture
def state_path() -> Path:
    tmp = Path(tempfile.mktemp(suffix=".json"))
    yield tmp
    tmp.unlink(missing_ok=True)


def _detector(state_path: Path, registry: MagicMock, services_config: dict | None = None) -> PositionCloseDetector:
    return PositionCloseDetector(
        registry=registry, state_path=state_path,
        services_config=services_config or {"vinu_research": "http://research-api:8087"},
    )


def test_no_prior_state_just_records_current_positions(state_path: Path):
    registry = MagicMock()
    broker = MagicMock()
    broker.get_positions.return_value = [_position("AAPL", 10, 150.0)]

    detector = _detector(state_path, registry)
    results = detector.check_and_debrief(broker, session_id="s1")

    assert results == []
    saved = json.loads(state_path.read_text())
    assert saved == {"AAPL": {"qty": 10.0, "avg_entry_price": 150.0}}


def test_position_still_open_produces_no_debrief(state_path: Path):
    state_path.write_text(json.dumps({"AAPL": {"qty": 10.0, "avg_entry_price": 150.0}}))
    registry = MagicMock()
    broker = MagicMock()
    broker.get_positions.return_value = [_position("AAPL", 10, 150.0)]

    detector = _detector(state_path, registry)
    results = detector.check_and_debrief(broker, session_id="s1")
    assert results == []


def test_closed_position_with_open_thesis_writes_evidence(state_path: Path):
    state_path.write_text(json.dumps({"JNJ": {"qty": 5.0, "avg_entry_price": 150.0}}))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(160.0)
    broker = MagicMock()
    broker.get_positions.return_value = []

    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {
        "count": 1,
        "hypotheses": [
            {"hypothesis_id": "hyp_1", "status": "testing", "universe": ["JNJ"]},
        ],
    }
    post_resp = MagicMock()
    post_resp.status_code = 200

    detector = _detector(state_path, registry)
    with patch("httpx.get", return_value=get_resp), patch("httpx.post", return_value=post_resp) as mock_post:
        results = detector.check_and_debrief(broker, session_id="s1")

    assert len(results) == 1
    assert results[0]["symbol"] == "JNJ"
    assert results[0]["realized_pnl"] == pytest.approx((160.0 - 150.0) * 5.0)
    assert results[0]["theses_updated"] == 1

    args, kwargs = mock_post.call_args
    assert args[0] == "http://research-api:8087/research/hypotheses/hyp_1/evidence"
    assert kwargs["json"]["metric"] == "realized_pnl"
    assert kwargs["json"]["conclusion"] == "supports"

    saved = json.loads(state_path.read_text())
    assert saved == {}


def test_closed_position_with_loss_marks_contradicts(state_path: Path):
    state_path.write_text(json.dumps({"TSLA": {"qty": 2.0, "avg_entry_price": 300.0}}))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(280.0)
    broker = MagicMock()
    broker.get_positions.return_value = []

    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {
        "count": 1,
        "hypotheses": [{"hypothesis_id": "hyp_2", "status": "exploring", "universe": ["TSLA"]}],
    }
    post_resp = MagicMock()
    post_resp.status_code = 200

    detector = _detector(state_path, registry)
    with patch("httpx.get", return_value=get_resp), patch("httpx.post", return_value=post_resp) as mock_post:
        results = detector.check_and_debrief(broker, session_id="s1")

    assert results[0]["realized_pnl"] < 0
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["conclusion"] == "contradicts"


def test_closed_position_with_no_open_thesis_still_reports_pnl_but_no_write(state_path: Path):
    state_path.write_text(json.dumps({"MSFT": {"qty": 1.0, "avg_entry_price": 400.0}}))
    registry = MagicMock()
    registry.execute.return_value = _stock_price_response(410.0)
    broker = MagicMock()
    broker.get_positions.return_value = []

    get_resp = MagicMock()
    get_resp.status_code = 200
    get_resp.json.return_value = {"count": 0, "hypotheses": []}

    detector = _detector(state_path, registry)
    with patch("httpx.get", return_value=get_resp), patch("httpx.post") as mock_post:
        results = detector.check_and_debrief(broker, session_id="s1")

    assert results[0]["theses_updated"] == 0
    mock_post.assert_not_called()


def test_exit_price_fetch_failure_skips_debrief_but_does_not_raise(state_path: Path):
    state_path.write_text(json.dumps({"AAPL": {"qty": 1.0, "avg_entry_price": 150.0}}))
    registry = MagicMock()
    registry.execute.side_effect = Exception("network down")
    broker = MagicMock()
    broker.get_positions.return_value = []

    detector = _detector(state_path, registry)
    results = detector.check_and_debrief(broker, session_id="s1")
    assert results == []
