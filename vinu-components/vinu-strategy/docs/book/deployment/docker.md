# Docker Deployment

## Overview

Deploy vinu-strategy using Docker for containerized execution.

## Docker Image

### Build Image

```bash
# Clone repository
git clone https://github.com/anomalyco/vinu-strategy.git
cd vinu-strategy

# Build image
docker build -t vinu-strategy:latest .
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy strategies and data
COPY strategies/ /app/strategies/
COPY data/ /app/data/

# Set environment variables
ENV FEATURES_API_URL=http://features-api:8000
ENV CORRELATION_API_URL=http://correlation-api:8001
ENV DATA_ROOT=/app/data
ENV STRATEGIES_DIR=/app/strategies

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run server
CMD ["vinu-strategy", "serve"]
```

## Running Container

### Basic Run

```bash
docker run -d \
  --name vinu-strategy \
  -p 8000:8000 \
  -v $(pwd)/strategies:/app/strategies \
  -v $(pwd)/data:/app/data \
  -e FEATURES_API_URL=http://host.docker.internal:8000 \
  -e CORRELATION_API_URL=http://host.docker.internal:8001 \
  vinu-strategy:latest
```

### Docker Compose

```yaml
version: '3.8'

services:
  vinu-strategy:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./strategies:/app/strategies
      - ./data:/app/data
    environment:
      - FEATURES_API_URL=http://features-api:8000
      - CORRELATION_API_URL=http://correlation-api:8001
      - HOST=0.0.0.0
      - PORT=8000
    depends_on:
      - features-api
      - correlation-api
    restart: unless-stopped

  features-api:
    image: vinu-features:latest
    ports:
      - "8000:8000"
    restart: unless-stopped

  correlation-api:
    image: vinu-correlation:latest
    ports:
      - "8001:8001"
    restart: unless-stopped
```

**Run**:
```bash
docker-compose up -d
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FEATURES_API_URL` | vinu-features API URL | - |
| `CORRELATION_API_URL` | vinu-correlation API URL | - |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `DATA_ROOT` | Data directory | `/app/data` |
| `STRATEGIES_DIR` | Strategies directory | `/app/strategies` |

### Volume Mounts

| Mount | Purpose |
|-------|---------|
| `./strategies:/app/strategies` | Strategy YAML files |
| `./data:/app/data` | Weight storage and metadata |

## Production Deployment

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vinu-strategy
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vinu-strategy
  template:
    metadata:
      labels:
        app: vinu-strategy
    spec:
      containers:
        - name: vinu-strategy
          image: vinu-strategy:latest
          ports:
            - containerPort: 8000
          env:
            - name: FEATURES_API_URL
              value: "http://features-api:8000"
            - name: CORRELATION_API_URL
              value: "http://correlation-api:8001"
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: vinu-strategy
spec:
  selector:
    app: vinu-strategy
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
```

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Logs

```bash
# View logs
docker logs -f vinu-strategy

# View logs with timestamps
docker logs -f --timestamps vinu-strategy
```

### Stats

```bash
docker stats vinu-strategy
```

## Scaling

### Horizontal Scaling

```bash
kubectl scale deployment vinu-strategy --replicas=5
```

### Resource Limits

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

## Next Steps

- [Production Setup](production.md)
- [HTTP API Reference](../api-reference/http-api.md)
- [Strategy Authoring](../strategy-authoring/yaml-schema.md)