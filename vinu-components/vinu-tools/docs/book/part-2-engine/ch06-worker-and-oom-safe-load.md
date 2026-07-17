# Chapter 6 — Worker and OOM-Safe Load

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/worker/runner.py`, `engine/engine.py` |
| **Status** | v1 |
| **Prerequisites** | ch05 |

## Learning objectives

- Run `vinu-features worker --once` to drain pending queue.
- Understand per-symbol fetch and incremental parquet append.
- Configure parallel processing for multiple symbols.

## OOM strategy

1. Fetch one symbol at a time from vinu-stock-price.
2. Apply indicators in memory for that symbol only.
3. Append to `features.parquet` via PyArrow writer.
4. Discard in-memory rows before next symbol.

Warm-up window: `from_ts - warmup_bars * interval_seconds`.

## Parallel Processing

For requests with multiple symbols, the engine processes them concurrently using a thread pool:

```python
with ThreadPoolExecutor(max_workers=min(len(request.symbols), 8)) as pool:
    futures = {pool.submit(_process_symbol, s): s for s in request.symbols}
    for future in as_completed(futures):
        table = future.result()
        writer.write_table(table)
```

### Configuration

- **Max workers**: 8 threads (configurable via `max_workers`)
- **Per-symbol**: Each thread handles one symbol fetch + indicator application
- **Merge**: Results appended to single parquet file in completion order

### Benefits

- **Speed**: 3 symbols processed ~3x faster than sequential
- **Memory**: Still OOM-safe since each thread discards rows after append
- **Scalability**: Limited to 8 workers to prevent resource exhaustion

### Example

```bash
# Single symbol: sequential processing
vinu-features submit --title single --symbols AAPL --days 365 --preset swing_basic

# Multiple symbols: parallel processing (up to 8 workers)
vinu-features submit --title multi --symbols AAPL,GOOGL,MSFT,NVDA,TSLA --days 365 --preset swing_basic
```

### Monitoring

Check logs for thread activity:

```bash
vinu-features worker --loop --verbose
# DEBUG: Processing symbol AAPL
# DEBUG: Processing symbol GOOGL
# DEBUG: Processing symbol MSFT
```
