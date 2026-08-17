"""Regression tests for the Decimal money path (implementation-plan task 12).

These prove the specific bug class Decimal prevents — float drift that
compounds into real lost/gained money on the order-quantity and cash-ledger
path — through the REAL code (book/positions.py, signal_translator.py,
execution.py), not a synthetic Decimal helper.

Analytics (weights, Sharpe, thresholds) stays float on purpose; nothing here
touches that.
"""

from __future__ import annotations

import os
import tempfile
from decimal import Decimal

import pytest

from vinu_live.book.positions import (
    add_to_position,
    close_position,
    daily_realized_pnl,
    get_position,
    init_book,
    open_position,
    reduce_position,
)
from vinu_live.book.quantize import (
    quantize_money,
    quantize_qty,
    sum_money,
    to_decimal,
)
from vinu_live.execution import ExecutionSlice, plan_twap, plan_vwap
from vinu_live.signal_translator import OrderInstruction, SignalTranslator


@pytest.fixture
def book():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    be = init_book(db_path)
    yield be
    be.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestQuantizeHelpers:
    def test_decimal_is_exact_where_float_drifts(self):
        # The canonical 0.1 + 0.2 != 0.3 float bug, on the exact helpers
        # every money computation on this path now goes through.
        assert to_decimal(0.1) + to_decimal(0.2) == Decimal("0.3")
        assert float(to_decimal(0.1) + to_decimal(0.2)) == 0.3

    def test_quantize_qty_rounds_to_whole_shares(self):
        assert quantize_qty(0.6) == Decimal("1")
        assert quantize_qty(0.4) == Decimal("0")

    def test_quantize_money_rounds_to_cents(self):
        assert quantize_money("0.105") == Decimal("0.11")
        assert quantize_money("0.104") == Decimal("0.10")

    def test_sum_money_is_exact(self):
        # float(sum([0.1, 0.1, 0.1])) == 0.30000000000000004; this path is exact.
        assert sum_money([0.1, 0.1, 0.1]) == 0.3


class TestLedgerDecimalArithmetic:
    def test_realized_pnl_accumulates_exactly_no_float_drift(self, book):
        # Three fills that each realize exactly 0.10. In pure float the
        # ledger would accumulate 0.30000000000000004; with the Decimal
        # path daily_realized_pnl is exactly 0.3.
        for i in range(3):
            pos = open_position(book, f"DRIFT{i}", "buy", 1, 10.0)
            assert pos is not None
            assert reduce_position(book, pos.position_id, 1, 10.1) is None  # closed
        assert daily_realized_pnl(book) == 0.3

    def test_commission_reduces_realized_exactly(self, book):
        # 0.01 commission per fill, subtracted exactly: 0.10 - 0.01 = 0.09
        # per fill, summed to exactly 0.27 -- no drift anywhere.
        for i in range(3):
            pos = open_position(book, f"CMSN{i}", "buy", 1, 10.0)
            assert reduce_position(book, pos.position_id, 1, 10.1, commission=0.01) is None
        assert daily_realized_pnl(book) == 0.27

    def test_weighted_average_entry_is_not_cents_truncated(self, book):
        # A truncated cents average (153.33) would scale into real money
        # error over shares; the cost basis stays Decimal-exact.
        pos = open_position(book, "AAPL", "buy", 100, 150.0)
        updated = add_to_position(book, pos.position_id, 50, 160.0)
        expected_avg = (100 * 150 + 50 * 160) / 150
        assert abs(updated.avg_entry - expected_avg) < 1e-6

    def test_realized_pnl_through_close_position_is_exact(self, book):
        pos = open_position(book, "AAPL", "buy", 100, 150.0)
        close_position(book, pos.position_id, 160.0)
        assert daily_realized_pnl(book) == 1000.0


class TestSignalTranslatorQuantizedQuantity:
    def _translate(self, target_w, price=100.0, portfolio=100000.0, current=None):
        return SignalTranslator().translate(
            target_weights=[{"name": "s", "symbol": "AAPL", "target_weight": target_w}],
            current_positions=current or {},
            portfolio_value=portfolio,
            prices={"AAPL": price},
        )

    def test_fractional_target_becomes_a_whole_share_order(self):
        # 0.5% of $100,000 at $100 = 5 shares exactly; a 0.525% target would
        # be 5.25 shares in float -- the order qty must be whole shares.
        instrs = self._translate(0.005)
        assert instrs[0].qty == 5.0
        instrs = self._translate(0.00525)
        assert instrs[0].qty == 5.0  # 5.25 rounds to 5, never 5.2500000001

    def test_sub_share_delta_after_quantization_is_skipped(self):
        # A delta that quantizes to zero shares (0.004 -> 0) must not emit a
        # fractional-share order.
        instrs = self._translate(0.5, portfolio=1000.0, price=100.0)  # target 5.0
        assert instrs[0].qty == 5.0
        instrs = self._translate(0.5, portfolio=1000.0, price=100.0, current={"AAPL": 5.0})
        assert instrs == []

    def test_zero_quantized_qty_is_not_emitted(self):
        instrs = self._translate(0.00004, portfolio=1000.0, price=100.0)  # 0.0004 -> 0 shares
        assert instrs == []


class TestExecutionSlicesExact:
    def _instr(self, qty):
        return OrderInstruction(symbol="AAPL", side="buy", qty=qty,
                                target_weight=0.5, current_qty=0.0, estimated_value=qty * 100.0)

    def test_twap_slices_sum_exactly_to_order_qty(self):
        # 100 / 6 in float = 16.666...; slices must be whole shares and the
        # remainder must fold into the last slice so the sum is exactly 100.
        plan = plan_twap([self._instr(100.0)], n_slices=6)
        assert len(plan.slices) == 6
        assert sum(s.qty for s in plan.slices) == 100.0
        assert all(s.qty == int(s.qty) for s in plan.slices)  # whole shares

    def test_vwap_slices_sum_exactly_to_order_qty(self):
        plan = plan_vwap([self._instr(100.0)], volume_weights={"AAPL": [0.4, 0.3, 0.2, 0.1]}, n_slices=4)
        assert [s.qty for s in plan.slices] == [40.0, 30.0, 20.0, 10.0]
        assert sum(s.qty for s in plan.slices) == 100.0

    def test_tiny_slice_sums_never_drift(self):
        # 1 share over 10 slices: nine zero-slices plus the full share folded
        # into the last -- never 0.10000000000000002-style slices.
        plan = plan_twap([self._instr(1.0)], n_slices=10)
        assert sum(s.qty for s in plan.slices) == 1.0
        assert [s.qty for s in plan.slices].count(0.0) == 9
        assert plan.slices[-1].qty == 1.0