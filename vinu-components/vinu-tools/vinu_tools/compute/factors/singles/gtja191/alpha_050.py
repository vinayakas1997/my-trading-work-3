
# ============================================================
# 中文名称: GTJA #50 - 开盘日内动量
# 简要说明: (-1*RANK(CORR(RANK(HIGH),RANK(VOLUME),6))*RANK(CORR(RANK(LOW),RANK(VOLUME),6)))，类似Alpha#48。
# 典型用途: 量价关系的复合反转信号。
# ============================================================
"""GTJA Alpha #50.

Formula: SUM(up_move,12)/(SUM(up_move,12)+SUM(dn_move,12)) - SUM(dn_move,12)/(SUM(up_move,12)+SUM(dn_move,12))
Source: 国泰君安 191 alpha 研报 (2014), alpha 50."""

import numpy as np
import pandas as pd
from .._compat import *  # noqa: F401, F403

__alpha_meta__ = {
    "id": "gtja191_050",
    "theme": ['reversal'],
    "formula_latex": 'SUM(up_move,12)/(SUM(up_move,12)+SUM(dn_move,12)) - SUM(dn_move,12)/(SUM(up_move,12)+SUM(dn_move,12))',
    "columns_required": ['high', 'low'],
    "extras_required": [],
    "requires_sector": False,
    "universe": ["equity_cn"],
    "frequency": ["1d"],
    "decay_horizon": 12,
    "min_warmup_bars": 13,
    "notes": 'Signed version of #49.',
}

def compute(panel: dict, **kwargs) -> pd.DataFrame:
    h = panel["high"]
    l = panel["low"]
    hl = h + l
    phl = h.shift(1) + l.shift(1)
    move = pd.DataFrame(
        np.maximum(np.abs(h.to_numpy() - h.shift(1).to_numpy()),
                   np.abs(l.to_numpy() - l.shift(1).to_numpy())),
        index=h.index, columns=h.columns,
    )
    dn = move.where(hl < phl, 0.0)
    up = move.where(hl > phl, 0.0)
    s_dn = dn.rolling(kwargs.get('window', 12), min_periods=kwargs.get('window_1', 12)).sum()
    s_up = up.rolling(kwargs.get('window_2', 12), min_periods=kwargs.get('window_3', 12)).sum()
    total = s_up + s_dn
    return safe_div(s_up, total) - safe_div(s_dn, total)
