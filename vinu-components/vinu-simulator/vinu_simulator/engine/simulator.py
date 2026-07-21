from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_simulator.engine.costs import (
    AlmgrenChrissCostModel,
    CostModel,
    FlatCostModel,
)
from vinu_simulator.engine.metrics import (
    compute_full_metrics,
    compute_performance_metrics,
    periods_per_year_for_interval,
)
from vinu_simulator.engine.sizing import PositionSizer, build_position_sizer
from vinu_simulator.models.metrics import MetricBundle
from vinu_simulator.models.simulation import (
    SimulationConfig,
    SimulationInput,
    SimulationResult,
    TradeRecord,
)


class WeightSimulator:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self._cost_model = self._build_cost_model()
        self._position_sizer = self._build_position_sizer()

    def _build_cost_model(self) -> CostModel:
        if self.config.slippage_model == "almgren_chriss":
            return AlmgrenChrissCostModel(
                fixed_cost_pct=self.config.transaction_cost_pct,
                slippage_pct=self.config.slippage_pct,
            )
        if self.config.slippage_model == "flat":
            return FlatCostModel(
                cost_pct=self.config.transaction_cost_pct,
                slippage_pct=self.config.slippage_pct,
            )
        raise ValueError(f"Unknown slippage_model: {self.config.slippage_model}")

    def _build_position_sizer(self) -> PositionSizer:
        return build_position_sizer(
            self.config.position_sizing_model,
            target_annual_vol=self.config.target_annual_vol,
            vol_lookback_days=self.config.vol_lookback_days,
            kelly_fraction=self.config.kelly_fraction,
            kelly_lookback_days=self.config.kelly_lookback_days,
            max_leverage=self.config.max_leverage,
        )

    def run(self, inp: SimulationInput) -> SimulationResult:
        weight_signals = inp.weight_signals.copy()
        price_data = inp.price_data.copy()
        volume_data = inp.volume_data.copy() if inp.volume_data is not None else None

        if not isinstance(weight_signals.index, pd.DatetimeIndex):
            weight_signals.index = pd.to_datetime(weight_signals.index)
        if not isinstance(price_data.index, pd.DatetimeIndex):
            price_data.index = pd.to_datetime(price_data.index)

        weight_signals = weight_signals.sort_index()
        price_data = price_data.sort_index()
        if volume_data is not None:
            volume_data = volume_data.sort_index()

        common_tickers = [c for c in weight_signals.columns if c in price_data.columns]
        if not common_tickers:
            raise ValueError("No common tickers between weight signals and price data")
        missing = set(weight_signals.columns) - set(common_tickers)
        if missing:
            weight_signals = weight_signals[common_tickers]

        weight_signals = weight_signals[common_tickers]
        total_calendar = price_data.index.union(weight_signals.index)
        price_data = price_data.reindex(total_calendar).ffill()
        if price_data.isna().any(axis=None):
            nan_dates = price_data.index[price_data.isna().any(axis=1)].tolist()
            nan_cols = price_data.columns[price_data.isna().any(axis=0)].tolist()
            raise ValueError(
                f"Prices contain NaN after forward-fill on dates {nan_dates}"
                f" for tickers {nan_cols}. Data does not cover full calendar range."
            )
        price_data = price_data[common_tickers]
        if volume_data is not None:
            volume_data = volume_data.reindex(total_calendar).ffill().fillna(0.0)
            volume_data = volume_data[common_tickers]

        ws_aligned = weight_signals.reindex(total_calendar).ffill().fillna(0.0)

        # T+1 execution: a signal observed using data through day D can only be acted on
        # starting day D+1 — a real order can't fill at the same close that produced the
        # signal. Shift the whole weight series forward by one row (one trading day in the
        # ordered calendar) so the weight applied on day D was decided using information
        # available through day D-1. Without this shift, the engine fills trades at the
        # exact price that produced the signal, which is look-ahead bias.
        target_weights_aligned = ws_aligned.shift(1).fillna(0.0)

        calendar_positions = {date: idx for idx, date in enumerate(total_calendar)}
        signal_positions = {
            calendar_positions[d] for d in weight_signals.index if d in calendar_positions
        }
        # A rebalance executes on day D if a new signal was set on day D-1 (the signal
        # now being acted on, one day late by construction).
        rebalance_positions = {p + 1 for p in signal_positions if p + 1 < len(total_calendar)}

        config = inp.config
        n = len(common_tickers)
        cash = config.initial_capital
        holdings = np.zeros(n, dtype=np.float64)
        portfolio_value = config.initial_capital
        prev_value = portfolio_value

        equity_curve: list[float] = []
        daily_ret: list[float] = []
        weights_hist: list[np.ndarray] = []
        trades: list[TradeRecord] = []

        # Pre-extract to numpy once, outside the loop. price_data / volume_data /
        # target_weights_aligned are all already reindexed to total_calendar in the
        # same row order, so integer position lookups here match `enumerate` exactly
        # — this avoids paying a `.loc[date]` label lookup 2-3x per day, every day,
        # on every backtest the system runs.
        price_matrix = price_data.values.astype(np.float64)
        volume_matrix = volume_data.values.astype(np.float64) if volume_data is not None else None
        weights_matrix = target_weights_aligned.values.astype(np.float64)

        for step_idx, date in enumerate(total_calendar):
            prices = price_matrix[step_idx]
            if np.any(~np.isfinite(prices)):
                raise ValueError(f"NaN/Inf prices on {date}")
            volumes = volume_matrix[step_idx] if volume_matrix is not None else None

            if config.allow_short:
                short_notional = float(np.sum(np.abs(np.minimum(holdings, 0.0)) * prices))
                if short_notional > 0:
                    cash -= self._cost_model.daily_borrow_cost(short_notional)

            nav_before = cash + np.sum(holdings * prices)
            # Scale by realized performance strictly before today (daily_ret holds
            # only returns already realized at this point in the loop) — direction
            # always comes from the strategy, sizing only ever adjusts magnitude.
            target_weights = self._position_sizer.size(
                weights_matrix[step_idx], np.asarray(daily_ret, dtype=np.float64)
            )

            is_rebalance = step_idx in rebalance_positions
            if is_rebalance:
                current_values = holdings * prices
                current_weights = np.zeros(n, dtype=np.float64)
                if nav_before > 0:
                    current_weights = current_values / nav_before

                rebalance_weights = target_weights.copy()
                if not config.allow_short:
                    rebalance_weights = np.maximum(rebalance_weights, 0.0)
                    wsum = rebalance_weights.sum()
                    if wsum > 0:
                        rebalance_weights = rebalance_weights / wsum

                deviation = np.abs(rebalance_weights - current_weights).sum()
                if not np.isfinite(deviation):
                    continue
                if deviation > config.deviation_threshold:
                    sell_order = np.argsort(current_weights - rebalance_weights)[::-1]
                    for idx in sell_order:
                        delta = rebalance_weights[idx] - current_weights[idx]
                        if delta >= 0:
                            continue
                        if prices[idx] <= 0:
                            continue
                        shares_to_sell = -delta * nav_before / prices[idx]
                        if not config.allow_short:
                            shares_to_sell = min(shares_to_sell, holdings[idx])
                        if not np.isfinite(shares_to_sell):
                            continue
                        if shares_to_sell <= 1e-12:
                            continue
                        vol = float(volumes[idx]) if volumes is not None else None
                        if vol is not None and vol > 0 and config.max_pct_of_volume < 1.0:
                            shares_to_sell = min(shares_to_sell, vol * config.max_pct_of_volume)
                        proceeds = self._cost_model.sell_proceeds(
                            float(prices[idx]), float(shares_to_sell), volume=vol
                        )
                        cash += proceeds
                        holdings[idx] -= shares_to_sell

                        trades.append(TradeRecord(
                            date=date,
                            symbol=common_tickers[idx],
                            side="SELL",
                            shares=float(shares_to_sell),
                            price=float(prices[idx]),
                            cost=float(shares_to_sell * prices[idx] - proceeds),
                            weight_before=float(current_weights[idx]),
                            weight_after=float(rebalance_weights[idx]),
                        ))

                    nav_after_sells = cash + np.sum(holdings * prices)
                    target_values = nav_after_sells * rebalance_weights

                    for idx in range(n):
                        delta = rebalance_weights[idx] - current_weights[idx]
                        if delta <= 0:
                            continue
                        if prices[idx] <= 0:
                            continue
                        target_shares = target_values[idx] / prices[idx]
                        current_shares = holdings[idx]
                        shares_to_buy = target_shares - current_shares
                        if not np.isfinite(shares_to_buy):
                            continue
                        if shares_to_buy <= 1e-12:
                            continue
                        vol = float(volumes[idx]) if volumes is not None else None
                        if vol is not None and vol > 0 and config.max_pct_of_volume < 1.0:
                            shares_to_buy = min(shares_to_buy, vol * config.max_pct_of_volume)
                        cost = self._cost_model.buy_cost(
                            float(prices[idx]), float(shares_to_buy), volume=vol
                        )
                        # A target of exactly 100% notional leaves no room for fees/
                        # slippage/impact, so `cost` lands just above `cash` and the
                        # order would silently never fill — every step, forever, on
                        # any fully-invested strategy. Shrink toward whatever size
                        # actually fits instead of dropping the order.
                        for _ in range(5):
                            if cost <= cash or shares_to_buy <= 1e-12:
                                break
                            shares_to_buy *= cash / cost
                            cost = self._cost_model.buy_cost(
                                float(prices[idx]), float(shares_to_buy), volume=vol
                            )
                        if cost <= cash:
                            cash -= cost
                            holdings[idx] += shares_to_buy
                            trades.append(TradeRecord(
                                date=date,
                                symbol=common_tickers[idx],
                                side="BUY",
                                shares=float(shares_to_buy),
                                price=float(prices[idx]),
                                cost=float(cost - shares_to_buy * prices[idx]),
                                weight_before=float(current_weights[idx]),
                                weight_after=float(rebalance_weights[idx]),
                            ))

            nav_after = cash + np.sum(holdings * prices)
            if nav_after <= 0:
                nav_after = 0.0

            equity_curve.append(float(nav_after))
            ret = (nav_after / prev_value - 1) if prev_value > 0 else 0.0
            if step_idx > 0:
                daily_ret.append(float(ret))
            prev_value = nav_after

            w = np.where(nav_after > 0, holdings * prices / nav_after, 0.0)
            weights_hist.append(w)

        portfolio_values_s = pd.Series(equity_curve, index=total_calendar, name="portfolio_value")
        daily_returns_s = pd.Series(daily_ret, index=total_calendar[1:], name="daily_return")
        weights_history_df = pd.DataFrame(
            np.stack(weights_hist),
            index=total_calendar,
            columns=common_tickers,
        )

        metrics = compute_full_metrics(
            portfolio_values_s, daily_returns_s,
            trades=trades,
            risk_free_rate=config.risk_free_rate_annual,
            periods_per_year=periods_per_year_for_interval(config.interval),
            full=config.full_metrics,
        )

        run_id = str(uuid.uuid4())

        return SimulationResult(
            strategy_name=inp.strategy_name,
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            config=deepcopy(self.config),
            portfolio_values=portfolio_values_s,
            daily_returns=daily_returns_s,
            weights_history=weights_history_df,
            trades=trades,
            metrics=metrics,
        )


