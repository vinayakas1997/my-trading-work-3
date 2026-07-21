# Future Features — Collected From Inefficiency Audit

> Feature gaps and enhancements discovered during the inefficiency fix sprint.
> These are **not bugs** — they are improvements that would add significant value
> but require new design or development beyond the scope of the audit.

---

## vinu-research

### Pass prior simulation metrics + code to research (Option 1)
- **Discovered in:** [FP-2](one-by-one/FP-2-research-ignores-simulator/solution.md)
- **What:** Extend research API to accept `prior_sim_result` with full simulator output (metrics, trades, equity curve). Feed prior metrics into LLM refinement context so it sees execution quality data.
- **Complexity:** High

### `user_idea=None` validation in `run_research`
- **Discovered in:** [DA-9](one-by-one/DA-9-llm-failure-fresh-template/solution.md)
- **What:** `service.run_research()` doesn't auto-propose from angles when `user_idea=None` (unlike `ensure_strategy`). If None passes through, undefined behavior.
- **Complexity:** Low — mirror `ensure_strategy`'s `_propose_idea` call

### Research report "not worth pursuing" conclusion
- **Discovered in:** [DA-9](one-by-one/DA-9-llm-failure-fresh-template/solution.md)
- **What:** Report shows metrics but never explicitly concludes if a strategy is unsuitable for a stock. Add a clear statement at the top.
- **Complexity:** Low

### Multi-stock strategy exploration
- **Discovered in:** [DA-9](one-by-one/DA-9-llm-failure-fresh-template/solution.md)
- **What:** Auto-try a strategy idea on multiple stocks and rank by deflated Sharpe. The `universe` parameter exists but is manual.
- **Complexity:** Medium

### Strategy-stock fit assessment
- **Discovered in:** [DA-9](one-by-one/DA-9-llm-failure-fresh-template/solution.md)
- **What:** Classify stocks by regime (trending/range/volatile) and strategy signals (momentum/mean-reversion/breakout). Evaluate fit before running research.
- **Complexity:** High

### Auto-suggest alternative stocks
- **Discovered in:** [DA-9](one-by-one/DA-9-llm-failure-fresh-template/solution.md)
- **What:** When a strategy fails validation for stock A, suggest stocks B/C/D where the same signals might work better.
- **Complexity:** High

---

## vinu-stock-price

*(none yet — open for future contributions)*

## vinu-news

*(none yet — open for future contributions)*

## vinu-tools

*(none yet — open for future contributions)*

## vinu-initial-analysis

*(none yet — open for future contributions)*

## vinu-strategy

*(none yet — open for future contributions)*

## vinu-simulator

### Expose validation results via API endpoint
- **Discovered in:** [DA-37](one-by-one/DA-37-simulator-validation-suite-every-run/solution.md)
- **What:** Add `GET /results/{run_id}/validation` to return Monte Carlo, bootstrap, walk-forward results from stored run card
- **Complexity:** Low

### Defer validation to background task
- **Discovered in:** [DA-37](one-by-one/DA-37-simulator-validation-suite-every-run/solution.md)
- **What:** Return simulation immediately, queue validation work async, append results to run_card when done
- **Complexity:** High

## run_pipeline.py

*(none yet — open for future contributions)*
