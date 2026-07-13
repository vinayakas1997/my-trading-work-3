# Installation

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Access to vinu-features and vinu-correlation HTTP APIs

## Installation Options

### Option 1: pip Install (Recommended)

```bash
pip install vinu-strategy
```

This installs the package and makes the `vinu-strategy` CLI available.

### Option 2: From Source

```bash
git clone https://github.com/anomalyco/vinu-strategy.git
cd vinu-strategy
pip install -e .
```

### Option 3: Docker

```bash
docker pull anomalyco/vinu-strategy:latest
docker run -v $(pwd)/strategies:/app/strategies \
  -e FEATURES_API_URL=http://features-api:8000 \
  -e CORRELATION_API_URL=http://correlation-api:8000 \
  anomalyco/vinu-strategy:latest
```

## Configuration

### Environment Variables

Create a `.env` file in your working directory:

```env
# API Endpoints
FEATURES_API_URL=http://localhost:8000
CORRELATION_API_URL=http://localhost:8001

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Data Paths
DATA_ROOT=./data
STRATEGIES_DIR=./strategies

# Risk Parameters
MAX_WEIGHT=0.25
CASH_FLOOR=0.10

# Optional: Shared watchlist
SHARED_WATCHLIST_PATH=./watchlist.json
```

### Configuration File

Alternatively, create `config.yaml`:

```yaml
features_api_url: http://localhost:8000
correlation_api_url: http://localhost:8001
host: 0.0.0.0
port: 8000
data_root: ./data
strategies_dir: ./strategies
max_weight: 0.25
cash_floor: 0.10
rebalance_freq: daily
```

## Verifying Installation

```bash
# Check CLI is available
vinu-strategy --help

# List strategies (should show empty list initially)
vinu-strategy list

# Start the API server
vinu-strategy serve
```

## Dependencies

### Required

- `fastapi>=0.110` - Web framework
- `uvicorn[standard]>=0.27` - ASGI server
- `pydantic>=2.0` - Data validation
- `python-dotenv>=1.0` - Environment loading
- `httpx>=0.27` - HTTP client
- `pyarrow>=15.0` - Parquet file handling
- `pyyaml>=6.0` - YAML parsing
- `numpy>=1.24` - Numerical computing
- `pandas>=2.0` - Data manipulation
- `scipy>=1.11` - Scientific computing

### Optional (Development)

- `pytest>=8.0` - Testing framework
- `httpx>=0.27` - Async HTTP testing

## Troubleshooting

### Issue: `vinu-strategy: command not found`

**Solution**: Ensure the package is installed in your active Python environment:

```bash
which python
python -m pip install vinu-strategy
```

### Issue: API connection errors

**Solution**: Verify your API endpoints are reachable:

```bash
curl http://localhost:8000/health
curl http://localhost:8001/health
```

### Issue: Strategy not found

**Solution**: Reload the strategy registry after adding YAML files:

```bash
vinu-strategy reload
```

## Next Steps

- [Quick Start Guide](quickstart.md)
- [Strategy Authoring](../strategy-authoring/yaml-schema.md)
- [API Reference](../api-reference/cli.md)