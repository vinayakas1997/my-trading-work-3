"""Compact vinu-initial-analysis angle outputs into a small context dict.

The /angle/{name}/{ticker} endpoint returns EVERY stored row across all
historical runs. These pure functions select the latest run, filter by the
research time format, and reduce the rows to a compact dict suitable for
the risk critic rules and the LLM prompt (small, deterministic, no NaN).
"""

from __future__ import annotations

import math
from typing import Any

# Research interval (simulator granularity) -> angle time_format column value
INTERVAL_TO_TIME_FORMAT = {
    "1d": "1D",
    "4h": "4H",
    "1h": "1H",
    "30m": "1H",
    "15m": "15min",
    "5m": "15min",
    "1m": "15min",
    "1w": "1W",
}

_INTRADAY_FORMATS = ("1H", "4H", "15min")


def _val(row: dict[str, Any], key: str) -> Any:
    """Row value with NaN normalized to None (parquet records carry NaN floats)."""
    v = row.get(key)
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _latest_run(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only rows from the most recently stored run.

    Rows are stamped with run_id + stored_at at write time; run_ids are random
    uuids so stored_at (ISO string) is the only chronological key.
    """
    if not rows:
        return []
    stamped = [r for r in rows if _val(r, "stored_at") and _val(r, "run_id")]
    if not stamped:
        return rows
    latest = max(stamped, key=lambda r: str(_val(r, "stored_at")))
    latest_run_id = _val(latest, "run_id")
    return [r for r in rows if _val(r, "run_id") == latest_run_id]


def _filter_tf(rows: list[dict[str, Any]], time_format: str) -> list[dict[str, Any]]:
    """Keep rows matching the time format; rows without the column pass through."""
    return [
        r for r in rows
        if _val(r, "time_format") is None or _val(r, "time_format") == time_format
    ]


def compact_trend_lifecycle(rows: list[dict[str, Any]], time_format: str = "1D") -> dict[str, Any] | None:
    rows = _filter_tf(_latest_run(rows), time_format)
    if not rows:
        return None
    out: dict[str, Any] = {}
    lifecycle = [r for r in rows if _val(r, "type") == "lifecycle"]
    if lifecycle:
        lc = lifecycle[-1]
        out["stage"] = _val(lc, "stage")
        out["risk"] = _val(lc, "risk")
        out["description"] = _val(lc, "description")
    summary = [r for r in rows if _val(r, "type") == "summary"]
    if summary:
        s = summary[-1]
        out["dominant_signal"] = _val(s, "dominant_signal")
        out["total_peaks"] = _val(s, "total_peaks")
        out["current_risk"] = _val(s, "current_risk")
    signals = [r for r in rows if _val(r, "type") == "signal"]
    if signals:
        best = max(signals, key=lambda r: _val(r, "confidence") or 0.0)
        out["signal"] = {
            k: _val(best, k)
            for k in ("signal_type", "confidence", "suggested_action",
                      "avg_drawdown_pct", "exit_threshold_pct")
        }
    return out or None


def compact_session_structure(rows: list[dict[str, Any]], time_format: str = "1H") -> dict[str, Any] | None:
    """Session stats exist only for intraday formats. Prefer the requested
    format; fall back to any intraday format present (labeled) so daily
    research still sees intraday session structure."""
    run_rows = _latest_run(rows)
    selected = _filter_tf(run_rows, time_format)
    used_tf = time_format
    if not [r for r in selected if _val(r, "type") == "session_stats"]:
        for tf in _INTRADAY_FORMATS:
            if tf == time_format:
                continue
            candidate = [r for r in run_rows if _val(r, "time_format") == tf]
            if [r for r in candidate if _val(r, "type") == "session_stats"]:
                selected = candidate
                used_tf = tf
                break
    stats = [r for r in selected if _val(r, "type") == "session_stats"]
    summaries = [r for r in selected if _val(r, "type") == "summary"]
    if not stats and not summaries:
        return None
    out: dict[str, Any] = {"time_format": used_tf}
    if summaries:
        s = summaries[-1]
        for k in ("status", "best_session", "worst_session", "n_qualifying_sessions"):
            out[k] = _val(s, k)
    out["sessions"] = [
        {
            k: _val(r, k)
            for k in ("session", "n_peaks", "n_mature_peaks", "meets_floor",
                      "avg_drawdown_pct", "recovery_rate")
        }
        for r in stats
    ]
    return out


def compact_news_causality(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    rows = _latest_run(rows)
    if not rows:
        return None
    out: dict[str, Any] = {}
    typed_keys = (
        ("granger", ("granger_causes_prices", "best_lag_minutes", "p_value", "sample_size")),
        ("correlation", ("news_return_corr", "corr_p_value", "sentiment_return_corr", "news_volume_corr")),
        ("lag", ("best_lag_minutes", "best_lag_correlation")),
    )
    for row_type, keys in typed_keys:
        matching = [r for r in rows if _val(r, "type") == row_type]
        if matching:
            for k in keys:
                v = _val(matching[-1], k)
                if v is not None:
                    out[k] = v
    return out or None


def compact_backtesting_metrics(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    rows = _latest_run(rows)
    if not rows:
        return None
    r = rows[-1]
    return {
        k: _val(r, k) for k in (
            "sharpe_ratio", "sortino_ratio", "max_drawdown", "calmar_ratio",
            "win_rate", "var_95", "cvar_95", "skewness", "kurtosis",
        ) if _val(r, k) is not None
    } or None


def format_angle_context_lines(angles: dict[str, Any]) -> list[str]:
    """Render a compact `story["angles"]` dict as prompt lines.

    Shared by the risk-critic prompt and the strategy-generator prompt so both
    LLM consumers see the same deterministic angle signals in the same format.
    """
    lines: list[str] = []
    if not angles:
        return lines
    lines.append("")
    lines.append("Deterministic Angle Analysis:")
    tl = angles.get("trend_lifecycle")
    if tl:
        lines.append(
            f"  Trend lifecycle: stage={tl.get('stage')}, risk={tl.get('risk')}, "
            f"dominant_signal={tl.get('dominant_signal')}"
        )
        sig = tl.get("signal") or {}
        if sig:
            lines.append(
                f"    Latest peak signal: {sig.get('signal_type')} "
                f"(confidence {sig.get('confidence')}): {sig.get('suggested_action')}"
            )
    ss = angles.get("session_structure")
    if ss:
        lines.append(
            f"  Session structure ({ss.get('time_format')}): "
            f"best={ss.get('best_session')}, worst={ss.get('worst_session')}, "
            f"qualifying sessions={ss.get('n_qualifying_sessions')}"
        )
        for s in (ss.get("sessions") or [])[:4]:
            if s.get("meets_floor"):
                lines.append(
                    f"    {s.get('session')}: {s.get('n_peaks')} peaks, "
                    f"avg drawdown {s.get('avg_drawdown_pct')}, "
                    f"recovery rate {s.get('recovery_rate')}"
                )
    nc = angles.get("news_causality")
    if nc:
        lines.append(
            f"  News causality: granger={nc.get('granger_causes_prices')}, "
            f"lag={nc.get('best_lag_minutes')}min, p={nc.get('p_value')}, "
            f"news-return corr={nc.get('news_return_corr')}"
        )
    bm = angles.get("backtesting_metrics")
    if bm:
        lines.append(
            f"  Risk metrics: Sharpe={bm.get('sharpe_ratio')}, "
            f"Sortino={bm.get('sortino_ratio')}, MaxDD={bm.get('max_drawdown')}, "
            f"Calmar={bm.get('calmar_ratio')}, WinRate={bm.get('win_rate')}"
        )
        lines.append(
            f"    Tail risk: VaR95={bm.get('var_95')}, CVaR95={bm.get('cvar_95')}, "
            f"Skew={bm.get('skewness')}, Kurt={bm.get('kurtosis')}"
        )
    return lines


def build_angle_context(
    trend_rows: list[dict[str, Any]] | None,
    session_rows: list[dict[str, Any]] | None,
    causality_rows: list[dict[str, Any]] | None,
    backtesting_rows: list[dict[str, Any]] | None = None,
    interval: str = "1d",
) -> dict[str, Any]:
    """Build the compact `story["angles"]` dict from raw /angle endpoint records."""
    tf = INTERVAL_TO_TIME_FORMAT.get(str(interval).lower(), "1D")
    ctx: dict[str, Any] = {}
    tl = compact_trend_lifecycle(trend_rows or [], tf)
    if tl:
        ctx["trend_lifecycle"] = tl
    ss = compact_session_structure(session_rows or [], tf)
    if ss:
        ctx["session_structure"] = ss
    nc = compact_news_causality(causality_rows or [])
    if nc:
        ctx["news_causality"] = nc
    bm = compact_backtesting_metrics(backtesting_rows or [])
    if bm:
        ctx["backtesting_metrics"] = bm
    return ctx
