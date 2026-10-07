"""One strategy, every bar size, judged by code.

A strategy written by a model (or a person) is run exactly as written on each bar size (15m, 1h, 4h, 1d), through the same
research loop and the same promotion bar a funded strategy must clear. Every number in the answer is copied from the
simulator's records; nothing a model typed is read. A bar size is `eligible` only when the run passed, it made at least
`min_trades_for_pass` trades, and `meets_promotion_bar` accepts it.

PBO needs a set of parameter trials. A fixed rule has none, so it is recorded as `None` with a note and not required for
that bar size; the deflated Sharpe (which counts every past trial on the symbol) and the holdout and stress checks still
apply.
"""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

LOG = logging.getLogger(__name__)

# History each bar size is judged over: the same windows the planner uses (a year of 15-minute bars is already ~6,500).
BAR_WINDOW_DAYS: dict[str, int] = {"1d": 1460, "4h": 1095, "1h": 730, "15m": 365}
DEFAULT_BARS = ("1d", "4h", "1h", "15m")


_IMPORTS = """from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_simulator.engine.strategies import BaseStrategy


"""


def normalise_strategy_code(code: str) -> str:
    """The form the research loop runs: a class named UserStrategy and the standard imports. The agent's prompt tells
    models to write `class Strategy(BaseStrategy)` with no imports; the loop needs the other form. Raises ValueError
    (with the reason) when the code cannot be put in that form."""
    import ast
    import re

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"strategy_code is not valid Python: {exc.msg} (line {exc.lineno})") from exc
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    if not any(c.name == "UserStrategy" for c in classes):
        strategies = [c for c in classes if any(getattr(b, "id", "") == "BaseStrategy" for b in c.bases)]
        if len(strategies) != 1:
            raise ValueError("strategy_code must define one class that subclasses BaseStrategy")
        code = re.sub(r"\bclass\s+" + re.escape(strategies[0].name) + r"\b", "class UserStrategy", code, count=1)
    if not re.search(r"^\s*(import|from)\s+pandas\b", code, re.M):
        code = _IMPORTS + code
    return code


# Columns a strategy may read: price/volume, plus the few indicators the backtest can merge into the DataFrame.
OHLCV = frozenset({"open", "high", "low", "close", "volume"})
_MERGEABLE = re.compile(r"^(sma_\d+|rsi_14|macd|macd_signal|daily_return|volatility_20d|adx_14)$")
MERGEABLE_HELP = "open, high, low, close, volume, sma_N, rsi_14, macd, macd_signal, daily_return, volatility_20d, adx_14"


def plan_indicators(code: str) -> tuple[list[str], list[str]]:
    """(indicator columns to request, unknown columns) from the `data[...]` / `data.get(...)` names the code reads.
    A strategy that reads a column the backtest cannot supply crashes on every bar size; finding that here costs nothing
    and gives the writer the list of real names."""
    import ast

    tree = ast.parse(code)
    subscripted: set[str] = set()
    fetched: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "data":
            key = node.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                subscripted.add(key.value)
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
              and isinstance(node.func.value, ast.Name) and node.func.value.id == "data"
              and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            fetched.add(node.args[0].value)     # .get() has a default, so a missing column is not a crash
    indicators = sorted(c for c in subscripted | fetched if _MERGEABLE.match(c))
    unknown = sorted(c for c in subscripted if c not in OHLCV and not _MERGEABLE.match(c))
    return indicators, unknown


MAX_STALE_DAYS = 7           # newest bar older than this (a long weekend is 4 days) means ingestion has stopped
_MIN_HISTORY_SHARE = 0.9     # the catalog must reach back over at least this much of the bar size's window


def data_problem(entry: dict[str, Any] | None, window_days: int, *, now: float | None = None) -> str:
    """Why the price data cannot support a test over `window_days`, or "" when it can. `entry` is the price service's
    catalog row for the symbol."""
    import time

    if not entry:
        return "the symbol is not in the price catalog"
    if entry.get("backfill_status") != "complete":
        return f"history backfill is {entry.get('backfill_status') or 'unknown'}, not complete"
    last = entry.get("last_bar_ts") or 0
    age_days = ((now if now is not None else time.time()) - last) / 86_400
    if age_days > MAX_STALE_DAYS:
        return f"the newest bar is {age_days:.0f} days old (more than {MAX_STALE_DAYS}); price ingestion has stalled"
    have_days = (last - (entry.get("first_bar_ts") or last)) / 86_400
    if have_days < window_days * _MIN_HISTORY_SHARE:
        return f"only {have_days:.0f} days of history; this bar size needs about {window_days}"
    return ""


def catalog_entry(config: Any, symbol: str) -> dict[str, Any] | None:
    """The price service's catalog row for `symbol`, or None when it is missing or the service cannot be reached."""
    import httpx

    try:
        r = httpx.get(f"{config.stock_price_api_url}/stock/catalog/{symbol}", timeout=15)
        rows = (r.json() or {}).get("data") or [] if r.status_code == 200 else []
        return rows[0] if rows else None
    except Exception as exc:  # noqa: BLE001 -- unreachable data service means "not ready", never "ready"
        LOG.warning("price catalog lookup for %s failed: %s", symbol, exc)
        return None


def bars_from_config(config: Any) -> list[str]:
    configured = [b for b in config.sweep_interval_list() if b in BAR_WINDOW_DAYS]
    return configured or list(DEFAULT_BARS)


