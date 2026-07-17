# Chapter 02 — Concepts & glossary

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Status** | DRAFT |
| **Prerequisites** | ch00 |

## Glossary

| Term | Definition |
|------|------------|
| **Impact** | Measured price change within a window (5m, 15m, 30m, 1h, 1d) after a news article |
| **Correlation** | Pearson correlation between news volume/sentiment and price returns |
| **Lag analysis** | Cross-correlation at different time offsets (0, 15, 30, 60 min) to find the best lead-lag relationship |
| **Granger causality** | Statistical test for whether news volume predicts future price returns |
| **Event study** | Abnormal return computation around news events with pre-event estimation window |
| **Drawdown** | Peak-to-trough price decline >= configurable threshold (default -3%) |
| **Drawdown attribution** | Decomposition of a drawdown into news-driven, market-beta, and unexplained components |
| **Baseline** | Rolling mean and stddev of news volume per session (pre-market, regular, after-hours) |
| **Deviation** | Z-score of current news volume relative to baseline, classified as normal/elevated/high/critical |
| **Session** | Market session (pre-market 8–13 UTC, regular 13–20 UTC, after-hours 20–24 UTC, closed 0–8 UTC) |
| **Incremental compute** | Only processes new data since the last computation timestamp |
| **Continuous loop** | Repeated compute + sleep cycle for ongoing monitoring |
