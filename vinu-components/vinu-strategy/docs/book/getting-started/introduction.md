# Introduction

## What is vinu-strategy?

**vinu-strategy** is a decision fusion layer that combines signals from **vinu-features** and **vinu-correlation** APIs to generate target portfolio weights for trading strategies.

### Core Purpose

The system takes technical indicators, price momentum, volume data, and correlation signals from external APIs, processes them through a configurable pipeline, and outputs optimized portfolio weights that respect risk constraints.

### Key Features

- **Modular Pipeline**: Selection, allocation, timing, and risk stages can be customized per strategy
- **YAML Configuration**: Define strategies without code using a declarative YAML format
- **Rule-Based Timing**: Implement complex trading logic with a flexible rules DSL
- **Risk Management**: Built-in risk normalization with support for long/short positions
- **REST API**: Full HTTP API for strategy management and evaluation
- **CLI Tools**: Command-line interface for evaluation, scheduling, and management

### Architecture Overview

```
┌─────────────────┐    vinu-features    vinu-correlation
│                │    API              API
│  Strategy YAML │─────>───────────────>──────────────┐
│                │    (indicators)     (correlations)│
└────────┬────────┘                              (signals)
        │
         v
┌─────────────────────────────────────────────────────┐
│                    Pipeline                         |
│  Selection  ->  Allocation  ->  Timing  ->  Risk   |
└─────────────────────────────────────────────────────┘
        │
         v
┌─────────────────┐
│  Portfolio      |
│  Weights        |
│  (Parquet DB)   |
└─────────────────┘
```

### Use Cases

1. **Trend Following**: MA crossovers, momentum strategies
2. **Mean Reversion**: RSI-based, Bollinger band strategies
3. **News-Aware Trading**: Incorporate correlation signals from news events
4. **Risk-Adjusted Portfolios**: Multi-asset allocation with position limits

### Getting Started

1. Install the package: `pip install vinu-strategy`
2. Configure your API endpoints in `.env`
3. Add strategy YAML files to `strategies/` directory
4. Run `vinu-strategy reload` to register strategies
5. Evaluate with `vinu-strategy evaluate ma_crossover AAPL MSFT`

### System Requirements

- Python 3.10+
- vinu-features API (HTTP endpoint)
- vinu-correlation API (HTTP endpoint)
- 1GB+ RAM for moderate portfolios
- Optional: Docker for containerized deployment