class SimulatorEnv:
    def __init__(
        self,
        tickers: list[str],
        price_data: pd.DataFrame,
        config: SimulationConfig,
    ):
        self.tickers = tickers
        self.price_data = price_data.sort_index()
        self.config = config
        # Reuse WeightSimulator's selector so this env can't silently diverge from the
        # cost model production backtests actually use.
        self._cost_model = WeightSimulator(config)._build_cost_model()

        self.dates = self.price_data.index.tolist()
        self.n = len(tickers)
        self._step_idx = 0
        self.cash = config.initial_capital
        self.holdings = np.zeros(self.n, dtype=np.float64)
        self.portfolio_value = config.initial_capital
        self._prev_value = config.initial_capital
        self._equity_curve: list[float] = [config.initial_capital]
        self._weights_history: list[np.ndarray] = []

    def reset(self, seed: int | None = None) -> np.ndarray:
        self._step_idx = 0
        self.cash = self.config.initial_capital
        self.holdings = np.zeros(self.n, dtype=np.float64)
        self.portfolio_value = self.config.initial_capital
        self._prev_value = self.config.initial_capital
        self._equity_curve = [self.config.initial_capital]
        self._weights_history = []
        return self._state()

    def _state(self) -> np.ndarray:
        prices = self.price_data.iloc[self._step_idx].values.astype(np.float64)
        current_weights = np.zeros(self.n, dtype=np.float64)
        if self.portfolio_value > 0:
            current_weights = (self.holdings * prices) / self.portfolio_value
        cash_weight = self.cash / self.portfolio_value if self.portfolio_value > 0 else 1.0
        return np.concatenate([current_weights, [cash_weight], prices])

    def step(self, target_weights: np.ndarray) -> tuple[np.ndarray, float, bool, dict[str, Any]]:
        if self._step_idx >= len(self.dates) - 1:
            return self._state(), 0.0, True, {}

        date = self.dates[self._step_idx]
        prices = self.price_data.loc[date].values.astype(np.float64)
        if np.any(~np.isfinite(prices)):
            raise ValueError(f"NaN/Inf prices on {date}")
        nav_before = self.cash + np.sum(self.holdings * prices)

        target_weights = np.asarray(target_weights, dtype=np.float64)
        target_weights = target_weights / max(np.abs(target_weights).sum(), 1e-12)

        rebalance_weights = target_weights.copy()
        if not self.config.allow_short:
            rebalance_weights = np.maximum(rebalance_weights, 0.0)
            wsum = rebalance_weights.sum()
            if wsum > 0:
                rebalance_weights = rebalance_weights / wsum

        current_values = self.holdings * prices
        current_weights = np.zeros(self.n, dtype=np.float64)
        if nav_before > 0:
            current_weights = current_values / nav_before

        deviation = np.abs(rebalance_weights - current_weights).sum()
        if not np.isfinite(deviation):
            raise ValueError(f"Non-finite deviation {deviation} on {date}")
        if deviation > self.config.deviation_threshold:
            sell_order = np.argsort(current_weights - rebalance_weights)[::-1]
            for idx in sell_order:
                delta = rebalance_weights[idx] - current_weights[idx]
                if delta >= 0:
                    continue
                if prices[idx] <= 0:
                    continue
                shares_to_sell = -delta * nav_before / prices[idx]
                if not self.config.allow_short:
                    shares_to_sell = min(shares_to_sell, self.holdings[idx])
                if not np.isfinite(shares_to_sell):
                    continue
                if shares_to_sell <= 1e-12:
                    continue
                proceeds = self._cost_model.sell_proceeds(
                    float(prices[idx]), float(shares_to_sell)
                )
                self.cash += proceeds
                self.holdings[idx] -= shares_to_sell

            nav_after_sells = self.cash + np.sum(self.holdings * prices)
            target_values = nav_after_sells * rebalance_weights

            for idx in range(self.n):
                delta = rebalance_weights[idx] - current_weights[idx]
                if delta <= 0:
                    continue
                if prices[idx] <= 0:
                    continue
                target_shares = target_values[idx] / prices[idx]
                shares_to_buy = target_shares - self.holdings[idx]
                if not np.isfinite(shares_to_buy):
                    continue
                if shares_to_buy <= 1e-12:
                    continue
                cost = self._cost_model.buy_cost(
                    float(prices[idx]), float(shares_to_buy)
                )
                for _ in range(5):
                    if cost <= self.cash or shares_to_buy <= 1e-12:
                        break
                    shares_to_buy *= self.cash / cost
                    cost = self._cost_model.buy_cost(
                        float(prices[idx]), float(shares_to_buy)
                    )
                if cost <= self.cash:
                    self.cash -= cost
                    self.holdings[idx] += shares_to_buy

        self._step_idx += 1
        next_date = self.dates[self._step_idx]
        next_prices = self.price_data.loc[next_date].values.astype(np.float64)

        nav_after = self.cash + np.sum(self.holdings * next_prices)
        self.portfolio_value = max(nav_after, 0.0)
        reward = (self.portfolio_value / max(self._prev_value, 1e-12)) - 1
        self._prev_value = self.portfolio_value
        self._equity_curve.append(float(self.portfolio_value))

        w = np.where(
            self.portfolio_value > 0,
            self.holdings * next_prices / self.portfolio_value,
            0.0,
        )
        self._weights_history.append(w)

        done = self._step_idx >= len(self.dates) - 1
        return self._state(), float(reward), done, {}

    @property
    def equity_curve(self) -> pd.Series:
        return pd.Series(
            self._equity_curve,
            index=self.dates[: len(self._equity_curve)],
            name="portfolio_value",
        )

    @property
    def daily_returns(self) -> pd.Series:
        vals = pd.Series(self._equity_curve)
        rets = vals.pct_change().dropna()
        return pd.Series(
            rets.values,
            index=self.dates[1 : len(rets) + 1],
            name="daily_return",
        )

    def metrics(self) -> dict[str, float]:
        return compute_performance_metrics(
            self.equity_curve, self.daily_returns,
            periods_per_year=periods_per_year_for_interval(self.config.interval),
        )
