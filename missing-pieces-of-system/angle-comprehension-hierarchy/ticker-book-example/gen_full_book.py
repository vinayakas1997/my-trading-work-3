# Generates a full 28-angle, real-time-format fake dataset for AAPL,
# in the same get_all_angles()-shaped JSON the real angle_synthesizer
# tool call returns. Two variants: "clean" (every angle has data at
# every one of its real time_formats) and "uneven" (deliberately messy:
# missing timeframes, an angle with zero data anywhere, malformed
# values, mismatched run_ids) -- to stress-test the prompt/LLM per the
# real request: "check with some uneven data so we know the prompt and
# the LLM can handle it."

import json

REAL_TIME_FORMATS = {
    "arima": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "backtesting_44_metrics": ["1min", "5min", "15min", "1H", "4H", "1D", "1W", "1M", "6M"],
    "chronos": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "dlinear": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "drawdown_deep_dive": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "exponential_smoothing": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "garch": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "itransformer": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "kalman_filters": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "kronos": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "lag_llama": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "lpatchtst": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "lstm": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "moirai": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "moment": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "news_price_causality": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "patchtst": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "peer_relative_strength": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "pnl_attribution": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "regime_analysis": ["1min", "5min", "15min", "1H", "4H", "1D", "1W", "1M"],
    "shock_clustering": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "shock_personality": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "tft": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "timer_timerxl": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "timesfm": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "tips_regime_aware_transformer": ["1min", "5min", "15min", "1H", "4H", "1D"],
    "trend_lifecycle": ["1min", "5min", "15min", "1H", "4H", "1D", "1W"],
    "trend_session_structure": ["1min", "5min", "15min", "1H", "4H"],
}

CLUSTERS = {
    "A": ["arima", "exponential_smoothing", "kalman_filters"],
    "B": ["chronos", "dlinear", "itransformer", "kronos", "lag_llama", "lpatchtst",
          "lstm", "moirai", "moment", "patchtst", "tft", "timer_timerxl", "timesfm",
          "tips_regime_aware_transformer"],
    "C": ["garch", "drawdown_deep_dive"],
    "D": ["regime_analysis", "trend_lifecycle", "trend_session_structure"],
    "E": ["shock_clustering", "shock_personality"],
    "F": ["peer_relative_strength", "news_price_causality"],
    "G": ["backtesting_44_metrics", "pnl_attribution"],
}

# Confidence/strength decays as timeframe shortens (established narrative:
# real daily uptrend, stalling intraday) -- longest timeframe first.
TF_ORDER = ["6M", "1M", "1W", "1D", "4H", "1H", "15min", "5min", "1min"]


def decay_factor(tf: str) -> float:
    idx = TF_ORDER.index(tf)
    d_idx = TF_ORDER.index("1D")
    # 1.0 at 1D, drifting down toward 1min, slightly up toward longer TFs
    return max(0.15, 1.0 - 0.11 * (idx - d_idx) if idx >= d_idx else 1.0 + 0.05 * (d_idx - idx))


def directional_row(base_conf: float, base_dir: str, tf: str) -> dict:
    f = decay_factor(tf)
    conf = round(min(0.95, max(0.08, base_conf * f)), 2)
    direction = base_dir if conf >= 0.30 else "flat"
    return {"direction": direction, "confidence": conf}


