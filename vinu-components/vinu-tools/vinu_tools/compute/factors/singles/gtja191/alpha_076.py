
# ============================================================
# 中文名称: GTJA Alpha #76
# 简要说明: 国泰君安191短周期交易型alpha因子第76号，详见公式定义。
# 典型用途: 在A股市场经中性化处理后用于选股或股指期货日内交易。
# ============================================================
"""GTJA Alpha #76.

Formula: STD(ABS((CLOSE/DELAY(CLOSE,1)-1))/VOLUME,20)/MEAN(ABS((CLOSE/DELAY(CLOSE,1)-1))/VOLUME,20)
Source: 国泰君安 191 alpha 研报 (2014), alpha 76."""

import numpy as np
import pandas as pd
from .._compat import *  # noqa: F401, F403

__alpha_meta__ = {
    "id": "gtja191_076",
    "theme": ['volatility', 'volume'],
    "formula_latex": 'STD(ABS((CLOSE/DELAY(CLOSE,1)-1))/VOLUME,20)/MEAN(ABS((CLOSE/DELAY(CLOSE,1)-1))/VOLUME,20)',
    "columns_required": ['close', 'volume'],
    "extras_required": [],
    "requires_sector": False,
    "universe": ["equity_cn"],
    "frequency": ["1d"],
    "decay_horizon": 20,
    "min_warmup_bars": 22,
    "notes": 'Coefficient-of-variation of |daily return|/volume over 20 days.',
}

def compute(panel: dict, **kwargs) -> pd.DataFrame:
    c = panel["close"]
    v = panel["volume"]
    x = safe_div((safe_div(c, c.shift(kwargs.get('lag', 1))) - kwargs.get('lag_1', 1.0)).abs(), v)
    return safe_div(ts_std(x, kwargs.get('window_2', 20)), ts_mean(x, kwargs.get('window_3', 20)))
