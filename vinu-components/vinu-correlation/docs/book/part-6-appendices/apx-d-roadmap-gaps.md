# Appendix D — Roadmap gaps & enhancement tasks

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Status** | DRAFT |

## Enhancement tasks

| ID | Task | Priority | Notes |
|----|------|----------|-------|
| TASK-C01 | Advanced correlation metrics | Medium | Spearman correlation, rolling correlation windows |
| TASK-C02 | Impact + drawdown integration | Medium | Use impact events as drawdown signal |
| TASK-C03 | Batch/multi-symbol compute | Low | Parallel compute across watchlist |
| TASK-C04 | Web UI charts | Low | Time-series charts for correlation + impact |
| TASK-C05 | Cointegration test | Low | Engle-Granger for pairs |
| TASK-C06 | Cross-ticker correlation | Low | Multi-ticker correlation matrix |

## Known gaps

| Gap | Description |
|-----|-------------|
| No real-time streaming | Currently poll-based, no WebSocket push |
| Limited backfill range | Default 30 days of news, no archive query |
| No persistence for correlation matrices | Stored but only computed on demand |
