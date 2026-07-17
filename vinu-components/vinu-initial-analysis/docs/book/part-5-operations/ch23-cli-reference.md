# Chapter 23 — CLI reference

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/cli.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch01 |

## 1. Commands

### `vinu-correlation-serve`

Start the FastAPI HTTP server.

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | 127.0.0.1 | Bind address |
| `--port` | 8083 | Port number |
| `--data-root` | ./data | Data directory |

### `vinu-correlation-compute`

Compute correlation data for one or more tickers.

| Flag | Default | Description |
|------|---------|-------------|
| `tickers` | — | Space-separated ticker symbols |
| `--all` | off | Compute all watchlist tickers |
| `--from-year` | — | Start year |
| `--to-year` | — | End year |
| `--incremental` | off | Only new data since last compute |
| `--force` | off | Full recompute from scratch |
| `--continuous` | off | Infinite polling loop |
| `--interval` | 3600 | Poll interval seconds |
| `--pipeline` | off | Pipeline status output |

### `vinu-correlation-compact`

Compact Parquet row groups.

| Flag | Default | Description |
|------|---------|-------------|
| `tickers` | — | Space-separated symbols |
| `--year` | 2026 | Target year |
| `--all` | off | Compact all symbols |

### `vinu-correlation-query`

Query stored results. Subcommands:

| Subcommand | Description |
|------------|-------------|
| `impact TICKER [--from] [--to]` | Get impact analysis |
| `events TICKER [--from] [--to]` | Get raw events |
| `correlation TICKER [--from] [--to]` | Get correlation metrics |
| `drawdown TICKER [--from] [--to]` | Get drawdown attribution |
| `baseline TICKER` | Get baseline deviation |
