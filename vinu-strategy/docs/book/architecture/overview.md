# Architecture Overview

## System Architecture

vinu-strategy is designed as a **modular, pipeline-based decision fusion engine** that transforms raw market data into actionable portfolio weights.

## High-Level Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        vinu-strategy                            |
├─────────────────────────────────────────────────────────────────┤
│                                                                 |
│  Input Layer                                                    |
│  +----------------+    +----------------+    +-------------+   |
│  | vinu-features  |    |vinu-correlation|    | Strategy    |   |
│  | API            |    | API            |    | YAML Config |   |
│  +----------------+    +----------------+    +-------------+   |
│         |                    |                  |              |
│         v                    v                  v              |
│  +-----------------------------------------------------------+ |
│  |                    StrategyService                        | |
│  +-----------------------------------------------------------+ |
│         |                    |                  |              |
│         v                    v                  v              |
│  +-----------------------------------------------------------+ |
│  |                    WeightPipeline                         | |
│  |  +------------+  +--------------+  +----------+  +------+ | |
│  |  | Selection  |->| Allocation   |->| Timing   |->| Risk | | |
│  |  +------------+  +--------------+  +----------+  +------+ | |
│  +-----------------------------------------------------------+ |
│         |                    |                  |              |
│         v                    v                  v              |
│  Output Layer                                                 |
│  +----------------+    +----------------+    +-------------+   |
│  | Parquet Storage|    |  Metadata DB   |    | HTTP API    |   |
│  +----------------+    +----------------+    +-------------+   |
│                                                                 |
└─────────────────────────────────────────────────────────────────┘
```

## Component Descriptions

### 1. StrategyService

**Location**: `vinu_strategy/service.py`

The central orchestrator that:
- Loads and validates strategy configurations
- Fetches features and correlation data from external APIs
- Executes the pipeline
- Stores results and metadata

**Key Methods**:
- `evaluate()` - Main entry point for strategy execution
- `list_strategies()` - List registered strategies
- `get_weights()` - Retrieve historical weights
- `get_runs()` - Get run history

### 2. WeightPipeline

**Location**: `vinu_strategy/engine/pipeline.py`

A 4-stage pipeline that transforms signals into weights:

1. **Selection**: Filters universe to candidates
2. **Allocation**: Assigns initial weights
3. **Timing**: Adjusts weights based on rules
4. **Risk**: Normalizes weights within constraints

### 3. Storage Layer

**Location**: `vinu_strategy/storage/`

- **Weights**: Parquet files organized by strategy and year
- **Metadata**: SQLite database for runs and strategy registry

### 4. HTTP API

**Location**: `vinu_strategy/server/`

FastAPI-based REST endpoints for:
- Strategy management
- Evaluation triggers
- Data retrieval
- History queries

## Design Principles

### 1. Separation of Concerns

Each pipeline stage has a single responsibility:
- Selection = **which** symbols to include
- Allocation = **how much** to allocate
- Timing = **when** to adjust
- Risk = **constraints** to enforce

### 2. Configurability

Everything is YAML-configurable:
- Method selection per stage
- Parameters for each method
- Rule definitions for timing

### 3. Testability

- Pure functions where possible
- Mockable clients for features/correlation
- Comprehensive test coverage

### 4. Extensibility

- Custom methods can be registered
- New features from vinu-features
- New correlation fields from vinu-correlation

## Data Flow

1. **Input**: Strategy YAML + Universe symbols
2. **Feature Fetch**: Parallel HTTP calls to vinu-features API
3. **Correlation Fetch**: Parallel HTTP calls to vinu-correlation API
4. **Pipeline Execution**: Sequential stage processing
5. **Output**: Portfolio weights stored in Parquet
6. **Metadata**: Run logged to SQLite

## Concurrency Model

- **Feature fetching**: ThreadPoolExecutor with 10 workers
- **Correlation fetching**: ThreadPoolExecutor with 10 workers
- **Pipeline execution**: Sequential (single-threaded)
- **HTTP server**: Async (uvicorn + FastAPI)

## Error Handling

- **Feature fetch failures**: Return empty dict, continue with other symbols
- **Correlation fetch failures**: Return empty dict, continue with other symbols
- **Pipeline errors**: Raise exception, log to run history
- **Storage errors**: Log warning, continue execution

## Performance Considerations

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Feature fetch | O(n) parallel | n = universe size |
| Correlation fetch | O(n) parallel | n = universe size |
| Selection | O(n log n) | Sorting for top_n |
| Allocation | O(n) | Linear pass |
| Timing | O(n * r) | r = number of rules |
| Risk | O(n) | Linear pass |
| Storage write | O(1) | Append to Parquet |

## Future Enhancements

- [ ] Scheduler for automatic rebalancing
- [ ] Backtesting framework
- [ ] Performance optimization for large universes
- [ ] Caching layer for feature/correlation data
- [ ] Web UI enhancements for debugging