def _eligibility(run: dict[str, Any], config: Any) -> tuple[bool, list[str], bool]:
    """(eligible, reasons, pbo_waived) for one finished run on one bar size."""
    from vinu_research.models import Artifact
    from vinu_research.promotion import meets_promotion_bar

    attempt = run.get("attempt") or {}
    reasons: list[str] = []
    trades = int(attempt.get("trade_count") or 0)
    if run.get("outcome_status") != "passed":
        # It failed the in-sample checks, so the holdout / stress / deflated-Sharpe steps never ran: report what the loop
        # actually found, not a list of "never computed".
        from vinu_research.strategy_validation import attempt_from_report

        found = attempt_from_report(run.get("report_md", "")).get("failed_checks") or []
        reasons.append(f"the research loop did not pass it ({run.get('outcome_status') or 'no outcome'})")
        reasons.extend(found)
        if trades < config.min_trades_for_pass:
            reasons.append(f"only {trades} trades; at least {config.min_trades_for_pass} are needed to trust the result")
        return False, reasons, run.get("pbo") is None
    if trades < config.min_trades_for_pass:
        reasons.append(f"only {trades} trades; at least {config.min_trades_for_pass} are needed to trust the result")

    pbo = run.get("pbo")
    waived = pbo is None
    bar_config = replace(config, promotion_pbo_required=False) if waived else config
    probe = Artifact.create(type_="strategy", name="bar_validation_probe", universe=[str(run.get("symbol", ""))])
    probe.initial_sharpe = float(run.get("best_sharpe") or attempt.get("sharpe") or 0.0)
    probe.deflated_sharpe = float(run.get("deflated_sharpe") or 0.0)
    probe.holdout_passed = run.get("holdout_passed")
    probe.stress_test_passed = run.get("stress_test_passed")
    probe.pbo = pbo
    reasons.extend(meets_promotion_bar(probe, bar_config).reasons)
    return not reasons, reasons, waived


def _row(interval: str, window: tuple[str, str], run: dict[str, Any] | None, config: Any, error: str = "") -> dict[str, Any]:
    base: dict[str, Any] = {"interval": interval, "from_date": window[0], "to_date": window[1]}
    if run is None or not run.get("total_iterations"):
        reason = error or "the research run did not execute the strategy"
        return {**base, "tested": False, "eligible": False, "reasons": [reason]}
    eligible, reasons, waived = _eligibility(run, config)
    attempt = run.get("attempt") or {}
    return {
        **base, "tested": True, "eligible": eligible, "reasons": reasons, "run_id": run.get("id"),
        "outcome": run.get("outcome_status"), "sharpe": attempt.get("sharpe"), "max_drawdown": attempt.get("max_drawdown"),
        "total_return": attempt.get("total_return"), "trade_count": attempt.get("trade_count"),
        "win_rate": attempt.get("win_rate"), "deflated_sharpe": run.get("deflated_sharpe"),
        "holdout_passed": run.get("holdout_passed"), "stress_test_passed": run.get("stress_test_passed"),
        "pbo": run.get("pbo"), "pbo_waived": waived, "diagnosis": run.get("diagnosis", ""),
    }


def choose_bar(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The eligible bar size with the highest deflated Sharpe, or None."""
    eligible = [r for r in rows if r.get("eligible")]
    if not eligible:
        return None
    return max(eligible, key=lambda r: (float(r.get("deflated_sharpe") or 0.0), float(r.get("sharpe") or 0.0)))


async def validate_across_bars(
    service: Any, *, symbol: str, strategy_code: str, bars: list[str] | None = None, to_date: str | None = None,
    catalog_lookup: Any = None,
) -> dict[str, Any]:
    """Run `strategy_code` unchanged on each bar size and return a comparison table plus the chosen bar size."""
    config = service.config
    end = date.fromisoformat(to_date) if to_date else date.today()
    rows: list[dict[str, Any]] = []
    entry = (catalog_lookup or catalog_entry)(config, symbol)
    indicators, unknown = plan_indicators(strategy_code)
    if unknown:
        reason = (f"the strategy reads column(s) the backtest cannot supply: {', '.join(unknown)}. "
                  f"Available columns: {MERGEABLE_HELP}")
        rows = [_row(b, ("", ""), None, config, error=reason) for b in (bars or bars_from_config(config))]
        return {"symbol": symbol, "bars": rows, "passing_bars": [], "chosen_bar": None, "chosen": None}
    for interval in (bars or bars_from_config(config)):
        if interval not in BAR_WINDOW_DAYS:
            rows.append(_row(interval, ("", ""), None, config, error=f"bar size {interval!r} is not testable"))
            continue
        window = ((end - timedelta(days=BAR_WINDOW_DAYS[interval])).isoformat(), end.isoformat())
        problem = data_problem(entry, BAR_WINDOW_DAYS[interval])
        if problem:
            rows.append(_row(interval, window, None, config, error=f"data not ready: {problem}"))
            continue
        try:
            run = await service.run_research(
                user_idea=f"validate {symbol} strategy on {interval} bars", symbol=symbol, from_date=window[0],
                to_date=window[1], strategy_code=strategy_code, interval=interval, max_iterations=1, validation=True,
                indicators=indicators or None,
            )
            rows.append(_row(interval, window, run, config))
        except Exception as exc:  # noqa: BLE001 -- one bar size failing must not hide the others
            LOG.warning("bar validation %s %s failed: %s", symbol, interval, exc)
            rows.append(_row(interval, window, None, config, error=f"{type(exc).__name__}: {exc}"))
    best = choose_bar(rows)
    return {"symbol": symbol, "bars": rows, "passing_bars": [r["interval"] for r in rows if r["eligible"]],
            "chosen_bar": best["interval"] if best else None, "chosen": best}
