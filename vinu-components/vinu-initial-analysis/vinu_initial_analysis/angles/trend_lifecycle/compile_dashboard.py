"""Dashboard compiler — generates a standalone HTML file for visual inspection.

Reads the stock's OHLCV Parquet and the trend_lifecycle output Parquet,
merges them, and embeds everything into a single self-contained HTML file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

from vinu_initial_analysis.config import load_config
from vinu_initial_analysis.storage.parquet import AngleStorage

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trend Lifecycle Dashboard - {symbol} ({time_format})</title>
<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', 'Segoe UI', sans-serif; background: #1a1f2e; color: #e0e0e0; display: flex; height: 100vh; overflow: hidden; }}
#chart {{ flex: 7; height: 100vh; min-width: 0; }}
#sidebar {{ flex: 3; height: 100vh; overflow-y: auto; background: #141826; border-left: 1px solid #2a2f42; padding: 16px; }}
.section-title {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #6b7280; margin: 16px 0 8px; border-bottom: 1px solid #2a2f42; padding-bottom: 4px; }}
.metric-group {{ margin-bottom: 12px; }}
.metric-row {{ display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }}
.metric-label {{ color: #9ca3af; }}
.metric-value {{ color: #f0f0f0; font-weight: 500; font-variant-numeric: tabular-nums; }}
.match-card {{ background: #1e2337; border-radius: 6px; padding: 10px; margin-bottom: 8px; border-left: 3px solid #ef4444; }}
.match-card .match-date {{ color: #9ca3af; font-size: 11px; }}
.match-card .match-sim {{ color: #22c55e; font-size: 14px; font-weight: 700; }}
.match-card .match-dd {{ color: #ef4444; font-size: 13px; }}
.signal-box {{ background: #1e2337; border-radius: 6px; padding: 12px; margin-top: 12px; border-left: 3px solid #f59e0b; }}
.signal-box.high {{ border-left-color: #ef4444; }}
.signal-box.low {{ border-left-color: #22c55e; }}
.signal-action {{ font-size: 13px; color: #f0f0f0; margin-top: 4px; line-height: 1.4; }}
.status-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
.status-badge.uptrend {{ background: #166534; color: #86efac; }}
.status-badge.topping {{ background: #7c2d12; color: #fdba74; }}
.status-badge.downtrend {{ background: #7f1d1d; color: #fca5a5; }}
.status-badge.basing {{ background: #1e3a5f; color: #93c5fd; }}
.click-hint {{ color: #6b7280; font-size: 12px; text-align: center; padding: 40px 0; }}
</style>
</head>
<body>
<div id="chart"></div>
<div id="sidebar">
  <div id="sidebar-content">
    <div class="click-hint">Click a peak/trough marker on the chart to inspect its full fingerprint.</div>
  </div>
</div>
<script>
const DATA = {data_json};
const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
  layout: {{ background: {{ color: '#1a1f2e' }}, textColor: '#9ca3af' }},
  grid: {{ vertLines: {{ color: '#2a2f42' }}, horzLines: {{ color: '#2a2f42' }} }},
  crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
  rightPriceScale: {{ borderColor: '#2a2f42' }},
  timeScale: {{ borderColor: '#2a2f42', timeVisible: true, secondsVisible: false }},
}});

const candleSeries = chart.addCandlestickSeries({{
  upColor: '#22c55e', downColor: '#ef4444', borderDownColor: '#ef4444',
  borderUpColor: '#22c55e', wickDownColor: '#ef4444', wickUpColor: '#22c55e',
}});
candleSeries.setData(DATA.candles);

function toChartTime(ts) {{
  const d = new Date(ts * 1000);
  return {{ year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() }};
}}

const markers = [];
DATA.peaks.forEach(p => {{
  markers.push({{ time: toChartTime(p.time), position: 'aboveBar', color: '#ef4444', shape: 'arrowDown', size: 1, text: '▼' }});
}});
DATA.troughs.forEach(t => {{
  markers.push({{ time: toChartTime(t.time), position: 'belowBar', color: '#22c55e', shape: 'arrowUp', size: 1, text: '▲' }});
}});
markers.sort((a, b) => {{
  const ta = a.time.year * 10000 + a.time.month * 100 + a.time.day;
  const tb = b.time.year * 10000 + b.time.month * 100 + b.time.day;
  return ta - tb;
}});
candleSeries.setMarkers(markers);

const volumeSeries = chart.addHistogramSeries({{
  priceFormat: {{ type: 'volume' }},
  priceScaleId: 'volume',
}});
chart.priceScale('volume').applyOptions({{
  scaleMargins: {{ top: 0.85, bottom: 0 }},
}});
if (DATA.volumes) volumeSeries.setData(DATA.volumes);

if (DATA.sma50) {{
  const sma50 = chart.addLineSeries({{ color: '#f59e0b', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }});
  sma50.setData(DATA.sma50);
}}
if (DATA.sma200) {{
  const sma200 = chart.addLineSeries({{ color: '#8b5cf6', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }});
  sma200.setData(DATA.sma200);
}}

chart.subscribeClick(param => {{
  if (!param || !param.time) return;
  let clickTs;
  if (typeof param.time === 'object') {{
    const d = new Date(Date.UTC(param.time.year, param.time.month - 1, param.time.day));
    clickTs = Math.floor(d.getTime() / 1000);
  }} else {{
    clickTs = Number(param.time);
  }}
  // Find nearest snapshot within 3 days tolerance
  let bestKey = null, bestDiff = Infinity;
  Object.keys(DATA.snapshots_by_ts).forEach(k => {{
    const diff = Math.abs(Number(k) - clickTs);
    if (diff < bestDiff) {{ bestDiff = diff; bestKey = k; }}
  }});
  const DAY = 86400;
  if (bestKey !== null && bestDiff <= 3 * DAY) {{
    showPeak(bestKey, DATA.snapshots_by_ts[bestKey]);
  }}
}});

chart.timeScale().fitContent();

function showPeak(ts, snap) {{
  let html = '';
  const lifecycle = DATA.lifecycles[ts];
  if (lifecycle) {{
    html += `<div class="section-title">Lifecycle Stage</div>`;
    html += "<div class=\"signal-box high\"><div><span class=\"status-badge " + lifecycle.stage + "\">" + lifecycle.stage.toUpperCase() + "</span> &mdash; Risk: " + lifecycle.risk.toUpperCase() + "</div>";
    html += "<div class=\"signal-action\">" + lifecycle.description + "</div></div>";
  }}

  const isPeak = snap.inflection_type === 'peak';

  if (isPeak) {{
    html += `<div class="section-title">Timing & Structure</div><div class="metric-group">`;
    html += metricRow('Runup bars', snap.runup_bars);
    html += metricRow('Internal dips', snap.internal_dips_count);
    html += metricRow('Relaxation bars', snap.relaxation_bars);
    html += metricRow('Return from trough', fmtPct(snap.return_from_prev_trough));
    html += `</div>`;
  }} else {{
    html += `<div class="section-title">Trough Info</div><div class="metric-group">`;
    html += metricRow('Relaxation bars', snap.relaxation_bars);
    html += metricRow('Drawdown from peak', fmtPct(snap.drawdown_pct));
    html += metricRow('Recovery bars', snap.recovery_time_bars);
    html += `</div>`;
  }}

  html += `<div class="section-title">Candle Shape & Volume</div><div class="metric-group">`;
  html += metricRow('Upper wick %', fmtPct(snap.upper_wick_pct));
  html += metricRow('Body size %', fmtPct(snap.body_size_pct));
  html += metricRow('Volume z-score 20', fmtNum(snap.volume_zscore_20));
  html += metricRow('Volume ratio 20', fmtNum(snap.volume_ratio_20));
  html += `</div>`;

  if (isPeak) {{
    html += `<div class="section-title">Overextension</div><div class="metric-group">`;
    html += metricRow('Dist to SMA_50', fmtPct(snap.close_sma_50_pct));
    html += metricRow('Dist to SMA_200', fmtPct(snap.close_sma_200_pct));
    html += metricRow('Peak ratio', fmtNum(snap.peak_ratio));
    html += `</div>`;
  }} else {{
    html += `<div class="section-title">Overextension</div><div class="metric-group">`;
    html += metricRow('Dist to SMA_50', fmtPct(snap.close_sma_50_pct));
    html += metricRow('Dist to SMA_200', fmtPct(snap.close_sma_200_pct));
    html += `</div>`;
  }}

  if (isPeak) {{
    html += `<div class="section-title">Trend Health</div><div class="metric-group">`;
    html += metricRow('RSI 14', fmtNum(snap.rsi_14));
    html += metricRow('ADX Slope 5', fmtNum(snap.adx_slope_5));
    html += metricRow('RSI divergence', fmtNum(snap.rsi_divergence));
    html += metricRow('ATR 14', fmtNum(snap.atr_14));
    html += metricRow('BB Width %', fmtPct(snap.bb_width_pct));
    html += `</div>`;
  }} else {{
    html += `<div class="section-title">Trend Health</div><div class="metric-group">`;
    html += metricRow('RSI 14', fmtNum(snap.rsi_14));
    html += metricRow('ADX Slope 5', fmtNum(snap.adx_slope_5));
    html += metricRow('ATR 14', fmtNum(snap.atr_14));
    html += metricRow('BB Width %', fmtPct(snap.bb_width_pct));
    html += `</div>`;
  }}

  const matches = DATA.matches_by_ts[ts] || [];
  if (matches.length > 0) {{
    html += `<div class="section-title">KNN Pattern Matches</div>`;
    matches.forEach(m => {{
      const d = new Date(m.matched_bar_ts * 1000);
      const dateStr = d.toISOString().split('T')[0];
      html += `<div class="match-card">`;
      html += `<div class="match-date">${dateStr}</div>`;
      html += `<div class="match-sim">Similarity: ${(m.similarity * 100).toFixed(0)}%</div>`;
      if (m.matched_drawdown_pct !== null) {{
        html += `<div class="match-dd">Drawdown: ${m.matched_drawdown_pct.toFixed(1)}%</div>`;
      }}
      if (m.matched_recovery_bars) {{
        html += `<div class="match-dd">Recovery: ${m.matched_recovery_bars} bars</div>`;
      }}
      html += `</div>`;
    }});
  }}

  const signals = DATA.signals_by_ts[ts] || [];
  if (signals.length > 0) {{
    html += `<div class="section-title">Signals</div>`;
    signals.forEach(s => {{
      const hl = s.confidence > 0.7 ? 'high' : s.confidence > 0.3 ? '' : 'low';
      html += `<div class="signal-box ${hl}">`;
      html += `<div style="display:flex;justify-content:space-between;"><strong>${s.signal_type.replace(/_/g, ' ').toUpperCase()}</strong> <span>${(s.confidence * 100).toFixed(0)}%</span></div>`;
      if (s.suggested_action) html += `<div class="signal-action">${s.suggested_action}</div>`;
      if (s.avg_drawdown_pct !== null && s.avg_drawdown_pct !== undefined) {{
        html += `<div class="signal-action">Avg drawdown: ${s.avg_drawdown_pct.toFixed(1)}%</div>`;
      }}
      html += `</div>`;
    }});
  }}

  document.getElementById('sidebar-content').innerHTML = html;
}}

function metricRow(label, value) {{
  const v = value !== null && value !== undefined && value !== '' ? value : '--';
  return `<div class="metric-row"><span class="metric-label">${label}</span><span class="metric-value">${v}</span></div>`;
}}
function fmtPct(v) {{ return v !== null && v !== undefined ? (v * 100).toFixed(1) + '%' : '--'; }}
function fmtNum(v) {{ return v !== null && v !== undefined ? (typeof v === 'number' ? v.toFixed(2) : v) : '--'; }}
</script>
</body>
</html>
"""


