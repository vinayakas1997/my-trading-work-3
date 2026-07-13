# Enhancement 9: Security & Architecture Hardening

## Current State Score: 6/10

The architecture is well-structured but has several security and operational gaps that prevent it from being production-grade:

1. **`exec()` for custom strategies** — Arbitrary code execution vulnerability
2. **No inter-service auth** — All APIs are open, no authentication
3. **vinu-research not in docker-compose** — Core component missing from orchestration
4. **No centralized logging** — Each service logs independently with different formats
5. **No health monitoring** — Health endpoints exist but no centralized monitoring/alerting
6. **Mixed async/sync** — Maintenance burden
7. **Duplicate dependency management** — No monorepo tooling

## Target State: 10/10

A hardened, production-ready architecture with:
1. **Sandboxed strategy execution** — Safe `exec()` with AST validation
2. **API authentication** — JWT or API keys for inter-service communication
3. **Full docker-compose orchestration** — All 7 services managed together
4. **Centralized logging** — Structured JSON logging with correlation IDs
5. **Health monitoring dashboard** — Prometheus metrics + Grafana
6. **Consistent async runtime** — All services using async where sensible
7. **Shared dependency management** — Monorepo with uv workspace

## Why This Matters (The Problem)

- `exec()` allows a malicious user (or buggy generated code) to execute `os.system("rm -rf /")` on the simulator server
- Open APIs mean any container on the Docker network can call any other service
- vinu-research not in docker-compose means it's not runnable via a simple `docker compose up`
- Without centralized logging, debugging across services requires reading 7 different log files
- Without monitoring, you don't know if a service is down until a strategy fails

## What to Build

### 1. Sandboxed Strategy Execution — Replace `exec()` in `custom_sim.py`

**Current (dangerous):**
```python
exec(strategy_code, globals_dict)
strategy = globals_dict["UserStrategy"]()
```

**New (safe):**
```python
import ast
import typing

RESTRICTED_GLOBALS = {
    "__builtins__": {
        "len": len, "range": range, "int": int, "float": float,
        "abs": abs, "min": min, "max": max, "sum": sum,
        "isinstance": isinstance, "type": type, "list": list,
        "dict": dict, "bool": bool, "True": True, "False": False,
        "None": None, "enumerate": enumerate, "zip": zip,
        "map": map, "filter": filter, "any": any, "all": all,
        "hasattr": hasattr, "getattr": getattr, "setattr": setattr,
        "round": round, "sorted": sorted, "reversed": reversed,
    },
    "pd": pd,
    "np": np,
    "BaseStrategy": BaseStrategy,
    "UserStrategy": None,  # Will be set by exec
}

def validate_and_execute(code: str) -> BaseStrategy:
    """Validate code is safe, then execute"""

    # Step 1: AST validation
    tree = ast.parse(code)
    for node in ast.walk(tree):
        # Allow only safe operations
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ("eval", "exec", "__import__", "open"):
                    raise ValueError(f"Unsafe function call: {node.func.id}")
        if isinstance(node, ast.Attribute):
            if node.attr in ("__subclasses__", "__globals__", "__builtins__"):
                raise ValueError(f"Unsafe attribute access: {node.attr}")

    # Step 2: Restricted exec
    local_vars = {}
    exec(code, RESTRICTED_GLOBALS, local_vars)

    # Step 3: Verify output
    strategy_class = local_vars.get("UserStrategy")
    if strategy_class is None:
        raise ValueError("Generated code must define UserStrategy class")

    strategy = strategy_class()
    if not hasattr(strategy, "generate_weights"):
        raise ValueError("UserStrategy must have generate_weights method")

    return strategy
```

### 2. API Authentication — Shared Middleware in `vinu_lib`

```python
# vinu_lib/auth.py
import hashlib
import hmac
import os
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

API_KEY = os.environ.get("VINU_API_KEY", "")
API_SECRET = os.environ.get("VINU_API_SECRET", "")

async def verify_api_key(request: Request, call_next):
    if not API_KEY:
        # No auth configured — pass through (dev mode)
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    signature = request.headers.get("X-Signature")

    if api_key != API_KEY:
        return JSONResponse(status_code=401, content={"error": "Invalid API key"})

    # HMAC signature verification for write operations
    if request.method in ("POST", "PUT", "DELETE"):
        body = await request.body()
        expected_sig = hmac.new(
            API_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return JSONResponse(status_code=401, content={"error": "Invalid signature"})

    return await call_next(request)
```

