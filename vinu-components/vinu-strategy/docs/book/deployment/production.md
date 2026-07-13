# Production Setup

## Overview

This guide covers production deployment considerations for vinu-strategy.

## Architecture

### Recommended Setup

```
┌─────────────────────────────────────────────────────────────┐
│                    Production Environment                   |
├─────────────────────────────────────────────────────────────┤
│                                                             |
│  [Load Balancer]                                           |
│       |                                                    |
│       v                                                    |
│  +----------------+  +----------------+  +--------------+  |
│  | vinu-strategy |  | vinu-strategy |  | vinu-strategy |  |
│  |   Container 1 |  |   Container 2 |  |   Container 3 |  |
│  +----------------+  +----------------+  +--------------+  |
│       |                    |                    |          |
│       v                    v                    v          |
│  +-----------------------------------------------------+   |
│  |              Shared Storage                         |   |
│  |  - Parquet weights (S3/NFS)                          |   |
│  |  - Metadata (RDS/Cloud SQL)                          |   |
│  +-----------------------------------------------------+   |
│                                                             |
│  +----------------+  +----------------+                      |
│  | vinu-features  |  |vinu-correlation|                      |
│  |     API        |  |      API       |                      |
│  +----------------+  +----------------+                      |
│                                                             |
└─────────────────────────────────────────────────────────────┘
```

## Configuration

### Environment Variables

```bash
# API Endpoints
FEATURES_API_URL=https://features-api.yourdomain.com
CORRELATION_API_URL=https://correlation-api.yourdomain.com

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Data Storage
DATA_ROOT=/data
STRATEGIES_DIR=/strategies

# Security (add in production)
API_KEY=your-secret-api-key
CORS_ORIGINS=https://yourdomain.com

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
```

### Database

**Option 1: SQLite (Small deployments)**
```
/data/meta.db
```

**Option 2: PostgreSQL (Large deployments)**
```python
# TODO: Add PostgreSQL support
DATABASE_URL="postgresql://:pass@host:5432/vinu_strategy"
```

### Storage

**Option 1: Local (Small deployments)**
```
/data/weights/
/data/meta.db
```

**Option 2: S3/NFS (Large deployments)**
```python
# Configure S3 storage
WEIGHTS_S3_BUCKET="s3://your-bucket/weights"
WEIGHTS_S3_PREFIX="vinu-strategy/"
```

## Security

### API Authentication

**Add API key middleware**:
```python
from fastapi import HTTPException, Header

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != "your-secret-api-key":
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key
```

**Apply to routes**:
```python
router.add_api_route(
    "/strategies/{name}/evaluate",
    evaluate_strategy,
    dependencies=[Depends(verify_api_key)]
)
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Rate Limiting

```python
from fastapi_throttle import Throttle

throttle = Throttle(
    rates={"1 hour": "1000 requests"},
    block_when_exhausted=True
)

@app.post("/strategies/{name}/evaluate")
async def evaluate_strategy(...):
    await throttle.check_limit()
    # ... rest of code
```

## Monitoring

### Logging

**Configuration**:
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/vinu-strategy.log'),
        logging.StreamHandler()
    ]
)
```

**Log rotation**:
```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    '/var/log/vinu-strategy.log',
    maxBytes=10_000_000,  # 10MB
    backupCount=5
)
```

### Metrics

**Planned metrics**:
- Evaluation duration
- Feature fetch latency
- Correlation fetch latency
- Pipeline stage duration
- Storage write time
- Error rates

**Implementation**:
```python
from prometheus_client import Counter, Histogram, generate_latest

evaluation_count = Counter('evaluations_total', 'Total evaluations')
evaluation_duration = Histogram('evaluation_duration_seconds', 'Evaluation duration')

@evaluation_duration.time()
def evaluate():
    evaluation_count.inc()
    # ... evaluation logic
```

### Health Checks

**Endpoint**: `GET /health`

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-07-06T14:30:22.123456",
  "checks": {
    "features_api": "healthy",
    "correlation_api": "healthy",
    "database": "healthy"
  }
}
```

## Scaling

### Horizontal Scaling

**Load balancing**:
- Use load balancer to distribute requests
- Share storage via S3/NFS
- Use shared database

**Stateless design**:
- No local state in containers
- All data in shared storage
- Easy to scale up/down

### Performance Tuning

**Connection pooling**:
```python
import httpx

# Use connection pool
client = httpx.Client(
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20
    )
)
```

**Async processing**:
```python
# Use async for API calls
async def fetch_features():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

## Backup

### Database Backup

```bash
# Daily backup
0 2 * * * cp /data/meta.db /backups/meta.db.$(date +\%Y\%m\%d)
```

### Weights Backup

```bash
# Weekly S3 sync
0 3 * * 0 aws s3 sync /data/weights s3://your-backup-bucket/weights/
```

### Recovery

```bash
# Restore database
cp /backups/meta.db.20260706 /data/meta.db

# Restore weights
aws s3 sync s3://your-backup-bucket/weights/ /data/weights/
```

## Maintenance

### Strategy Updates

1. Update YAML file
2. Reload: `vinu-strategy reload`
3. Test: `vinu-strategy evaluate strategy_name`

### Log Rotation

```bash
# Configure logrotate
cat > /etc/logrotate.d/vinu-strategy<<EOF
/var/log/vinu-strategy.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
}
EOF
```

### Monitoring Alerts

**Alert rules**:
- Error rate > 5%
- Evaluation duration > 10s
- API connection failures
- Disk space > 90%

## Next Steps

- [Version History](../versioning/v1.md)
- [HTTP API Reference](../api-reference/http-api.md)
- [Strategy Authoring](../strategy-authoring/yaml-schema.md)