def build_clean_dataset() -> dict:
    angles = {}

    def put(name, rows_fn):
        tfs = REAL_TIME_FORMATS[name]
        angles[name] = {tf: rows_fn(tf) for tf in tfs}

    # Cluster A -- classical statistical
    put("arima", lambda tf: {
        "forecast_price": round(186.0 + 3.2 * decay_factor(tf), 2),
        "order": [2, 1, 1] if tf in ("1D", "4H") else [1, 1, 1],
        "aic": round(842.1 * (0.4 + 0.6 * decay_factor(tf)), 1),
    })
    put("exponential_smoothing", lambda tf: {
        "point_forecast": round(188.5 + 3 * decay_factor(tf), 2),
        "alpha": 0.32, "beta": 0.05,
        "trend": "up" if decay_factor(tf) > 0.5 else "flat",
    })
    put("kalman_filters", lambda tf: {
        "filtered_level": round(186.0 + 1.4 * decay_factor(tf), 2),
        "filtered_trend": round(0.12 * decay_factor(tf), 3),
    })

    # Cluster B -- deep-learning / foundation-model (14 members)
    put("patchtst", lambda tf: directional_row(0.61, "up", tf))
    put("lpatchtst", lambda tf: directional_row(0.66, "up", tf))
    put("timesfm", lambda tf: {
        "point_forecast": round(186.0 + 3 * decay_factor(tf), 2),
        "model_backend": "pretrained",
    })
    put("chronos", lambda tf: {
        "median_forecast": round(186.5 + 2.5 * decay_factor(tf), 2),
        "model_backend": "pretrained",
        **directional_row(0.58, "up", tf),
    })
    put("dlinear", lambda tf: directional_row(0.44, "up", tf))
    put("itransformer", lambda tf: directional_row(0.50, "up", tf))
    put("kronos", lambda tf: {
        "next_bar_close": round(187.0 + 2 * decay_factor(tf), 2),
        "model_backend": "pretrained",
    })
    put("lag_llama", lambda tf: {
        "p50_forecast": round(187.2 + 2 * decay_factor(tf), 2),
        "model_backend": "fallback_proxy",
    })
    put("lstm", lambda tf: directional_row(0.39, "up", tf))
    put("moirai", lambda tf: {
        "p50_forecast": round(187.0 + 2.2 * decay_factor(tf), 2),
        "model_backend": "fallback_proxy",
    })
    put("moment", lambda tf: {
        "p50_forecast": round(186.8 + 2.1 * decay_factor(tf), 2),
        "model_backend": "fallback_proxy",
    })
    put("tft", lambda tf: directional_row(0.47, "up", tf))
    put("timer_timerxl", lambda tf: {
        "point_forecast": round(187.5 + 1.8 * decay_factor(tf), 2),
        "model_backend": "pretrained",
    })
    put("tips_regime_aware_transformer", lambda tf: {
        **directional_row(0.42, "up", tf),
        "regime_label": "momentum" if decay_factor(tf) > 0.5 else "mean_reversion",
    })

    # Cluster C -- volatility / drawdown
    put("garch", lambda tf: {
        "forecast_volatility": round(0.021 + 0.006 * (1 - decay_factor(tf)), 3),
        "persistence": 0.95,
    })
    put("drawdown_deep_dive", lambda tf: {
        "current_drawdown_pct": -0.03,
        "max_drawdown_pct": -0.18,
    })

    # Cluster D -- regime / trend
    put("regime_analysis", lambda tf: {
        "regime": "bull" if decay_factor(tf) > 0.55 else "sideways",
        "bull_prob": round(0.30 + 0.30 * decay_factor(tf), 2),
        "sideways_prob": round(0.55 - 0.35 * decay_factor(tf), 2),
    })
    put("trend_lifecycle", lambda tf: {
        "stage": "uptrend",
        "reversal_signal": False,
        "knn_similarity_score": round(0.45 + 0.35 * decay_factor(tf), 2),
    })
    put("trend_session_structure", lambda tf: {
        "peak_session": "US_open" if tf in ("1H", "4H") else "Asia",
        "trough_session": "US_close",
    })

    # Cluster E -- shock / personality
    put("shock_personality", lambda tf: {
        "gap_fill_rate_mean": 0.60,
        "vol_persistence": round(0.88 + 0.06 * (1 - decay_factor(tf)), 2),
    })
    put("shock_clustering", lambda tf: {
        "cluster_members": ["MSFT", "GOOGL"],
        "co_shock_rate": 0.35,
    })

    # Cluster F -- cross-asset / causality
    put("peer_relative_strength", lambda tf: {
        "peer": "MSFT",
        "relative_return_20d": 0.023,
    })
    put("news_price_causality", lambda tf: {
        "granger_p_value": 0.04,
        "pearson_correlation": 0.38,
    })

    # Cluster G -- validation / attribution (backward-looking, timeframe-invariant)
    put("backtesting_44_metrics", lambda tf: {"sharpe": 1.15, "win_rate": 0.54})
    put("pnl_attribution", lambda tf: {"win_rate": 0.58, "trade_count": 19})

    return angles


def to_row_count_shape(angles: dict) -> dict:
    """Wrap in the real get_all_angles() response shape: each angle has
    row_count + per-timeframe latest data."""
    out = {}
    for name, by_tf in angles.items():
        out[name] = {
            "row_count": len(by_tf),
            "by_time_format": by_tf,
        }
    return out


