"""Backtest-vs-realized parity report (v2 A3): is what a strategy / forecast promised what it delivered?

Two comparisons, both read-only and advisory (nothing consumes the verdicts yet -- see the status doc):

1. **Strategies: backtest vs paper replay.** Each strategy artifact carries the Sharpe and max drawdown its
   backtest produced (`initial_sharpe`, `initial_max_dd`); the shadow evaluator then appends one paper day at a
   time (`paper_performance`). Realized Sharpe / drawdown over those days is compared with the backtest's, with
   a standard error so a short paper window does not produce a confident verdict it cannot support.

   **Read this before trusting it:** the paper series is *not* independent of the backtest engine. It is the
   strategy's own code re-run on the most recent trading day (`ShadowEvaluator.record_daily_paper_returns`),
   with no order, fill, spread or slippage in it. So this measures *out-of-sample stability after promotion*
   (did the edge survive new days?), NOT execution parity (slippage, partial fills, latency). Execution parity
   needs real fills compared with the reference price at decision time, which this system does not record yet.

2. **Trade plans: stated vs realized.** Over closed live trades (`calibration_entries`), mean stated confidence
   (recovered from the Brier score, see confidence_calibration.py) against realized directional hit rate, and
   mean forecast magnitude against the realized return in the forecast direction.

Pure functions, no I/O, never raise on odd input. Verdict vocabulary: `insufficient_data`,
`no_backtest_expectation`, `in_line`, `underperforming` / `overconfident` / `overstated_magnitude`. `in_line`
only means "no shortfall detectable at this sample size": the report carries the standard error and the
smallest shortfall it could have detected, so a thin window is visibly thin.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from vinu_research.confidence_calibration import recover_pairs

TRADING_DAYS = 252
DEFAULT_MIN_PAPER_DAYS = 20
DEFAULT_MIN_TRADES = 30
Z_FLAG = 2.0


def _clean(returns: Iterable[Any]) -> list[float]:
    out: list[float] = []
    for r in returns or []:
        try:
            f = float(r)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def realized_stats(daily_returns: Iterable[Any]) -> dict[str, Any]:
    """n, mean daily return, annualized Sharpe (None when undefined), max drawdown (positive fraction), hit rate."""
    r = _clean(daily_returns)
    n = len(r)
    out: dict[str, Any] = {"n_days": n, "mean_daily_return": None, "sharpe": None, "max_drawdown": None, "hit_rate": None}
    if n == 0:
        return out
    out["mean_daily_return"] = statistics.fmean(r)
    out["hit_rate"] = sum(1 for x in r if x > 0) / n
    equity, peak, worst = 1.0, 1.0, 0.0
    for x in r:
        equity *= 1.0 + x
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak if peak > 0 else 0.0)
    out["max_drawdown"] = worst
    if n >= 2:
        sd = statistics.stdev(r)
        if sd > 0:
            out["sharpe"] = statistics.fmean(r) / sd * math.sqrt(TRADING_DAYS)
    return out


def sharpe_standard_error(sharpe_annual: float, n_days: int) -> float | None:
    """Standard error of an annualized Sharpe estimated from `n_days` daily returns (Lo 2002, i.i.d. approximation)."""
    if n_days < 2:
        return None
    sr_daily = sharpe_annual / math.sqrt(TRADING_DAYS)
    return math.sqrt((1.0 + 0.5 * sr_daily * sr_daily) / n_days) * math.sqrt(TRADING_DAYS)


@dataclass
class StrategyParity:
    artifact_id: str
    verdict: str
    expected_sharpe: float | None = None
    expected_max_drawdown: float | None = None
    realized: dict[str, Any] = field(default_factory=dict)
    sharpe_standard_error: float | None = None
    z_score: float | None = None
    detectable_shortfall: float | None = None   # 2 standard errors: a smaller gap could not have been seen
    drawdown_exceeds_backtest: bool = False
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def strategy_parity(
    artifact_id: str,
    expected_sharpe: float | None,
    expected_max_drawdown: float | None,
    daily_returns: Sequence[Any] | None,
    *,
    min_days: int = DEFAULT_MIN_PAPER_DAYS,
) -> StrategyParity:
    stats = realized_stats(daily_returns or [])
    p = StrategyParity(
        artifact_id=artifact_id, verdict="insufficient_data", realized=stats,
        expected_sharpe=expected_sharpe, expected_max_drawdown=abs(expected_max_drawdown) if expected_max_drawdown else None,
    )
    n = stats["n_days"]
    if n < min_days:
        p.note = f"{n} paper day(s) < {min_days}: too few to compare"
        return p
    if expected_sharpe is None or expected_sharpe <= 0:
        p.verdict = "no_backtest_expectation"
        p.note = "the backtest recorded no positive Sharpe to compare against"
        return p
    if stats["sharpe"] is None:
        p.note = "realized Sharpe undefined (constant or single return)"
        return p
    se = sharpe_standard_error(stats["sharpe"], n)
    p.sharpe_standard_error = se
    if se and se > 0:
        p.z_score = (stats["sharpe"] - expected_sharpe) / se
        p.detectable_shortfall = Z_FLAG * se
    p.verdict = "underperforming" if p.z_score is not None and p.z_score < -Z_FLAG else "in_line"
    if p.expected_max_drawdown and stats["max_drawdown"] is not None:
        p.drawdown_exceeds_backtest = stats["max_drawdown"] > 1.5 * p.expected_max_drawdown
    if p.verdict == "in_line" and p.detectable_shortfall is not None and p.detectable_shortfall > expected_sharpe:
        p.note = (f"only a Sharpe shortfall above {p.detectable_shortfall:.2f} (the whole expected {expected_sharpe:.2f}) "
                  f"could be seen at {n} days: 'in_line' here is weak evidence")
    return p


@dataclass
class TradePlanParity:
    verdict: str
    n_trades: int = 0
    expected_hit_rate: float | None = None      # mean stated confidence
    realized_hit_rate: float | None = None
    hit_rate_z: float | None = None
    expected_move: float | None = None          # mean forecast magnitude (fraction)
    realized_move: float | None = None          # mean return in the forecast direction
    move_capture: float | None = None           # realized / expected
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def trade_plan_parity(entries: Iterable[Any], *, min_trades: int = DEFAULT_MIN_TRADES) -> TradePlanParity:
    entries = list(entries or [])
    pairs = recover_pairs(entries)
    directional = [e for e in entries if getattr(e, "forecast_direction", None) in ("long", "short")]
    n = len(pairs)
    out = TradePlanParity(verdict="insufficient_data", n_trades=n)
    if n < min_trades:
        out.note = f"{n} closed directional trade(s) < {min_trades}: too few to compare"
        return out
    p_exp = statistics.fmean(c for c, _ in pairs)
    p_real = sum(1 for _, h in pairs if h) / n
    out.expected_hit_rate, out.realized_hit_rate = p_exp, p_real
    se = math.sqrt(max(p_exp * (1 - p_exp), 1e-12) / n)
    out.hit_rate_z = (p_real - p_exp) / se
    moves, mags = [], []
    for e in directional:
        try:
            ret, mag = float(e.actual_return_pct), float(e.forecast_magnitude_pct)
        except (TypeError, ValueError):
            continue
        if math.isfinite(ret) and math.isfinite(mag) and mag > 0:
            moves.append(ret if e.forecast_direction == "long" else -ret)
            mags.append(mag)
    if moves:
        out.expected_move, out.realized_move = statistics.fmean(mags), statistics.fmean(moves)
        out.move_capture = out.realized_move / out.expected_move
    if out.hit_rate_z < -Z_FLAG:
        out.verdict = "overconfident"
        out.note = f"stated confidence averaged {p_exp:.2f} but only {p_real:.2f} of calls were right"
    elif out.move_capture is not None and out.move_capture < 0.5 and len(moves) >= min_trades:
        out.verdict = "overstated_magnitude"
        out.note = f"realized only {out.move_capture:.0%} of the forecast move"
    else:
        out.verdict = "in_line"
    return out


def build_parity_report(
    strategies: Iterable[Any],
    paper_returns: dict[str, Sequence[Any]],
    calibration_entries: Iterable[Any],
    *,
    min_days: int = DEFAULT_MIN_PAPER_DAYS,
    min_trades: int = DEFAULT_MIN_TRADES,
) -> dict[str, Any]:
    """`strategies`: anything with artifact_id / initial_sharpe / initial_max_dd. `paper_returns`: artifact_id -> daily returns
    (artifacts without an entry are reported as insufficient_data)."""
    rows = [
        strategy_parity(
            s.artifact_id, getattr(s, "initial_sharpe", None), getattr(s, "initial_max_dd", None),
            paper_returns.get(s.artifact_id), min_days=min_days,
        ).to_dict()
        for s in strategies
    ]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return {
        "kind": "backtest_vs_paper_replay",
        "caveat": ("paper days are the strategy's code re-run on new days, not real fills: this measures out-of-sample stability, "
                   "not execution parity (slippage, spread, partial fills)"),
        "strategies": {"count": len(rows), "by_verdict": counts, "rows": rows},
        "trade_plans": trade_plan_parity(calibration_entries, min_trades=min_trades).to_dict(),
    }


def read_paper_returns_db(agent_data_root: Any) -> dict[str, list[float]] | None:
    """artifact_id -> daily paper returns, from vinu-agent's `paper_performance.db` (raw read-only sqlite, the same
    way maturity_assessor reads it -- no import of the other service). None when the root is unset / the file is
    missing / unreadable, so the caller can fall back to HTTP and say where the data came from."""
    import json
    import sqlite3
    from pathlib import Path

    if not agent_data_root:
        return None
    db = Path(agent_data_root) / "paper_performance.db"
    if not db.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT artifact_id, returns_json FROM paper_performance").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    out: dict[str, list[float]] = {}
    for artifact_id, raw in rows:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, list):
            out[artifact_id] = _clean(parsed)
    return out
