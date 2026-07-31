from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

from vinu_portfolio.regime import classify_current_regime
from vinu_portfolio.service import PortfolioService

LOG = logging.getLogger(__name__)

DEFAULT_WARMUP_DAYS = 21  # matches regime.py's rolling-vol window


@dataclass
class SimulationMetrics:
    sharpe: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    calmar: float = 0.0
    annualized_return: float = 0.0
    total_return: float = 0.0
    n_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SimulationResult:
    status: str = "ok"
    strategy_metrics: dict[str, Any] = field(default_factory=dict)
    equal_weight_metrics: dict[str, Any] = field(default_factory=dict)
    benchmark_metrics: dict[str, Any] = field(default_factory=dict)
    daily_records: list[dict[str, Any]] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    n_days: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _empty_result(reason: str) -> SimulationResult:
    return SimulationResult(status="empty", warnings=[reason])


def compute_performance_metrics(daily_returns: pd.Series) -> SimulationMetrics:
    """Sharpe, max drawdown, win rate, Calmar from a series of daily
    simple returns. Assumes 252 trading days/year."""
    daily_returns = daily_returns.dropna()
    if daily_returns.empty:
        return SimulationMetrics()

    ann_factor = 252.0 ** 0.5
    mean = float(daily_returns.mean())
    std = float(daily_returns.std())
    sharpe = (mean / std) * ann_factor if std > 0 else 0.0

    cum = (1.0 + daily_returns).cumprod()
    running_max = cum.cummax()
    drawdown = cum / running_max - 1.0
    max_dd = float(drawdown.min())

    win_rate = float((daily_returns > 0).mean())
    total_return = float(cum.iloc[-1] - 1.0)
    n_days = len(daily_returns)
    annualized_return = (
        float((1.0 + total_return) ** (252.0 / n_days) - 1.0) if n_days > 0 else 0.0
    )
    calmar = float(annualized_return / abs(max_dd)) if max_dd < 0 else 0.0

    return SimulationMetrics(
        sharpe=round(sharpe, 4),
        max_drawdown=round(max_dd, 4),
        win_rate=round(win_rate, 4),
        calmar=round(calmar, 4),
        annualized_return=round(annualized_return, 4),
        total_return=round(total_return, 4),
        n_days=n_days,
    )


