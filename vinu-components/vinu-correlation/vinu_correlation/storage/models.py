import pyarrow as pa

IMPACT_SCHEMA = pa.schema([
    ("article_id", pa.string()),
    ("symbol", pa.string()),
    ("is_primary", pa.bool_()),
    ("ticker_count", pa.int64()),
    ("ts", pa.int64()),
    ("session", pa.string()),
    ("headline", pa.string()),
    ("sentiment", pa.string()),
    ("sentiment_score", pa.int64()),
    ("impact_label", pa.string()),
    ("price_change_5m", pa.float64()),
    ("price_change_15m", pa.float64()),
    ("price_change_30m", pa.float64()),
    ("price_change_1h", pa.float64()),
    ("price_change_1d", pa.float64()),
    ("abnormal_return_30m", pa.float64()),
    ("car_1h", pa.float64()),
    ("ar_p_value", pa.float64()),
    ("ar_significant", pa.bool_()),
    ("thread_id", pa.string()),
    ("computed_at", pa.int64()),
])

BASELINE_SCHEMA = pa.schema([
    ("symbol", pa.string()),
    ("hour_ts", pa.int64()),
    ("session", pa.string()),
    ("article_count", pa.int64()),
    ("mean", pa.float64()),
    ("stddev", pa.float64()),
    ("sample_size", pa.int64()),
])

CORRELATION_SCHEMA = pa.schema([
    ("symbol", pa.string()),
    ("window", pa.string()),
    ("period_start", pa.int64()),
    ("period_end", pa.int64()),
    ("sample_size", pa.int64()),
    ("news_return_corr", pa.float64()),
    ("corr_p_value", pa.float64()),
    ("corr_ci_lower", pa.float64()),
    ("corr_ci_upper", pa.float64()),
    ("granger_p_value", pa.float64()),
    ("granger_best_lag_mins", pa.int64()),
    ("sentiment_return_corr", pa.float64()),
    ("news_volume_corr", pa.float64()),
])
