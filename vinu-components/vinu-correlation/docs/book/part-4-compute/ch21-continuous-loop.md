# Chapter 21 — Continuous polling loop

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/cli.py` (compute_main) |
| **Status** | DRAFT |
| **Prerequisites** | ch19, ch20 |

## 1. Problem

For monitoring use cases, correlation data should be kept fresh automatically. The continuous loop mode runs compute in an infinite cycle with a configurable interval.

## 2. Logic

```python
if args.continuous:
    while True:
        _compute_batch(tickers, incremental=not args.force)
        time.sleep(args.interval)  # default 3600s (1 hour)
```

## 3. Configuration

| Flag | Default | Description |
|------|---------|-------------|
| `--continuous` | off | Enable continuous loop |
| `--interval` | 3600s | Sleep interval between iterations |

## 4. Use case

```bash
# Poll every hour for the watchlist
vinu-correlation-compute AAPL MSFT GOOGL --continuous --interval 3600

# All watchlist tickers, continuous
vinu-correlation-compute --all --continuous
```

## 5. Pipeline status output

With `--pipeline`, each compute iteration logs status for each symbol:

```
INFO Computing AAPL (incremental=True)...
INFO Done AAPL
INFO Computing MSFT...
...
INFO Sleeping 3600s...
```
