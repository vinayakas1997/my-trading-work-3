from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Any


REGIME_SIZING_MULTIPLIERS: dict[str | None, float] = {
    "bull": 1.0,
    "bear": 0.8,
    "sideways": 0.9,
    "high_vol": 0.6,
}

TIER_WARNING = 1
TIER_REDUCE = 2
TIER_HALT = 3


@dataclass
class SymbolRiskStatus:
    symbol: str
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    tier: int = 0
    regime_band_multiplier: float = 1.0
    suggested_size_multiplier: float = 1.0
    halted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RiskBudget:
    date: str = ""
    equity: float | None = None
    symbols: list[dict[str, Any]] = field(default_factory=list)
    aggregate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DailyPositionTracker:
    """In-memory daily P&L tracker. Resets each day."""

    def __init__(self) -> None:
        self._current_date: date | None = None
        self._daily_pnl: dict[str, float] = {}

    def _check_reset(self) -> None:
        today = datetime.now(timezone.utc).date()
        if self._current_date is None or today > self._current_date:
            self._current_date = today
            self._daily_pnl.clear()

    def record_daily_pnl(self, symbol: str, pnl: float) -> float:
        """Accumulate and return the running daily P&L for the symbol."""
        self._check_reset()
        prev = self._daily_pnl.get(symbol, 0.0)
        self._daily_pnl[symbol] = prev + pnl
        return self._daily_pnl[symbol]

    def get_daily_pnl(self, symbol: str) -> float:
        self._check_reset()
        return self._daily_pnl.get(symbol, 0.0)


def regime_sizing_multiplier(regime: str | None) -> float:
    return REGIME_SIZING_MULTIPLIERS.get(regime, 1.0)


def compute_symbol_tier(
    daily_pnl: float,
    equity: float,
    warning_threshold: float = -0.01,
    reduce_threshold: float = -0.02,
    halt_threshold: float = -0.03,
) -> int:
    if daily_pnl <= halt_threshold * equity:
        return TIER_HALT
    if daily_pnl <= reduce_threshold * equity:
        return TIER_REDUCE
    if daily_pnl <= warning_threshold * equity:
        return TIER_WARNING
    return 0


def compute_risk_budget(
    positions: list[dict[str, Any]],
    equity: float | None,
    regime: str | None = None,
    tracker: DailyPositionTracker | None = None,
    warning_threshold: float = -0.01,
    reduce_threshold: float = -0.02,
    halt_threshold: float = -0.03,
) -> RiskBudget:
    if equity is None or equity <= 0:
        return RiskBudget(
            date=datetime.now(timezone.utc).date().isoformat(),
            equity=None,
            symbols=[],
            aggregate={"status": "no_equity", "n_halted": 0, "n_warning": 0},
        )

    if tracker is None:
        tracker = DailyPositionTracker()

    band_mult = regime_sizing_multiplier(regime)
    symbols: list[SymbolRiskStatus] = []
    n_halted = 0
    n_warning = 0

    for p in positions:
        symbol = p.get("symbol", "?")
        current_pnl = float(p.get("unrealized_pl", 0.0))
        daily_pnl = tracker.record_daily_pnl(symbol, current_pnl)

        tier = compute_symbol_tier(
            daily_pnl, equity, warning_threshold, reduce_threshold, halt_threshold
        )

        size_mult = band_mult
        if tier >= TIER_REDUCE:
            size_mult *= 0.5
        if tier == TIER_HALT:
            size_mult = 0.0

        halted = tier == TIER_HALT
        if halted:
            n_halted += 1
        if tier == TIER_WARNING:
            n_warning += 1

        symbols.append(SymbolRiskStatus(
            symbol=symbol,
            daily_pnl=round(daily_pnl, 2),
            daily_pnl_pct=round(daily_pnl / equity * 100, 4) if equity else 0.0,
            tier=tier,
            regime_band_multiplier=round(band_mult, 4),
            suggested_size_multiplier=round(size_mult, 4),
            halted=halted,
        ))

    if not symbols:
        symbols.append(SymbolRiskStatus(
            symbol="*no_positions",
            daily_pnl=0.0,
            daily_pnl_pct=0.0,
            tier=0,
            regime_band_multiplier=round(band_mult, 4),
            suggested_size_multiplier=1.0,
            halted=False,
        ))

    total_pnl = sum(s.daily_pnl for s in symbols)
    aggregate = {
        "n_positions": len(symbols),
        "n_halted": n_halted,
        "n_warning": n_warning,
        "total_daily_pnl": round(total_pnl, 2),
        "total_daily_pnl_pct": round(total_pnl / equity * 100, 4) if equity else 0.0,
    }

    return RiskBudget(
        date=datetime.now(timezone.utc).date().isoformat(),
        equity=equity,
        symbols=[s.to_dict() for s in symbols],
        aggregate=aggregate,
    )
