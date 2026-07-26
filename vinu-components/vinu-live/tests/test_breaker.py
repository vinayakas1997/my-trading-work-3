import os
import tempfile
import pytest
import numpy as np
from vinu_live.breaker import (
    BreakerLimits,
    BreakerState,
    DEFAULT_LIMITS,
    check_limits,
    reset_breaker,
    BreakerVerdict,
)
from vinu_live.book import init_book, open_position


@pytest.fixture
def book():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    be = init_book(db_path)
    yield be
    be.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_allow_when_within_limits(book):
    open_position(book, "AAPL", "buy", 100, 150.0)
    prices = {"AAPL": 155.0}
    verdict, reason = check_limits(
        book, prices=prices, portfolio_value=100000,
        daily_realized_pnl=0, covariance_matrix=None,
    )
    assert verdict == BreakerVerdict.ALLOW
    assert reason is None


def test_halt_on_daily_loss(book):
    open_position(book, "AAPL", "buy", 100, 150.0)
    prices = {"AAPL": 155.0}
    limits = BreakerLimits(max_daily_loss_pct=0.01)
    verdict, reason = check_limits(
        book, prices=prices, portfolio_value=100000,
        daily_realized_pnl=-5000, covariance_matrix=None,
        limits=limits,
    )
    assert verdict == BreakerVerdict.HALT
    assert "Daily loss" in reason


def test_halt_on_position_count(book):
    for i in range(25):
        open_position(book, f"SYM{i}", "buy", 10, 100.0)
    prices = {f"SYM{i}": 100.0 for i in range(25)}
    limits = BreakerLimits(max_position_count=20)
    verdict, reason = check_limits(
        book, prices=prices, portfolio_value=100000,
        daily_realized_pnl=0, covariance_matrix=None,
        limits=limits,
    )
    assert verdict == BreakerVerdict.HALT
    assert "Position count" in reason


def test_halt_on_leverage(book):
    open_position(book, "AAPL", "buy", 10000, 150.0)
    prices = {"AAPL": 150.0}
    limits = BreakerLimits(max_leverage=1.0)
    verdict, reason = check_limits(
        book, prices=prices, portfolio_value=100000,
        daily_realized_pnl=0, covariance_matrix=None,
        limits=limits,
    )
    assert verdict == BreakerVerdict.HALT
    assert "Leverage" in reason


def test_halt_on_aggregate_var(book):
    open_position(book, "AAPL", "buy", 100, 150.0)
    open_position(book, "GOOGL", "buy", 100, 200.0)
    prices = {"AAPL": 150.0, "GOOGL": 200.0}
    cov = np.array([[0.25, 0.2], [0.2, 0.3]])
    limits = BreakerLimits(max_var_95_pct=0.001)
    verdict, reason = check_limits(
        book, prices=prices, portfolio_value=100000,
        daily_realized_pnl=0, covariance_matrix=cov,
        limits=limits,
    )
    assert verdict == BreakerVerdict.HALT
    assert "VaR" in reason


def test_halt_on_cluster_exposure(book):
    open_position(book, "AAPL", "buy", 100, 150.0)
    open_position(book, "MSFT", "buy", 100, 200.0)
    prices = {"AAPL": 150.0, "MSFT": 200.0}
    cluster_map = {"AAPL": "tech", "MSFT": "tech"}
    limits = BreakerLimits(max_cluster_exposure_pct=0.10)
    verdict, reason = check_limits(
        book, prices=prices, portfolio_value=100000,
        daily_realized_pnl=0, covariance_matrix=None,
        cluster_map=cluster_map, limits=limits,
    )
    assert verdict == BreakerVerdict.HALT
    assert "Cluster" in reason


def test_halted_state_persists(book):
    open_position(book, "AAPL", "buy", 100, 150.0)
    prices = {"AAPL": 155.0}
    state = BreakerState()
    state.halted = True
    state.halted_reason = "manual"
    verdict, reason = check_limits(
        book, prices=prices, portfolio_value=100000,
        daily_realized_pnl=0, covariance_matrix=None,
        state=state,
    )
    assert verdict == BreakerVerdict.HALT
    assert reason == "manual"


def test_reset_breaker():
    state = BreakerState()
    state.halted = True
    state.halted_reason = "test"
    reset_breaker(state)
    assert not state.halted
    assert state.halted_reason == ""


def test_cluster_exposure_not_needed_without_map(book):
    open_position(book, "AAPL", "buy", 100, 150.0)
    prices = {"AAPL": 155.0}
    verdict, reason = check_limits(
        book, prices=prices, portfolio_value=100000,
        daily_realized_pnl=0, covariance_matrix=None,
        cluster_map=None,
    )
    assert verdict == BreakerVerdict.ALLOW


def test_empty_book_allows(book):
    prices = {}
    verdict, reason = check_limits(
        book, prices=prices, portfolio_value=100000,
        daily_realized_pnl=0, covariance_matrix=None,
    )
    assert verdict == BreakerVerdict.ALLOW
