"""Drawdown Deep-Dive — detect drawdowns, attribute to news, compute recovery time."""

import pandas as pd
from datetime import datetime, timezone

from vinu_initial_analysis.angles._helpers import bars_to_candle_list
from .drawdown import get_drawdowns, attribute_drawdown


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    now = datetime.now(timezone.utc).isoformat()
    candles = bars_to_candle_list(bars)
    articles = news or []
    rows: list[dict] = []

    if not candles:
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "drawdown_deep_dive",
            "type": "status", "drawdown_count": 0, "max_drop_pct": 0.0,
        })
        return pd.DataFrame(rows)

    # Detect all drawdowns
    dd_list = get_drawdowns(symbol, candles, from_ts=from_ts, to_ts=to_ts, drop_threshold_pct=-2.0)
    max_drop = 0.0
    for dd in dd_list:
        dd["analysis_at"] = now
        dd["angle"] = "drawdown_deep_dive"
        dd["type"] = "drawdown"
        rows.append(dd)
        max_drop = min(max_drop, dd["drop_pct"])

    # Attribution for the worst drawdown
    if dd_list:
        worst = min(dd_list, key=lambda d: d["drop_pct"])
        attr = attribute_drawdown(symbol, worst["peak_ts"], worst["trough_ts"], articles)
        rows.append({
            "symbol": symbol, "analysis_at": now, "angle": "drawdown_deep_dive",
            "type": "attribution",
            "peak_ts": worst["peak_ts"],
            "trough_ts": worst["trough_ts"],
            "drop_pct": worst["drop_pct"],
            "news_driven_pct": attr["attribution"]["news_driven_pct"],
            "market_beta_pct": attr["attribution"]["market_beta_pct"],
            "unexplained_pct": attr["attribution"]["unexplained_pct"],
            "contributing_events": len(attr["attribution"]["contributing_events"]),
        })

    # Summary row
    total_dd = len(dd_list)
    rows.append({
        "symbol": symbol, "analysis_at": now, "angle": "drawdown_deep_dive",
        "type": "summary",
        "drawdown_count": total_dd,
        "max_drop_pct": round(max_drop, 2),
    })

    return pd.DataFrame(rows) if rows else pd.DataFrame()
