# Phase 8 — Portfolio-Level Correlation Gate

Status: **not started** · Depends on: Phase 4 · Blocks: —
(Advanced vision — see [02-advanced-vision.md](02-advanced-vision.md))

## What it is

Adds a precondition on strategy promotion: does adding this strategy actually improve the
portfolio, or is it redundant with strategies already running? A strategy can look excellent
in isolation (good Sharpe, passes every Stage 0–2 check) and still be a bad addition if it's
highly correlated with existing live strategies — it adds concentrated risk without adding
diversification, and in a drawdown, correlated strategies lose money together.

Today, nothing in the pipeline checks a candidate strategy against the current live portfolio
before promoting it — Stages 0–2 only evaluate a strategy against its own backtest and its own
research history, never against what's *currently deployed*.

## Impact

**Before this phase:** Promotion is a purely strategy-local decision. Two highly correlated
momentum strategies on different tech tickers could both get promoted independently, each
looking fine alone, while jointly doubling down on the same underlying risk factor.

**After this phase:** Promotion considers marginal contribution to portfolio risk/return — a
strategy that's redundant with the existing book is flagged (not necessarily blocked, but
surfaced) before it's promoted.

## Where changes occur

- `vinu-portfolio` (`vinu-components/vinu-portfolio/`) — this package already exists;
  confirm at implementation time what portfolio-level analytics it currently exposes (position
  correlation, risk contribution, etc.) before building new logic — reuse rather than
  duplicate.
- `vinu-research/vinu_research/service.py` — before the existing approval flow (`service.py`
  lines ~229-260) promotes a strategy's code into `strategy_store.db`, add a call out to
  `vinu-portfolio` requesting the candidate strategy's correlation/marginal-risk-contribution
  against the current live book (equity curve correlation is the simplest version; a
  factor-exposure comparison is a stronger version worth considering once the simple version
  ships).
- Result surfaced alongside Stage 2's comparison angles — likely a new field on whatever
  response `service.py` already returns for a completed research run, e.g.
  `portfolio_fit: {correlation_to_book: float, marginal_sharpe_contribution: float, flagged: bool}`.
- `vinu-agent/vinu_agent/tools/trade_plan_tool.py` (Phase 5) — surface `portfolio_fit` as a
  playbook note if a strategy is highly correlated with an existing live position.

## How to test it

- Unit test: a candidate strategy with an equity curve nearly identical to an existing live
  strategy's equity curve should be flagged with high `correlation_to_book`.
- Unit test: a candidate strategy with a low/negative correlation to the existing book should
  show a positive `marginal_sharpe_contribution` and not be flagged.
- Integration test: confirm the approval flow still succeeds (this is informational, not a hard
  block, per the base design intent) when a strategy is flagged, but that the flag is visibly
  attached to the promoted record.
