# Chapter 10 — HTTP API

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/server/routes_requests.py` |
| **Status** | v1 |
| **Prerequisites** | ch05 |

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Registry counts |
| GET | `/presets` | List blueprints |
| POST | `/requests` | Submit job |
| GET | `/requests` | List with filters |
| GET | `/requests/{id}` | By id |
| GET | `/requests/by-title/{title}` | Latest by title |
| POST | `/requests/{id}/run` | Process one job |
| DELETE | `/requests/{id}` | Delete run |

Default port: **8082** (`VINU_FEATURES_PORT`).

## Example

```bash
curl -X POST http://127.0.0.1:8082/requests \
  -H "Content-Type: application/json" \
  -d '{"title":"demo","symbols":["AAPL"],"days":90,"preset":"basic_ta","run_immediately":true}'
```
