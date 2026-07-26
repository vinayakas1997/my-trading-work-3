import os
import tempfile
import pytest
from vinu_live.book import (
    init_book,
    open_position,
    add_to_position,
    reduce_position,
    close_position,
    get_position,
    list_open_positions,
    list_closed_positions,
    mark_feedback_processed,
    per_symbol_exposure,
    portfolio_total_exposure,
    exposure_summary,
    Position,
)


@pytest.fixture
def book():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    be = init_book(db_path)
    yield be
    be.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_open_position(book):
    pos = open_position(book, "AAPL", "buy", 100, 150.0)
    assert pos is not None
    assert pos.symbol == "AAPL"
    assert pos.side == "long"
    assert pos.qty == 100
    assert pos.avg_entry == 150.0
    assert pos.is_open


def test_open_short_position(book):
    pos = open_position(book, "AAPL", "sell", 50, 150.0)
    assert pos is not None
    assert pos.side == "short"
    assert pos.qty == 50


def test_open_position_invalid_side(book):
    pos = open_position(book, "AAPL", "invalid", 100, 150.0)
    assert pos is None


def test_add_to_position(book):
    pos = open_position(book, "AAPL", "buy", 100, 150.0)
    assert pos is not None
    updated = add_to_position(book, pos.position_id, 50, 160.0)
    assert updated is not None
    assert updated.qty == 150
    expected_avg = (100 * 150 + 50 * 160) / 150
    assert abs(updated.avg_entry - expected_avg) < 0.001


def test_add_to_position_nonexistent(book):
    result = add_to_position(book, "nonexistent", 50, 150.0)
    assert result is None


def test_reduce_position(book):
    pos = open_position(book, "AAPL", "buy", 100, 150.0)
    assert pos is not None
    updated = reduce_position(book, pos.position_id, 30, 155.0)
    assert updated is not None
    assert updated.qty == 70
    assert updated.realized_pnl == (155.0 - 150.0) * 30


def test_reduce_position_full_close(book):
    pos = open_position(book, "AAPL", "buy", 100, 150.0)
    assert pos is not None
    result = reduce_position(book, pos.position_id, 100, 155.0)
    assert result is None  # position closed
    assert get_position(book, pos.position_id) is None


def test_reduce_position_short(book):
    pos = open_position(book, "AAPL", "sell", 100, 150.0)
    assert pos is not None
    updated = reduce_position(book, pos.position_id, 30, 145.0)
    assert updated is not None
    assert updated.qty == 70
    assert updated.realized_pnl == (150.0 - 145.0) * 30


def test_close_position(book):
    pos = open_position(book, "AAPL", "buy", 100, 150.0)
    assert pos is not None
    closed = close_position(book, pos.position_id, 160.0)
    assert closed is not None
    assert get_position(book, pos.position_id) is None


def test_list_open_positions(book):
    open_position(book, "AAPL", "buy", 100, 150.0)
    open_position(book, "GOOGL", "buy", 50, 200.0)
    positions = list_open_positions(book)
    assert len(positions) == 2


def test_list_open_positions_filtered(book):
    open_position(book, "AAPL", "buy", 100, 150.0)
    open_position(book, "GOOGL", "buy", 50, 200.0)
    positions = list_open_positions(book, symbol="AAPL")
    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"


def test_get_position(book):
    pos = open_position(book, "AAPL", "buy", 100, 150.0)
    assert pos is not None
    retrieved = get_position(book, pos.position_id)
    assert retrieved is not None
    assert retrieved.position_id == pos.position_id


def test_per_symbol_exposure(book):
    pos1 = open_position(book, "AAPL", "buy", 100, 150.0)
    pos2 = open_position(book, "GOOGL", "buy", 50, 200.0)
    assert pos1 is not None and pos2 is not None
    prices = {"AAPL": 155.0, "GOOGL": 210.0}
    exposure = per_symbol_exposure(
        [p for p in [pos1, pos2] if p is not None],
        prices,
    )
    assert abs(exposure["AAPL"] - 100 * 155.0) < 0.01
    assert abs(exposure["GOOGL"] - 50 * 210.0) < 0.01


def test_portfolio_total_exposure(book):
    pos1 = open_position(book, "AAPL", "buy", 100, 150.0)
    pos2 = open_position(book, "GOOGL", "buy", 50, 200.0)
    assert pos1 is not None and pos2 is not None
    prices = {"AAPL": 155.0, "GOOGL": 210.0}
    total = portfolio_total_exposure(
        [p for p in [pos1, pos2] if p is not None],
        prices,
    )
    expected = 100 * 155.0 + 50 * 210.0
    assert abs(total - expected) < 0.01


def test_exposure_summary(book):
    pos1 = open_position(book, "AAPL", "buy", 100, 150.0)
    assert pos1 is not None
    prices = {"AAPL": 155.0}
    summary = exposure_summary(
        [pos1],
        prices,
        cluster_map={"AAPL": "tech"},
    )
    assert summary["position_count"] == 1
    assert summary["long_count"] == 1
    assert "per_symbol" in summary
    assert "per_cluster" in summary
    assert summary["per_cluster"].get("tech") == 100 * 155.0


def test_position_unrealized_pnl(book):
    pos = open_position(book, "AAPL", "buy", 100, 150.0)
    assert pos is not None
    upnl = pos.unrealized_pnl(155.0)
    assert upnl == (155 - 150) * 100


def test_position_unrealized_pnl_short(book):
    pos = open_position(book, "AAPL", "sell", 100, 150.0)
    assert pos is not None
    upnl = pos.unrealized_pnl(145.0)
    assert upnl == (150 - 145) * 100


class TestArtifactIdAndFeedback:
    def test_open_position_carries_artifact_id(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 100, 150.0, artifact_id="art_123")
        assert pos.artifact_id == "art_123"

    def test_open_position_defaults_to_empty_artifact_id(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 100, 150.0)
        assert pos.artifact_id == ""

    def test_closed_position_carries_artifact_id_forward(self, book) -> None:
        pos = open_position(book, "AAPL", "buy", 100, 150.0, artifact_id="art_123")
        close_position(book, pos.position_id, 160.0)
        closed = list_closed_positions(book)
        assert len(closed) == 1
        assert closed[0]["artifact_id"] == "art_123"
        assert closed[0]["close_price"] == 160.0

    def test_list_closed_positions_filters_by_symbol(self, book) -> None:
        p1 = open_position(book, "AAPL", "buy", 10, 150.0)
        p2 = open_position(book, "MSFT", "buy", 10, 300.0)
        close_position(book, p1.position_id, 160.0)
        close_position(book, p2.position_id, 310.0)
        assert len(list_closed_positions(book, symbol="AAPL")) == 1
        assert len(list_closed_positions(book)) == 2

    def test_unprocessed_only_excludes_marked_and_artifactless(self, book) -> None:
        p1 = open_position(book, "AAPL", "buy", 10, 150.0, artifact_id="art_1")
        p2 = open_position(book, "MSFT", "buy", 10, 300.0)  # no artifact_id
        close_position(book, p1.position_id, 160.0)
        close_position(book, p2.position_id, 310.0)

        unprocessed = list_closed_positions(book, unprocessed_only=True)
        assert len(unprocessed) == 1
        assert unprocessed[0]["symbol"] == "AAPL"

        mark_feedback_processed(book, p1.position_id)
        assert list_closed_positions(book, unprocessed_only=True) == []
        # Marking doesn't remove the row -- it's still visible unfiltered.
        assert len(list_closed_positions(book)) == 2
