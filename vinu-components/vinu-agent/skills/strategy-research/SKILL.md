---
name: strategy-research
description: When and how to call run_research to drive the vinu-research quant-coder/backtest/risk-critic refinement loop
category: strategy
---

## Strategy Research — Using `run_research`

`run_research` calls `vinu-research`'s multi-iteration loop: generate a candidate
strategy → backtest it via `vinu-simulator` → apply a risk critic → refine → repeat
until PASS, STOP, or max iterations. It is the tool for cases where you need a
strategy *generated or tuned*, not just evaluated once (use `run_strategy` /
`run_backtest` for a single evaluation of an already-known strategy).

### When to use it
- The user wants a new strategy idea explored ("try a mean-reversion approach on
  AAPL") — the loop's own quant-coder writes and iterates the code.
- The user wants an existing idea tuned to hit a target Sharpe / max-drawdown —
  pass the idea as `idea` and let refinement iterate on it.
- The user wants a portfolio-level check across correlated tickers — pass
  `universe` (comma-separated) alongside `symbol`; the same strategy runs on each
  name and results are aggregated with a correlation matrix and beta-hedge overlay.

### Before running
- Always try `dry_run=true` first for a new/unfamiliar `idea` + date range — it's
  a cheap way to catch bad inputs (invalid symbol, malformed dates) before paying
  for a full multi-iteration run.
- Keep `from_date`/`to_date` at least several months apart — the loop carves a
  trailing holdout slice internally, so very short ranges may run without holdout
  gating (less trustworthy PASS verdicts).
- Only pass `indicators` if the idea references specific ones by name; otherwise
  the service defaults to `sma_20, sma_50, rsi_14`.

### Reading the response
The response JSON includes:
- `status`: `"done"` or `"failed"`.
- `best_sharpe`, `best_max_dd`, `best_iteration`, `total_iterations`.
- `report_md`: a full human-readable report — surface this to the user rather
  than re-deriving your own summary from the raw metrics.
- `portfolio` (only present when `universe` was used): correlation matrix,
  raw vs. hedged Sharpe, final beta estimate.

### Telling the user a strategy isn't good
The loop's own risk critic already does this — a low `best_sharpe`, a `STOP`
verdict, or a `report_md` that calls out drawdown/overfitting concerns *is* the
"this idea doesn't work, here's why" answer. Relay its reasoning rather than
independently re-judging the numbers; the critic's verdict already accounts for
walk-forward validation and the holdout check the raw metrics alone don't show.
