from __future__ import annotations

import pandas as pd


PERIODS_PER_YEAR: dict[str, int] = {
    "15min": 6552,
    "1H": 1638,
    "1D": 252,
    "1W": 52,
    "1M": 12,
    "6M": 2,
}


def periods_per_year(time_format: str) -> int:
    return PERIODS_PER_YEAR.get(time_format, 252)


def ann_factor(time_format: str) -> float:
    return float(periods_per_year(time_format) ** 0.5)


def bars_to_candle_list(bars: pd.DataFrame | None) -> list[dict]:
    if bars is None or bars.empty:
        return []
    if "bar_ts" not in bars.columns:
        return []
    return bars.to_dict("records")