def build_uneven_dataset(clean: dict) -> dict:
    """Deliberately messy variant, real-shaped problems:
    - trend_session_structure: total row_count=0 (angle never ran for this ticker)
    - Cluster B: wildly uneven coverage -- half the models only have 1D,
      the other half only have intraday, none have the full real set
      (realistic: different models finish their runs on different
      schedules/cadences)
    - kronos: an "error" field instead of data (a real angle-runner failure)
    - garch: one timeframe has a NaN-ish malformed value
    - arima: mismatched run_id pattern across timeframes (two different
      run_ids claiming to be the "latest" -- a real race/staleness bug
      shape, not just missing data)
    """
    import copy
    uneven = copy.deepcopy(clean)

    # trend_session_structure: angle never computed for this ticker
    uneven["trend_session_structure"] = {"row_count": 0, "by_time_format": {}}

    # Cluster B uneven coverage: keep only some timeframes per model,
    # asymmetric across the cluster (not a clean subset all models share)
    intraday_only = ["chronos", "dlinear", "moment"]
    daily_only = ["moirai", "lag_llama", "tft"]
    for name in intraday_only:
        by_tf = uneven[name]["by_time_format"]
        keep = {tf: v for tf, v in by_tf.items() if tf in ("1min", "5min", "15min", "1H")}
        uneven[name] = {"row_count": len(keep), "by_time_format": keep}
    for name in daily_only:
        by_tf = uneven[name]["by_time_format"]
        keep = {tf: v for tf, v in by_tf.items() if tf in ("4H", "1D")}
        uneven[name] = {"row_count": len(keep), "by_time_format": keep}

    # kronos: real angle-runner failure shape
    uneven["kronos"] = {"row_count": 1, "by_time_format": {
        "1D": {"error": "model checkpoint load failed: CUDA OOM"}
    }}

    # garch: malformed value slipped through at one timeframe
    uneven["garch"]["by_time_format"]["1min"] = {"forecast_volatility": "NaN", "persistence": 0.95}

    # arima: mismatched run_id / stale-looking duplicate 1D read (two
    # different values both claiming to be the latest 1D result --
    # represented here as the 1D value silently disagreeing with what a
    # freshly-run 4H would imply, a staleness smell rather than a clean gap)
    uneven["arima"]["by_time_format"]["1D"] = {
        "forecast_price": 171.40, "order": [2, 1, 1], "aic": 842.1,
        "_note_run_id": "AAPL_arima_1da_260918_260921_01_x7k2q (3 days stale)",
    }

    return uneven


def render_digest_lines(angles_row_count_shape: dict) -> str:
    lines = []
    for name in sorted(angles_row_count_shape.keys()):
        entry = angles_row_count_shape[name]
        rc = entry["row_count"]
        if rc == 0:
            lines.append(f"{name}: row_count=0 (no data)")
            continue
        for tf, vals in entry["by_time_format"].items():
            if "error" in vals:
                lines.append(f"{name}.{tf}: error={vals['error']}")
                continue
            kv = ", ".join(f"{k}={v}" for k, v in vals.items())
            lines.append(f"{name}.{tf}: {kv}")
    return "\n".join(lines)


if __name__ == "__main__":
    clean = build_clean_dataset()
    clean_wrapped = to_row_count_shape(clean)
    uneven_wrapped = build_uneven_dataset(clean_wrapped)

    with open("clean_dataset.json", "w", encoding="utf-8") as f:
        json.dump(clean_wrapped, f, indent=2)
    with open("uneven_dataset.json", "w", encoding="utf-8") as f:
        json.dump(uneven_wrapped, f, indent=2)

    with open("clean_digest.txt", "w", encoding="utf-8") as f:
        f.write(render_digest_lines(clean_wrapped))
    with open("uneven_digest.txt", "w", encoding="utf-8") as f:
        f.write(render_digest_lines(uneven_wrapped))

    print("clean angles:", len(clean_wrapped), "total rows:",
          sum(v["row_count"] for v in clean_wrapped.values()))
    print("uneven angles:", len(uneven_wrapped), "total rows:",
          sum(v.get("row_count", 0) for v in uneven_wrapped.values()))