### 3. Centralized Logging

Add to `vinu_lib`:

```python
# vinu_lib/logging.py
import json
import logging
import uuid
from contextvars import ContextVar

correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "service": record.name.split(".")[0],
            "correlation_id": correlation_id.get(),
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def setup_logging(service_name: str):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
```

### 4. Full Docker Compose — Add vinu-research and monitoring

```yaml
# docker-compose additions
services:
  # ... existing services ...

  vinu-research:
    build: ./vinu-research
    ports:
      - "8086:8086"
    env_file: .env
    depends_on:
      vinu-simulator:
        condition: service_healthy
      vinu-correlation:
        condition: service_healthy
    volumes:
      - vinu_shared_exchange:/shared
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8086/health"]
      interval: 30s

  # Monitoring
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
```

### 5. Health Monitoring — Prometheus Metrics in `vinu_lib`

```python
# vinu_lib/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests",
    ["service", "method", "endpoint", "status"]
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration",
    ["service", "method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

BACKTEST_DURATION = Histogram(
    "backtest_duration_seconds", "Backtest execution duration",
    ["service"],
    buckets=[1, 5, 10, 30, 60, 120]
)

STRATEGY_VERDICT = Counter(
    "strategy_verdicts_total", "Strategy verdicts",
    ["service", "verdict"]  # PASS, STOP, REFINE
)
```

### 6. Standardize on Async — Migrate Key Sync Services

**Current async services**: vinu-research (async)
**Current sync services**: vinu-news, vinu-stock-price, vinu-features, vinu-strategy, vinu-simulator

**Migration plan**:
- Phase 1: vinu-simulator (most latency-sensitive, already has async callers)
- Phase 2: vinu-correlation (async callers in research loop)
- Phase 3: vinu-stock-price, vinu-features (data services, benefit from async I/O)
- Leave vinu-news sync (it's I/O-bound and less latency-sensitive)

### 7. Shared Dependency Management

```toml
# pyproject.toml at root (uv workspace)
[tool.uv]
workspace = true

[project]
name = "vinu"
dependencies = [
    "fastapi>=0.110",
    "pydantic>=2.0",
    "httpx>=0.27",
    "pandas>=2.0",
    "numpy>=1.24",
]
```

Each service references shared deps:

```toml
# vinu-research/pyproject.toml
[project]
name = "vinu-research"
dependencies = [
    "vinu-lib"  # Shared library
]
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_lib/auth.py` | **NEW** | Shared API key + HMAC auth middleware |
| `vinu_lib/logging.py` | **NEW** | Structured JSON logging with correlation IDs |
| `vinu_lib/metrics.py` | **NEW** | Prometheus metrics (request count, duration, backtest stats) |
| `vinu_simulator/engine/custom_sim.py` | MODIFY | Replace bare exec() with AST-validated sandbox |
| `vinu_lib/server.py` | MODIFY | Add auth middleware, metrics endpoints |
| `docker-compose.yml` | MODIFY | Add vinu-research, prometheus, grafana |
| `.github/workflows/ci.yml` | **NEW** | GitHub Actions CI (test + lint) |
| `monitoring/prometheus.yml` | **NEW** | Prometheus scrape config |
| `monitoring/grafana/dashboards/` | **NEW** | Grafana dashboards |

## Complexity & Verdict

- **Difficulty**: Medium (mostly straightforward tooling, sandboxed exec is the only hard part)
- **Lines of code**: ~500-700 total
- **Priority**: **MEDIUM** — critical for production, but development can proceed without it
- **Risk**: Medium — auth changes could break inter-service communication if not done carefully
- **Time estimate**: 5-8 days

## Implementation Order

### Phase 1 — Critical (3 days)
1. Replace `exec()` with sandboxed execution in custom_sim.py
2. Add vinu-research to docker-compose
3. Add health check endpoints to all services

### Phase 2 — Observability (2 days)
4. Add Prometheus metrics to all services
5. Add Grafana dashboards
6. Add structured logging

### Phase 3 — Security (2 days)
7. Add API key auth middleware
8. Add HMAC request signing for write operations
9. Document security model in README

### Phase 4 — Developer Experience (1 day)
10. Set up uv workspace for shared dep management
11. Set up GitHub Actions CI
12. Add pre-commit hooks (ruff, mypy)
