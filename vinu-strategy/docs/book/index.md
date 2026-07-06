# vinu-strategy Documentation Book

> Decision fusion layer - combines vinu-features + vinu-correlation signals into target portfolio weights.

## Quick Links

- [Getting Started](getting-started/introduction.md)
- [Strategy Authoring](strategy-authoring/yaml-schema.md)
- [API Reference](api-reference/cli.md)
- [Version History](versioning/v1.md)

## Table of Contents

### Getting Started

- [Introduction](getting-started/introduction.md)
- [Installation](getting-started/installation.md)
- [Quick Start](getting-started/quickstart.md)

### Architecture

- [Overview](architecture/overview.md)
- [Pipeline Design](architecture/pipeline.md)
- [Components](architecture/components.md)
- [Data Flow](architecture/data-flow.md)

### Strategy Authoring

- [YAML Schema](strategy-authoring/yaml-schema.md)
- [Feature Catalog](strategy-authoring/features-catalog.md)
- [Correlation Fields](strategy-authoring/correlation-fields.md)
- [Pipeline Methods](strategy-authoring/pipeline-methods.md)
- [Rules DSL](strategy-authoring/rules-dsl.md)
- [Examples](strategy-authoring/examples.md)

### API Reference

- [CLI](api-reference/cli.md)
- [HTTP API](api-reference/http-api.md)
- [Python API](api-reference/python-api.md)

### Storage

- [Weight Storage](storage/weights.md)
- [Metadata Storage](storage/metadata.md)

### Testing

- [Test Guide](testing/test-guide.md)

### Deployment

- [Docker](deployment/docker.md)
- [Production Setup](deployment/production.md)

### Version History

- [Version 1](versioning/v1.md)
- [Version 2](versioning/v2.md)
- [Version 3](versioning/v3.md)

## About

vinu-strategy is a decision fusion engine that transforms raw market data into optimized portfolio weights through a configurable 4-stage pipeline.

**Key Features**:
- Modular pipeline (selection, allocation, timing, risk)
- YAML strategy configuration
- Rule-based timing logic
- REST API and CLI
- Parquet storage for historical analysis

**Version**: 0.1.0

**License**: MIT

**Repository**: https://github.com/anomalyco/vinu-strategy