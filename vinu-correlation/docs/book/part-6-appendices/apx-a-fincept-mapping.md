# Appendix A — Fincept step → Vinu module mapping

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Status** | DRAFT |

| Fincept step | Vinu module | Status |
|-------------|-------------|--------|
| News → Price correlation | `engine/correlation.py` | DONE |
| Event study impact | `engine/impact.py`, `engine/event_study.py` | DONE |
| Sentiment → Return | `engine/correlation.py` (sentiment_return_corr) | DONE |
| Granger causality | `engine/granger.py` | DONE |
| Drawdown attribution | `engine/drawdown.py` | DONE |
| News volume baseline | `engine/baseline.py` | DONE |
| Session-aware windows | `engine/market_hours.py` | DONE |
| Multi-window impact | `engine/impact.py` (5m/15m/30m/1h/1d) | DONE |
| Bootstrap CI | `engine/correlation.py` | DONE |
| Thread aggregation | `engine/impact.py` (aggregate_by_thread) | DONE |
