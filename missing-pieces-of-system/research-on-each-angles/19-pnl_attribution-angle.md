# 19 — pnl_attribution

- **Angle id:** `pnl_attribution`
- **Cluster:** G — Validation & attribution
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/pnl_attribution/`
  (`compute.py`, `pnl_attribution_ingest.py`; no `backtest.py`/`naive_baseline.py`
  -- there is nothing to backtest, this angle reports realized trades)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Not a forecast or a bars-driven angle at all -- reports real, already-
closed trades' win rate, average win/loss size, and total realized PnL,
both per symbol and broken down per `artifact_id` (whatever produced the
trade). **`compute()` is a documented no-op** -- real data only arrives
via a separate push-fed ingest path
(`pnl_attribution_ingest.ingest_closed_positions`), never through the
normal `/run/{ticker}` sweep.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | A Student's t-distribution confidence interval (`mean ± t × SE`) is an adequate way to report uncertainty for **all** of `win_rate`, `avg_win_pct`, and `avg_loss_pct`. | code's own design (one shared `_rate_with_ci` helper used for all three) |
| A2 | *(Literature)* For a **binomial proportion** specifically (like `win_rate`, built from 0/1 win/loss flags), the equivalent large-sample normal/t-style interval ("Wald interval") is known to perform poorly -- its true coverage can fall well short of the nominal 95% -- unless the sample size is large. | [PN1] |
| A3 | A Wilson score interval (or the simple "add 2 successes and 2 failures" adjusted-Wald approximation to it) keeps coverage close to nominal even at small sample sizes, and is the standard recommended fix. | [PN1] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Wald-type confidence interval for a binomial proportion | "It has been known for some time that the Wald interval performs poorly unless n is quite large." Coverage can be substantially below the stated confidence level, especially for proportions near 0 or 1 and for small samples. | [PN1] |
| R2 | Wilson score interval vs. Wald, across sample sizes | Wilson's score-based interval "yields coverage probabilities close to nominal confidence levels, even for very small sample sizes." The simple "add 2 successes, 2 failures" adjusted-Wald interval behaves similarly. | [PN1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `win_rate`'s confidence interval is computed by the same generic `_rate_with_ci` helper used for `avg_win_pct`/`avg_loss_pct` -- a Student's t-interval around the mean of the underlying values. For `win_rate`, those values are 0/1 win flags, making this a Wald-style interval for a binomial proportion. | Wald-style intervals for a proportion are known to have poor coverage at realistic sample sizes, and can even extend past the valid `[0, 1]` range -- a Wilson-score-style interval is the standard fix [PN1]. | **Real, verifiable methodological gap specific to `win_rate`.** `avg_win_pct`/`avg_loss_pct` are continuous return sizes, where a t-interval is the right, standard tool -- no issue there. `win_rate` is structurally a binomial proportion, and early in any strategy's life (exactly when this attribution matters most for feedback) trade counts are small and win rates often sit near 0 or 1 -- precisely the regime where a Wald/t-style interval is least reliable. A Wilson-score interval (or the Agresti-Coull adjusted-Wald approximation) would be a closer fit for this one field specifically. |
| F2 | `_rate_with_ci` returns `status: "insufficient_sample"` when `n < 2`, and no CI at all -- rather than a wide/degenerate one. | -- | Sensible guard -- avoids reporting a fake-precise interval from a single trade. |
| F3 | `loss_cause` breakdown reads an already-enriched field from upstream (`vinu-live`'s feedback loop), falling back to `"unclassified"` when absent rather than dropping the row. | -- | Reasonable, non-destructive handling of partially-enriched historical data. |
| F4 | `compute()` (the bars-driven entry point) is an explicit, documented no-op, returning `status: "push_fed_not_runner_driven"` rather than silently returning empty or erroring. | -- | Clear, honest self-description -- a caller sweeping `/run/{ticker}` across all angles gets an unambiguous signal that this angle's real data lives elsewhere, not a confusing empty/error result. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

From `aggregate_pnl_attribution` (the real entry point, called by the ingest path):

| Field | Meaning |
|---|---|
| `n_trades` | Count of closed positions in this aggregation. |
| `total_realized_pnl` | Sum of realized PnL across all included trades. |
| `win_rate` | `{mean, n_observations, confidence_interval, status}` -- fraction of trades with positive realized PnL. **See F1** for the CI methodology caveat. |
| `avg_win_pct` / `avg_loss_pct` | Same shape, mean return-on-cost for winning/losing trades respectively. |
| `loss_causes` | Dict of `{cause: count}` from the upstream-enriched `loss_cause` field, `"unclassified"` when absent. |
| `by_artifact` | The same `n_trades`/`total_realized_pnl`/`win_rate`/`avg_win_pct`/`avg_loss_pct`/`loss_causes` block, broken down per `artifact_id` (whichever upstream signal/strategy produced each trade). |
| `closed_positions_json` | Full input history, JSON-serialized (kept as a string specifically so parquet/FastAPI round-tripping doesn't choke on a raw list-of-dicts column) so future ingests can re-aggregate over everything, not just the newest batch. |

From `compute()` (the no-op bars-driven path): only identification fields
plus `status`.

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Real aggregation produced (via `aggregate_pnl_attribution`, the ingest path). | All fields above. |
| `no_data` | `aggregate_pnl_attribution` called with zero closed positions. | Identification fields + `closed_positions_json: "[]"`. |
| `push_fed_not_runner_driven` | The bars-driven `compute()` entry point was called directly (e.g. by a generic all-angles sweep) -- this angle has nothing to compute from bars alone. | Identification fields only. |

Within each `_rate_with_ci` sub-object, its own nested `status` is
`"ok"` or `"insufficient_sample"` (fewer than 2 values) -- independent of
the row's top-level `status`.

## 7. Comprehensive explanation  *(for humans only)*

**Why this angle looks different from every other one researched so
far.** Every other angle in this folder computes something from price
bars (and sometimes news) fetched fresh for a symbol. This one is
fundamentally about **already-realized outcomes** -- actual closed
trades, however they were produced -- so it deliberately breaks the
standard bars-driven pattern: the real logic (`aggregate_pnl_attribution`)
is called directly by a push-fed ingest endpoint, and the bars-driven
`compute()` that every other angle implements is kept only so a generic
sweep across all angles doesn't crash on this one.

**The confidence-interval methodology, and where it's a good fit vs.
not (F1).** `_rate_with_ci` is one shared helper applied to three
different kinds of values: `win_rate` (a 0/1 indicator per trade,
i.e. a true binomial proportion), and `avg_win_pct`/`avg_loss_pct`
(continuous percentage returns). A Student's t-interval is the textbook
right tool for the continuous cases. For a proportion specifically,
though, the equivalent large-sample interval -- essentially what this
helper computes when fed 0/1 values -- is exactly the "Wald interval"
that Agresti & Coull's widely-cited paper shows has real, known coverage
problems: it can understate uncertainty badly at realistic sample sizes,
and can even produce bounds outside the possible `[0, 1]` range for
`win_rate` [PN1]. Their recommended fix (Wilson's score interval, or the
simple "add two wins and two losses before computing a normal-style
interval" approximation to it) is specifically designed to stay reliable
exactly where this angle needs it most: small trade counts, early in a
strategy's or artifact's life, which is when feedback matters most and
when the current interval is least trustworthy.

**Everything else here is solid.** The `insufficient_sample` guard,
honest no-op signaling from `compute()`, and non-destructive handling of
partially-enriched historical rows (`loss_cause` falling back to
`"unclassified"` rather than being dropped) are all sound, defensive
design choices -- the one real finding in this angle is narrow and
specific to `win_rate`'s interval, not the module as a whole.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| PN1 | Agresti & Coull, "Approximate is Better than 'Exact' for Interval Estimation of Binomial Proportions," *The American Statistician* 52(2), 1998, pp. 119 (abstract + introduction) | Wald interval's known poor coverage for a binomial proportion, especially at small sample sizes; Wilson score interval and the "add 2 successes/2 failures" adjusted-Wald approximation as the recommended, more reliable alternatives even at very small n. | https://math.unm.edu/~james/Agresti1998.pdf |
