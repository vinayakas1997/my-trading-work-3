# Appendix B — Troubleshooting

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Status** | DRAFT |

## Connection refused to news/price API

```
requests.exceptions.ConnectionError: Connection refused
```

**Cause:** vinu-news or vinu-stock-price is not running.  
**Fix:** Start the services. In Docker, `127.0.0.1` is auto-rewritten to `host.docker.internal`.

## Insufficient data for correlation

```
returns correlation 0.0, p_value 1.0
```

**Cause:** Fewer than 5 hourly observations after merging news + price data.  
**Fix:** Check that both services have data for the ticker. Increase the time range.

## Granger test returning safe defaults

```
granger_causes_prices: false, p_value: 1.0
```

**Cause:** Insufficient observations (< max_lag + 5). Need at least 17 hourly data points.  
**Fix:** Ensure enough news+price data is available.

## Parquet read errors

```
ArrowInvalid: Could not read Parquet file
```

**Cause:** Corrupted Parquet file from interrupted write.  
**Fix:** Delete the file and recompute: `vinu-correlation-compute SYMBOL --force`.

## Cache returning stale data

**Cause:** TTL not yet expired (default 300s).  
**Fix:** Wait or restart the server. Cache is invalidated on `compute_and_store()`.
