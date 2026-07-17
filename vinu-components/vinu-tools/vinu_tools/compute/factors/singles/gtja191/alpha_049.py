
# ============================================================
# 中文名称: GTJA #49 - 指数平滑量比
# 简要说明: SUM((HIGH+LOW+CLOSE+OPEN)*0.25*VOLUME,12)/SUM(VOLUME,12)，12日成交量加权的平均价格。
# 典型用途: 量价加权平均价格，反映资金流动的方向和力度。
# ============================================================
"""GTJA Alpha #49.

Formula: SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(...,12)+SUM(...,12))
Source: 国泰君安 191 alpha 研报 (2014), alpha 49."""

import numpy as np
import pandas as pd
from .._compat import *  # noqa: F401, F403

__alpha_meta__ = {
    "id": "gtja191_049",
    "theme": ['reversal'],
    "formula_latex": 'SUM(((HIGH+LOW)>=(DELAY(HIGH,1)+DELAY(LOW,1))?0:MAX(ABS(HIGH-DELAY(HIGH,1)),ABS(LOW-DELAY(LOW,1)))),12)/(SUM(...,12)+SUM(...,12))',
    "columns_required": ['high', 'low'],
    "extras_required": [],
    "requires_sector": False,
    "universe": ["equity_cn"],
    "frequency": ["1d"],
    "decay_horizon": 12,
    "min_warmup_bars": 13,
    "notes": 'Down-side range as share of total range over 12 days.',
}

def compute(panel: dict, **kwargs) -> pd.DataFrame:
    h = panel["high"]
    l = panel["low"]
    hl = h + l
    phl = h.shift(kwargs.get('lag', 1)) + l.shift(kwargs.get('lag_1', 1))
    move = pd.DataFrame(
        np.maximum(np.abs(h.to_numpy() - h.shift(kwargs.get('lag_2', 1)).to_numpy()),
                   np.abs(l.to_numpy() - l.shift(kwargs.get('lag_3', 1)).to_numpy())),
        index=h.index, columns=h.columns,
    )
    dn = move.where(hl < phl, 0.0)
    up = move.where(hl > phl, 0.0)
    s_dn = dn.rolling(kwargs.get('window_2', 12), min_periods=kwargs.get('window_3', 12)).sum()
    s_up = up.rolling(kwargs.get('window_5', 12), min_periods=12).sum()
    return safe_div(s_dn, s_dn + s_up)
