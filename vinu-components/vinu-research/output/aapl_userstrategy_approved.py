from __future__ import annotations

import pandas as pd
import numpy as np

from vinu_simulator.engine.strategies import BaseStrategy


class UserStrategy(BaseStrategy):
    def __init__(self, fast_period=None, slow_period=None):
        self.fast_period = fast_period or 20
        self.slow_period = slow_period or 50

    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        fast_ma = data['close'].rolling(int(20)).mean()
        slow_ma = data['close'].rolling(int(50)).mean()
        signal = (fast_ma > slow_ma).astype(int).diff()
        # Session filter: skip London session
        session = data.get('session', pd.Series('ny_regular', index=data.index))
        signal[session == 'london'] = 0
        return signal * 0.98
