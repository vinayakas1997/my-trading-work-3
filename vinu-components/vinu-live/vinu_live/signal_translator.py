from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from vinu_live.book.quantize import (
    money_float,
    quantize_money,
    quantize_qty,
)

LOG = logging.getLogger(__name__)


@dataclass
class OrderInstruction:
    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    target_weight: float
    current_qty: float
    estimated_value: float
    strategy_name: str = ""


class SignalTranslator:
    """Converts target portfolio weights into concrete order instructions.

    Diffs target weights against current broker positions, sizes the delta,
    and produces OrderInstructions ready for execution (with or without
    slicing).
    """

    def __init__(self, max_slippage_pct: float = 0.001) -> None:
        self._max_slippage_pct = max_slippage_pct

    def translate(
        self,
        target_weights: list[dict[str, Any]],
        current_positions: dict[str, float],
        portfolio_value: float,
        prices: dict[str, float],
    ) -> list[OrderInstruction]:
        """Diff target weights vs. current positions and produce orders.

        Args:
            target_weights: [{name, symbol, target_weight, ...}, ...]
            current_positions: {symbol: qty}
            portfolio_value: Total portfolio value in dollars.
            prices: {symbol: current_price}

        Returns:
            List of OrderInstructions (buy side for underweights, sell for
            overweights). Zero-delta positions are omitted. Symbols currently
            held but no longer present in target_weights (a strategy that
            exited a name, or was itself dropped) are treated as target_weight
            0.0 and produce a full close instruction — previously these were
            silently never sold, since the loop only ever considered symbols
            that appeared in target_weights.
        """
        instructions: list[OrderInstruction] = []
        seen_symbols: set[str] = set()

        for tw in target_weights:
            symbol = tw.get("symbol", "")
            if not symbol:
                continue
            seen_symbols.add(symbol)
            target_w = tw.get("target_weight", 0.0)
            instr = self._build_instruction(
                symbol, target_w, current_positions, prices, portfolio_value,
                strategy_name=tw.get("name", ""),
            )
            if instr is not None:
                instructions.append(instr)

        for symbol, current_qty in current_positions.items():
            if symbol in seen_symbols or abs(current_qty) < 0.001:
                continue
            instr = self._build_instruction(
                symbol, 0.0, current_positions, prices, portfolio_value,
                strategy_name="",
            )
            if instr is not None:
                instructions.append(instr)

        return instructions

    @staticmethod
    def _build_instruction(
        symbol: str,
        target_w: float,
        current_positions: dict[str, float],
        prices: dict[str, float],
        portfolio_value: float,
        strategy_name: str,
    ) -> OrderInstruction | None:
        from decimal import Decimal

        target_value = Decimal(str(target_w)) * Decimal(str(portfolio_value))
        price = prices.get(symbol, 1.0)
        if price <= 0:
            return None
        target_qty = target_value / Decimal(str(price))
        current_qty = Decimal(str(current_positions.get(symbol, 0.0)))
        delta = target_qty - current_qty

        if abs(delta) < Decimal("0.001"):
            return None

        # Quantize the order quantity to the instrument's tradeable
        # increment (whole shares by default) -- never emit a fractional
        # share count computed from float division (task 12).
        abs_qty = quantize_qty(abs(delta))
        if abs_qty <= 0:
            return None

        side = "buy" if delta > 0 else "sell"
        estimated_value = money_float(quantize_money(abs_qty * Decimal(str(price))))

        return OrderInstruction(
            symbol=symbol,
            side=side,
            qty=float(abs_qty),
            target_weight=target_w,
            current_qty=float(current_qty),
            estimated_value=estimated_value,
            strategy_name=strategy_name,
        )