def run_historical_simulation(
    strategies: list[dict[str, Any]],
    returns_df: pd.DataFrame,
    benchmark_returns: pd.Series,
    service: PortfolioService,
    warmup_days: int = DEFAULT_WARMUP_DAYS,
) -> SimulationResult:
    """Walk-forward daily-rebalance replay of the risk-parity + regime-tilt
    allocation (`PortfolioService.allocate_risk_parity()` +
    `_regime_alignment_multiplier()`) against historical returns, with no
    look-ahead: weights decided at close of day t only ever see returns
    up to and including day t, then are held for day t+1's realized return.

    Deliberately out of scope for this v1 (documented, not an oversight):
    outcome-confidence and shock-clustering tilts, and the Step 04/05
    game-plan/risk-budget layers. Both depend on live artifact/broker
    state (which strategy artifact was ACTIVE with what calibration
    accuracy on a given past date, live account equity, live positions)
    that has no recorded historical trail to replay against — reusing them
    here would mean fabricating history, not simulating it. This replays
    the part of the pipeline that *is* honestly reconstructable from
    price history alone: the risk-parity base and the regime-alignment
    tilt (Step 10 + the addition this plan's Step 04 built on top of).

    `returns_df`: wide DataFrame, index=dates (ascending), columns=strategy
    names, values=daily simple returns. `benchmark_returns`: Series of the
    regime benchmark's daily simple returns, same date domain.
    """
    if returns_df.empty or not strategies:
        return _empty_result("no returns data or no strategies provided")

    dates = returns_df.index
    if len(dates) <= warmup_days + 1:
        return _empty_result(
            f"need more than warmup_days+1 ({warmup_days + 1}) daily observations, "
            f"got {len(dates)}"
        )

    strategy_dates: list[Any] = []
    strategy_rets: list[float] = []
    equal_weight_rets: list[float] = []
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    n_strategies = len(strategies)

    for i in range(warmup_days, len(dates) - 1):
        as_of = dates[i]
        realize_date = dates[i + 1]

        hist_returns = returns_df.iloc[: i + 1]
        bench_hist = benchmark_returns.loc[:as_of]

        regime_info = classify_current_regime(bench_hist)
        regime = regime_info.get("regime")

        base_weights = service.allocate_risk_parity(strategies, hist_returns)
        base_by_name = {w["name"]: w.get("target_weight", 0.0) for w in base_weights}

        tilted: dict[str, float] = {}
        for s in strategies:
            name = s["name"]
            base_w = base_by_name.get(name, 0.0)
            mult = service._regime_alignment_multiplier(name, regime)
            tilted[name] = base_w * mult

        total = sum(tilted.values())
        if total > 0:
            tilted = {k: v / total for k, v in tilted.items()}
        else:
            tilted = {s["name"]: 1.0 / n_strategies for s in strategies}
            warnings.append(
                f"{as_of}: tilted weights summed to zero, fell back to equal-weight"
            )

        realized = returns_df.loc[realize_date]
        port_ret = sum(
            tilted.get(name, 0.0) * float(realized.get(name, 0.0)) for name in tilted
        )
        eq_ret = float(realized.reindex(returns_df.columns).fillna(0.0).mean())

        strategy_dates.append(realize_date)
        strategy_rets.append(port_ret)
        equal_weight_rets.append(eq_ret)
        records.append({
            "date": str(realize_date),
            "regime": regime,
            "weights": {k: round(v, 4) for k, v in tilted.items()},
            "portfolio_return": round(port_ret, 6),
        })

    strat_series = pd.Series(strategy_rets, index=strategy_dates)
    eq_series = pd.Series(equal_weight_rets, index=strategy_dates)
    bench_aligned = benchmark_returns.reindex(strat_series.index).dropna()

    return SimulationResult(
        status="ok",
        strategy_metrics=compute_performance_metrics(strat_series).to_dict(),
        equal_weight_metrics=compute_performance_metrics(eq_series).to_dict(),
        benchmark_metrics=compute_performance_metrics(bench_aligned).to_dict(),
        daily_records=records,
        start_date=str(dates[warmup_days]),
        end_date=str(dates[-1]),
        n_days=len(records),
        warnings=warnings,
    )


async def fetch_historical_returns(
    service: PortfolioService,
    symbols: list[str],
    days: int = 730,
) -> pd.DataFrame:
    """Daily simple returns per symbol, fetched from vinu-stock-price's
    historical candles endpoint. Requires vinu-stock-price to actually
    have that history backfilled — this function does not fabricate data
    when it's missing, it drops the symbol and logs a warning."""
    series: dict[str, pd.Series] = {}
    for symbol in symbols:
        try:
            resp = await service._http.get(
                f"{service._config.stock_api_url}/stock/candles/{symbol}",
                params={"interval": "1d", "adjusted": True, "days": days},
            )
            if resp.status_code != 200:
                LOG.warning("historical candles unavailable for %s: HTTP %s", symbol, resp.status_code)
                continue
            data = resp.json()
            records = data.get("data") if isinstance(data, dict) else None
            if not records:
                LOG.warning("no historical candle data for %s", symbol)
                continue
            idx = pd.to_datetime([r["bar_ts"] for r in records], unit="s").normalize()
            closes = pd.Series([float(r["close"]) for r in records], index=idx).sort_index()
            closes = closes[~closes.index.duplicated(keep="last")]
            series[symbol] = closes.pct_change().dropna()
        except Exception as exc:
            LOG.warning("failed to fetch historical candles for %s: %s", symbol, exc)

    if not series:
        return pd.DataFrame()
    return pd.concat(series, axis=1).dropna(how="all")


async def fetch_benchmark_returns(
    service: PortfolioService,
    days: int = 730,
) -> pd.Series:
    df = await fetch_historical_returns(service, [service._config.benchmark_symbol], days=days)
    if df.empty or service._config.benchmark_symbol not in df.columns:
        return pd.Series(dtype=float)
    return df[service._config.benchmark_symbol].dropna()