def _serialize_value(val):
    """Serialize a value for JSON, handling numpy/pandas types."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except Exception:
        pass
    if isinstance(val, (np.floating,)):
        return float(val) if not np.isnan(val) else None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, float):
        return None if np.isnan(val) else val
    return val


def _to_timestamp(ts_val):
    """Convert various timestamp types to unix integer."""
    if ts_val is None:
        return None
    if isinstance(ts_val, pd.Timestamp):
        return int(ts_val.timestamp())
    if isinstance(ts_val, float):
        if np.isnan(ts_val):
            return None
        return int(ts_val)
    if isinstance(ts_val, str):
        try:
            return int(pd.Timestamp(ts_val).timestamp())
        except Exception:
            return None
    try:
        return int(ts_val)
    except (ValueError, TypeError):
        return None


def compile_dashboard(
    symbol: str,
    time_format: str = "1D",
    output_dir: str | Path | None = None,
) -> str | None:
    """Read Parquet data and generate dashboard HTML.

    Args:
        symbol: Stock symbol (e.g., "TSLA")
        time_format: Time format used (e.g., "1D", "1H")
        output_dir: Output directory. If None, uses default data root.

    Returns:
        Path to generated HTML file, or None on failure.
    """
    config = load_config()
    storage = AngleStorage(config.data_root)

    trend_lifecycle = storage.read(symbol, "trend_lifecycle")
    if trend_lifecycle.empty:
        return None

    time_format_col = trend_lifecycle.get("time_format")
    snapshot_rows = trend_lifecycle[
        (trend_lifecycle.get("type") == "snapshot")
        & ((time_format_col == time_format) | (time_format_col.isna()))
    ]
    match_rows = trend_lifecycle[
        (trend_lifecycle.get("type") == "match")
        & ((time_format_col == time_format) | (time_format_col.isna()))
    ]
    signal_rows = trend_lifecycle[
        (trend_lifecycle.get("type") == "signal")
        & ((time_format_col == time_format) | (time_format_col.isna()))
    ]
    lifecycle_rows = trend_lifecycle[
        (trend_lifecycle.get("type") == "lifecycle")
        & ((time_format_col == time_format) | (time_format_col.isna()))
    ]

    data_root = config.data_root
    price_candidates = [
        data_root / "stock-prices" / symbol / "parquet",
        data_root / "stock-price" / "prices" / "1m" / symbol / "archive",
        data_root / "stock-prices" / "1m" / symbol,
        data_root / "stock-prices" / symbol,
    ]
    candles_list = []
    for pdir in price_candidates:
        if pdir.exists():
            files = sorted(pdir.glob("*.parquet"))
            if files:
                for f in files[-3:]:
                    try:
                        df = pd.read_parquet(f)
                        candles_list.append(df)
                    except Exception:
                        pass
                if candles_list:
                    break

    chart_candles = []
    chart_volumes = []
    sma50_data = []
    sma200_data = []
    if candles_list:
        all_candles = pd.concat(candles_list, ignore_index=True)
        all_candles = all_candles.sort_values("bar_ts")
        if "bar_ts" in all_candles.columns:
            all_candles["_date"] = pd.to_datetime(all_candles["bar_ts"], unit="s").dt.date
            daily = all_candles.groupby("_date").agg(
                open=("open", "first"), high=("high", "max"),
                low=("low", "min"), close=("close", "last"),
                volume=("volume", "sum"),
            ).reset_index()
            daily["bar_ts"] = daily["_date"].apply(lambda d: int(pd.Timestamp(d).timestamp()))
            candles = daily
        else:
            candles = all_candles

        close_vals = candles["close"].astype(float)
        sma50_vals = close_vals.rolling(50).mean()
        sma200_vals = close_vals.rolling(200).mean()
        for i in range(len(candles)):
            row = candles.iloc[i]
            ts = _to_timestamp(row.get("bar_ts"))
            if ts is None:
                continue
            o = _serialize_value(row.get("open"))
            h = _serialize_value(row.get("high"))
            lv = _serialize_value(row.get("low"))
            c = _serialize_value(row.get("close"))
            if None in (o, h, lv, c):
                continue
            chart_candles.append({"time": ts, "open": o, "high": h, "low": lv, "close": c})
            v = _serialize_value(row.get("volume"))
            if v is not None and v > 0:
                chart_volumes.append({"time": ts, "value": v, "color": "#26a69a" if (c >= o) else "#ef5350"})
            s50 = sma50_vals.iloc[i]
            if pd.notna(s50):
                sma50_data.append({"time": ts, "value": round(float(s50), 2)})
            s200 = sma200_vals.iloc[i]
            if pd.notna(s200):
                sma200_data.append({"time": ts, "value": round(float(s200), 2)})

    _NON_SNAPSHOT_COLUMNS = {
        "status", "total_peaks", "total_patterns", "n_matches", "n_signals",
        "current_stage", "stage", "risk", "description",
        "n_recent_peaks", "n_recent_troughs", "peak_trend", "trough_trend",
        "signal_type", "confidence", "suggested_action", "avg_drawdown_pct",
        "exit_threshold_pct", "min_drop_threshold", "new_snapshots",
        "current_risk", "dominant_signal",
        "matched_bar_ts", "similarity", "matched_drawdown_pct",
        "matched_recovery_bars", "query_bar_ts",
    }

    peaks = []
    troughs = []
    snapshots_by_ts = {}
    snapshots_by_date = {}
    for _, row in snapshot_rows.iterrows():
        ts = _to_timestamp(row.get("bar_ts"))
        if ts is None:
            continue
        snap = {
            col: _serialize_value(row.get(col))
            for col in row.index if col not in _NON_SNAPSHOT_COLUMNS
        }
        key = str(ts)
        snapshots_by_ts[key] = snap
        date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        snapshots_by_date[date_str] = snap
        if row.get("inflection_type") == "peak":
            peaks.append({"time": ts})
        elif row.get("inflection_type") == "trough":
            troughs.append({"time": ts})

    # Key matches by the peak's bar_ts (stored in query_bar_ts only — skip old rows without it)
    known_snap_keys = set(snapshots_by_ts.keys())
    matches_by_ts = {}
    for _, row in match_rows.iterrows():
        query_ts = _to_timestamp(row.get("query_bar_ts"))
        if query_ts is None:
            continue  # skip legacy rows that only have analysis_at
        key = str(query_ts)
        if key not in known_snap_keys:
            # Try to find nearest snap within 1 day (handles midnight vs bar_ts offset)
            DAY = 86400
            closest = min(known_snap_keys, key=lambda k: abs(int(k) - query_ts), default=None)
            if closest and abs(int(closest) - query_ts) <= DAY:
                key = closest
            else:
                continue
        if key not in matches_by_ts:
            matches_by_ts[key] = []
        matches_by_ts[key].append({
            "matched_bar_ts": _to_timestamp(row.get("matched_bar_ts")),
            "similarity": _serialize_value(row.get("similarity")),
            "matched_drawdown_pct": _serialize_value(row.get("matched_drawdown_pct")),
            "matched_recovery_bars": _serialize_value(row.get("matched_recovery_bars")),
        })

    signals_by_ts = {}
    for _, row in signal_rows.iterrows():
        key = str(_to_timestamp(row.get("bar_ts"))) if pd.notna(row.get("bar_ts")) else "unknown"
        if key not in signals_by_ts:
            signals_by_ts[key] = []
        signals_by_ts[key].append({
            "signal_type": str(row.get("signal_type", "")),
            "confidence": _serialize_value(row.get("confidence")),
            "suggested_action": str(row.get("suggested_action", "")),
            "avg_drawdown_pct": _serialize_value(row.get("avg_drawdown_pct")),
        })

    # Lifecycle is a single global result — broadcast it to every snapshot
    lifecycles = {}
    if not lifecycle_rows.empty:
        row = lifecycle_rows.iloc[-1]  # most recent lifecycle row
        lc_entry = {
            "stage": str(row.get("stage", "")),
            "risk": str(row.get("risk", "")),
            "description": str(row.get("description", "")),
        }
        for snap_key in snapshots_by_ts:
            lifecycles[snap_key] = lc_entry

    data = {
        "candles": chart_candles,
        "volumes": chart_volumes,
        "sma50": sma50_data,
        "sma200": sma200_data,
        "peaks": peaks,
        "troughs": troughs,
        "snapshots_by_ts": snapshots_by_ts,
        "snapshots_by_date": snapshots_by_date,
        "matches_by_ts": matches_by_ts,
        "signals_by_ts": signals_by_ts,
        "lifecycles": lifecycles,
    }

    data_json = json.dumps(data, default=str)

    html = _HTML_TEMPLATE.replace("{{", "{").replace("}}", "}")
    html = html.replace("{symbol}", symbol).replace("{time_format}", time_format).replace("{data_json}", data_json)

    if output_dir is None:
        output_dir = config.data_root / "analysis" / symbol / "trend_lifecycle"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"dashboard_{symbol}_{time_format}.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)
