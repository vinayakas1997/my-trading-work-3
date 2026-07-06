# Chapter 25 — Docker & compose

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `Dockerfile` |
| **Status** | DRAFT |
| **Prerequisites** | ch01 |

## 1. Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . /app/vinu-correlation
WORKDIR /app/vinu-correlation
RUN pip install --no-cache-dir -e ".[dev]"
ENV VINU_CORRELATION_DATA_ROOT=/data
VOLUME ["/data"]
EXPOSE 8083
```

## 2. Build & run

```bash
docker build -t vinu-correlation .
docker run -p 8083:8083 \
  -v /path/to/data:/data \
  -e VINU_NEWS_API_URL=http://host.docker.internal:8080 \
  -e VINU_STOCK_API_URL=http://host.docker.internal:8081 \
  vinu-correlation
```

## 3. Docker networking

The `net.py` module automatically rewrites `127.0.0.1` → `host.docker.internal` when running inside a container and the initial connection fails. This means the same `.env` file works both locally and in Docker.

## 4. Data volumes

Correlation data is persisted at `/data/correlation/{SYMBOL}/*.parquet` inside the container.
