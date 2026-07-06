# Chapter 01 — Install, serve, first compute

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Status** | DRAFT |
| **Prerequisites** | ch00 |

## 1. Install

```bash
cd vinu-correlation
pip install -e ".[dev]"
cp .env.example .env
# edit .env to point at running news + stock-price instances
```

## 2. Start the API server

```bash
vinu-correlation-serve --host 0.0.0.0 --port 8083
```

Or via Docker:

```bash
docker build -t vinu-correlation .
docker run -p 8083:8083 -v /path/to/data:/data vinu-correlation
```

## 3. First compute

```bash
vinu-correlation-compute AAPL
vinu-correlation-compute AAPL MSFT GOOGL --from-year 2026 --to-year 2026
```

## 4. Query results

```bash
vinu-correlation-query correlation AAPL
vinu-correlation-query impact AAPL
vinu-correlation-query drawdown AAPL
vinu-correlation-query baseline AAPL
```

## 5. Run tests

```bash
pytest tests/ -v
```
