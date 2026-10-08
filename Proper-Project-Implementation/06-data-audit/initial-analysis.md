# Data audit: vinu-initial-analysis

Checked 2026-10-08 on the running stack (`initial-analysis-api`; `/data/analysis/<SYMBOL>/<angle>/<bar size>/tier2/*.parquet`, 355 MB; database `vinu_initial_analysis_runs.db`).

## What triggers it
- **On demand:** `POST /initial-analysis/run/{ticker}` and the CLI run an "angle" (a named analysis) per symbol and bar size. For each run the runner fetches bars from stock-price and articles from news (cached once per run), computes, writes a parquet file and a row in `runs`.
- 5,452 runs so far over 50 symbols, 22 angle names, 9 bar sizes (1min to 6M); 5,439 completed, 13 errors. The newest analysis window in the files ends 2026-10-01.

## Data items

### I1 Angle result files  `analysis/<SYMBOL>/<angle>/<bar>/tier2/<SYM>_<angle>_<bar>_<from>_<to>_<n>_<hash>.parquet` (5,441 files)
- **Format:** one table per run; two files per run (full history 2022-01 to 2026-10-01, and a recent window from 2026-06-17). Rows per run range from 1 (a summary row: arima, garch, kalman, exponential smoothing, backtesting, pnl attribution, shock clustering/personality) to tens of thousands (peer_relative_strength 62,800; trend_lifecycle about 67).
- **Access:** `GET /initial-analysis/angle/{angle}/{ticker}`, `/angles`, `/manifest`, `/coverage/{ticker}`, `/symbols`, `/v1/fetch/...`, `/v1/factsheet/{ticker}/{method}`, `/v1/latest-run/{ticker}`; shortcuts `/impact`, `/events`, `/correlation`, `/drawdown`, `/story`.
- **Consumers (found in code):**
  - research: `tools.get_angle_rows` -> `angle_context` (trend_lifecycle, news causality, regime, shock, signal_evidence) -> the strategy-idea prompt. This is the main path to decisions.
  - agent: `angles_tool`, `trade_plan_tool._fetch_angles` (plan checklists), `get_live_decision_context_tool`, `ticker_gate` (`/latest-run`: is a ticker analysed), `audit/freshness`.
  - live: reads `signal_evidence`, `shock_clustering`, `shock_personality`, `regime_analysis`, `pnl_attribution` by name; posts realised trades to `/pnl-attribution/{ticker}/record` (`feedback_loop`).
  - strategy: `correlation_client` (`/impact`, `/correlation`, `/drawdown`).
  - reflection: reads the parquet files directly (`_initial_analysis_parquet.py`), including shock and signal evidence.
  - portfolio, simulator, strategy: use `regime_analysis` by name.
- **Verdict by angle:** `used well`: trend_lifecycle, signal_evidence, shock_personality, shock_clustering, regime_analysis, news_price_causality, pnl_attribution, backtesting_44_metrics, garch. `named only in the agent` (not in research, live, portfolio): drawdown_deep_dive, peer_relative_strength, exponential_smoothing, kalman_filters, arima, trend_session_structure, search_trends.

### I2 Run log  `runs` (5,452 rows in `vinu_initial_analysis_runs.db`)
- **Format:** `symbol, angle_name, run_id, analysis_from/until, stored_at, status, error, row_count, granularity, tier, duration_seconds`. It decides which file is the "latest" for a symbol/angle/bar.
- **Consumers:** the storage layer itself, `/latest-run`, `/coverage`, `ticker_gate`. Older runs are kept (up to 4 per symbol/angle on 1D), never deleted. **Verdict:** `used well`.
- **Failures (13):** seven are the model angles (chronos, dlinear, itransformer, kronos, lpatchtst, lstm, patchtst) hitting the dormant models container, by design; the rest are mostly `stock-api` read timeouts / broken connections on 1-minute bars (arima, backtesting).

### I3 Stray and absent stores
- `run_log.db` and `meta.db` exist and have no tables (leftovers). The batch tracker `angle_run_status` (planned jobs, retries, heartbeat) has no table in any live database, so the retry and heartbeat bookkeeping described in the code is not in use.

## Where angles reach a decision
angles -> research prompt (strategy ideas) and the validation gates; agent trade plans and the live-decision context; live reads regime/shock/signal evidence for its own checks. They do not set sizes directly.
