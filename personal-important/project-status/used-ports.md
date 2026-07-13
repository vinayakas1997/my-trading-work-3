# Used Ports

## Component Overview

| Component | Frontend/API Port | Backend/Ingest Port |
|-----------|-------------------|---------------------|
| **vinu-news** | 8080 | N/A (no separate ingest port) |
| **vinu-stock-price** | 8081 | N/A (no separate ingest port) |
| **vinu-features** | 8082 | N/A (no separate ingest port) |
| **vinu-correlation** | 8083 | N/A (no separate ingest port) |
| **vinu-strategy** | 8084 | N/A (no separate ingest port) |
| **vinu-simulator** | 8085 | N/A (no separate ingest port) |
| **vinu-research** | N/A (CLI-only) | N/A |

## Detailed Port Information

### 1. vinu-news (Port: 8080)
- **Frontend/API**: `news-api` service exposes port 8080
- **Command**: `vinu-news-serve --host 0.0.0.0 --port 8080`
- **Backend/Ingest**: `news-ingest` service (no external port, runs internally)
- **Dependencies**: None

### 2. vinu-stock-price (Port: 8081)
- **Frontend/API**: `stock-api` service exposes port 8081
- **Command**: `vinu-stock-serve --host 0.0.0.0 --port 8081`
- **Backend/Ingest**: `stock-ingest` service (no external port, runs internally)
- **Dependencies**: None

### 3. vinu-features (Port: 8082)
- **Frontend/API**: `features-api` service exposes port 8082
- **Command**: `vinu-features serve --host 0.0.0.0 --port 8082`
- **Backend/Ingest**: `features-worker` service (no external port, runs internally)
- **Dependencies**: 
  - Connects to `stock-api:8081`

### 4. vinu-correlation (Port: 8083)
- **Frontend/API**: `correlation-api` service exposes port 8083
- **Command**: `vinu-correlation-serve --host 0.0.0.0 --port 8083`
- **Backend/Ingest**: `correlation-compute` service (no external port, runs internally)
- **Dependencies**: 
  - Connects to `news-api:8080`
  - Connects to `stock-api:8081`

### 5. vinu-strategy (Port: 8084)
- **Frontend/API**: `strategy-api` service exposes port 8084
- **Command**: `vinu-strategy serve --host 0.0.0.0 --port 8084`
- **Backend/Ingest**: N/A (on-demand evaluation)
- **Dependencies**: 
  - Connects to `features-api:8082`
  - Connects to `correlation-api:8083`

### 6. vinu-simulator (Port: 8085)
- **Frontend/API**: `simulator-api` service exposes port 8085
- **Command**: `vinu-simulator serve --host 0.0.0.0 --port 8085`
- **Backend/Ingest**: N/A (on-demand simulation)
- **Dependencies**: 
  - Connects to `strategy-api:8084`
  - Connects to `stock-api:8081`
  - Connects to `features-api:8082`

### 7. vinu-research (No API port)
- **Interface**: CLI-only (`vinu-research run "..."`)
- **Backend**: Optional HTTP server can be started for management (not a dedicated API)
- **Dependencies**: 
  - Connects to `simulator-api:8085`
  - Connects to `features-api:8082`
  - Connects to `correlation-api:8083`

## Port Overlap Check

**Result: NO OVERLAPS DETECTED**

All 7 components use distinct, non-overlapping ports:
- vinu-news: **8080**
- vinu-stock-price: **8081**
- vinu-features: **8082**
- vinu-correlation: **8083**
- vinu-strategy: **8084**
- vinu-simulator: **8085**
- vinu-research: **CLI-only (no API port)**

Each component has a unique port assignment, ensuring no conflicts between services.
