
# ============================================================
# 中文名称: GTJA Alpha #65
# 简要说明: 国泰君安191短周期交易型alpha因子第65号，详见公式定义。
# 典型用途: 在A股市场经中性化处理后用于选股或股指期货日内交易。
# ============================================================
"""GTJA Alpha #65.

Formula: MEAN(CLOSE,6)/CLOSE
Source: 国泰君安 191 alpha 研报 (2014), alpha 65."""

import numpy as np
import pandas as pd
from .._compat import *  # noqa: F401, F403

__alpha_meta__ = {
    "id": "gtja191_065",
    "theme": ['reversal'],
    "formula_latex": 'MEAN(CLOSE,6)/CLOSE',
    "columns_required": ['close'],
    "extras_required": [],
    "requires_sector": False,
    "universe": ["equity_cn"],
    "frequency": ["1d"],
    "decay_horizon": 6,
    "min_warmup_bars": 7,
    "notes": 'MA6 over close.',
}

def compute(panel: dict, **kwargs) -> pd.DataFrame:
    c = panel["close"]
    return safe_div(ts_mean(c, kwargs.get('window', 6)), c)
