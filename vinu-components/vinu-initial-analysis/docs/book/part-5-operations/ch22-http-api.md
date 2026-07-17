# Chapter 22 — HTTP API route reference

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/server/` |
| **Status** | DRAFT |
| **Prerequisites** | ch01 |

## 1. Routes

| Method | Path | Description | Returns |
|--------|------|-------------|---------|
| GET | `/health` | Health check | `{"ok": true}` |
| GET | `/settings` | Current config | `SettingsResponse` |
| GET | `/impact/{ticker}` | Impact analysis | `DataResponse` with events |
| GET | `/events/{ticker}` | Raw events list | `DataResponse` |
| GET | `/correlation/{ticker}` | Correlation metrics | Correlation dict |
| GET | `/drawdown/{ticker}` | Drawdown attribution | Drawdown dict |
| GET | `/baseline/{ticker}` | Baseline deviation | Baseline dict |

## 2. Query parameters

All data endpoints accept optional:

| Param | Type | Description |
|-------|------|-------------|
| `from` | int | Start timestamp (Unix seconds) |
| `to` | int | End timestamp (Unix seconds) |

## 3. Response models

```python
class DataResponse(BaseModel, Generic[T]):
    count: int
    data: list[T] | dict[str, Any]

class SettingsResponse(BaseModel):
    data_root: str
    news_api_url: str
    stock_api_url: str
    port: int
    impact_high_threshold: float
    impact_medium_threshold: float
    drawdown_min_pct: float
    drawdown_lookback_hours: int
    baseline_window_days: int
    cache_ttl_sec: int
    compute_poll_interval_sec: int
    compact_threshold: int
```

## 4. Static UI

The `/ui` path serves the React web dashboard built in `web/`.

## 5. Server startup

```bash
vinu-correlation-serve --host 0.0.0.0 --port 8083
```
