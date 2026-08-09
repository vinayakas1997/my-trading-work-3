# pnl_attribution (AAPL) -- PnL Attribution

**pnl_attribution (AAPL):** Realized-trade PnL statistics per symbol -- win rate, average win/loss, trade count -- computed from Phase 6 (vinu-live) execution logs. Every field includes sample size and confidence interval. Deviates from the standard runner-driven angle pattern: its natural input is closed positions/fills, not price bars, so it is push-fed via POST /pnl-attribution/{symbol}/record (Phase 7's feedback loop) rather than pulled by AngleRunner from bars/news. `compute()` still exists with the standard signature so a generic `/run/{ticker}` sweep doesn't error, but it is a documented no-op there -- real population happens through the ingest path (`pnl_attribution_ingest.py`), which calls `aggregate_pnl_attribution` directly and writes via `AngleStorage.write()`. Output: PnL attribution results with confidence intervals

## Status counts by time format
1D: analysis_at = 2026-08-09T14:00:23.819131+00:00: n=1 (of 1)
1D: angle = pnl_attribution: n=1 (of 1)
1D: status = no_data: n=1 (of 1)
1D: closed_positions_json = []: n=1 (of 1)

_This exact document is also available live via `GET /v1/stage1/vinu-initial-analysis/factsheet/AAPL/pnl_attribution`. For the raw underlying rows behind any cell (not just its session/time-format average), call `GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/pnl_attribution/fb10e1ec51b3` (`{time_range}` filled in with whatever window you need; the run_id above pins the exact computation this table's 1D numbers came from). This document states values only -- it does not compare, rank, or advise between them._