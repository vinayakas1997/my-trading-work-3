from __future__ import annotations
import pandas as pd
import numpy as np
from vinu_simulator.engine.strategies import BaseStrategy

class UserStrategy(BaseStrategy):
    def __init__(self, rsi_entry_thresh: float = 40.0, vol_ma_period: int = 20,
                 atr_period: int = 14, rr_ratio: float = 1.5, pullback_tol: float = 0.005,
                 regime_div_thresh: float = 0.015):
        self.rsi_entry_thresh = rsi_entry_thresh
        self.vol_ma_period = vol_ma_period
        self.atr_period = atr_period
        self.rr_ratio = rr_ratio
        self.pullback_tol = pullback_tol
        self.regime_div_thresh = regime_div_thresh

    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        # Derived metrics
        atr = (data['high'] - data['low']).rolling(self.atr_period).mean()
        vol_ma = data['volume'].rolling(self.vol_ma_period).mean()
        sma20 = data['sma_20']
        sma50 = data['sma_50']
        rsi = data['rsi_14']

        # Basing regime filter (low SMA divergence)
        sma_div = abs(sma20 - sma50) / sma50.replace(0, np.nan)
        is_basing = sma_div < self.regime_div_thresh

        # Entry: pullback to SMA20, RSI dip, volume contraction
        pullback = data['close'] <= sma20 * (1 + self.pullback_tol)
        rsi_dip = rsi < self.rsi_entry_thresh
        vol_contract = data['volume'] < vol_ma
        entry_long = is_basing & pullback & rsi_dip & vol_contract

        # Scale-in: breakout above recent peak with volume expansion
        recent_peak = data['close'].rolling(self.vol_ma_period).max()
        vol_expand = data['volume'] > vol_ma
        scale_in = (data['close'] > recent_peak) & vol_expand & is_basing

        # Exit: close below support floor (rolling min low)
        support_floor = data['low'].rolling(self.vol_ma_period).min()
        exit_long = data['close'] < support_floor

        # Assign weights with priority: exit > scale-in > entry
        conditions = [exit_long, scale_in, entry_long]
        choices = [0.0, 1.0, 0.5]
        weights = pd.Series(np.select(conditions, choices, default=0.0), index=data.index)

        # Handle NaNs and clamp to [-1, 1]
        return weights.fillna(0.0).clip(-1.0, 1.0)