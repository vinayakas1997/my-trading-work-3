---
name: adding-a-new-angle
status: guide
purpose: plain-language guide for adding a new angle to vinu-initial-analysis — the config pattern, the walk-forward pattern, and every rule a new angle's own code and docs are expected to follow, distilled from actually building and real-data-validating all 31 existing angles.
---

# Adding a New Angle — A Practical Guide

An "angle" is one lens on price/news data — `lstm`, `garch`,
`news_price_causality`, `regime_analysis`, and so on, each living in its
own `vinu-initial-analysis/vinu_initial_analysis/angles/<name>/` folder.
This guide is what to read before adding a new one, distilled from
actually building and real-data-validating all 31 angles currently in
the project (`06-implementation-of-each-angles/plan.md` has the
per-angle record).

## The four files a new angle needs

| File | Required? | What it's for |
|---|---|---|
| `spec.yaml` | Always | Declares the angle's `time_formats` (which timeframes it runs on), purpose, and output shape. |
| `compute.py` | Always | The single-shot `compute()` entry point plus, for forecaster angles, an extracted `_fit_and_forecast()`/`_forecast()` helper both `compute()` and `backtest.py` call. |
| `backtest.py` | Forecaster angles (Group A) and most non-forecaster angles (Group B) | Walk-forward or custom backtest glue. See "Which backtest pattern" below. |
| `tests/test_<name>*.py` | Always | Real unit tests — see "Testing" below. |

`_tagging.py`/`signal_contract.py` (`tag_row`) and `_helpers.py`
(`pinball_loss`, `pearson_with_ci`, `mean_with_ci`, `calendar_quarter_key`,
etc.) are shared across every angle — check `_helpers.py` before writing
a new statistical helper; it may already exist there from another angle.

## The config pattern — how to make a threshold configurable

Every angle that has a "minimum observations before I can compute at
all" floor (almost all Group A forecasters, and several Group B angles)
declares it as a plain module-level constant in `compute.py`, wired
through `vinu_initial_analysis/config.py`'s `get_angle_setting()`:

```python
from vinu_initial_analysis.config import DEFAULT_MIN_OBSERVATIONS, get_angle_setting

ANGLE_NAME = "my_new_angle"
MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", DEFAULT_MIN_OBSERVATIONS)
```

This makes the threshold overridable via `.env` (or the real environment)
as `VINU_MY_NEW_ANGLE_MIN_OBSERVATIONS=<value>` without touching code —
matching the `.env` pattern `config.py` already uses everywhere else
(`VINU_STAGE1_START_DATE`, `VINU_TIER2_PERIOD_MONTHS`, etc.).

**`DEFAULT_MIN_OBSERVATIONS` (100) is a shared fallback, not a rule.**
Most angles converged on 100 through this project's own consistency
sweep (ARIMA/DLinear/LSTM/... were each individually raised from smaller
values to 100 for comparable real-data checks) — but several angles have
a real, different, already-decided reason to differ, and keep their own
value as the `default` argument instead of `DEFAULT_MIN_OBSERVATIONS`:

| Angle | Value | Why |
|---|---|---|
| `chronos` | 512 | Fixed pretrained-model context requirement (Amazon's own stated default). |
| `kronos` | 30 | Its own pretrained-model requirement. |
| `shock_personality` | 21 | Real floor: its rolling windows' own requirement, not candle count. |
| `regime_analysis` | 141 (derived: `VOL_BASELINE_WINDOW + VOL_WINDOW`) | A genuinely computed floor, not an arbitrary constant. |
| `tips_regime_aware_transformer` | 120 | Its own decided design — needs a regime-window + lookback-window margin 100 doesn't give. |
| `timer_timerxl` | 100, but **guarded** — see below | Real architectural requirement, not just a convention. |

`get_angle_setting()` is generic beyond `min_observations` too — e.g.
`timesfm`/`timer_timerxl` also use it for `MAX_CONTEXT`:
```python
MAX_CONTEXT = get_angle_setting(ANGLE_NAME, "max_context", 1024)
```

**If your angle's threshold has a real architectural floor** (not just a
convention), guard the override the way `timer_timerxl` does — an env
var that violates a real constraint should be rejected outright, not
silently accepted:
```python
MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", 100)
if MIN_OBSERVATIONS < PATCH_SIZE:
    raise ValueError(
        f"VINU_TIMER_TIMERXL_MIN_OBSERVATIONS={MIN_OBSERVATIONS} is below "
        f"PATCH_SIZE={PATCH_SIZE} -- the real model can never produce even "
        "one patch below this floor and silently falls through to the "
        "fallback proxy, the exact bug this angle's own fix corrected."
    )
```
(This is a real, previously-fixed bug in `timer_timerxl` — raising
`MIN_OBSERVATIONS` past `PATCH_SIZE` was the actual fix; the guard exists
so a careless env override can't quietly reintroduce it.)

**Don't** wire a shared/global env var that overrides every angle at
once — this was explicitly decided against (see
`06-implementation-of-each-angles`'s session log): a single angle needs
to be tunable without affecting every other angle's already-validated
behavior.

## Which backtest pattern to use

Check `06-implementation-of-each-angles/parallel-backtest-infra.md`'s
group table before writing `backtest.py` — it's the authoritative,
directly-checked-against-every-angle classification:

1. **Forecaster with a fixed context window** (pretrained inference, or a
   trained-from-scratch model that only looks at a bounded recent
   window): call `vinu_tools.compute.backtest.walk_forward.run_walk_forward()`
   with `window=<your MIN_OBSERVATIONS/MIN_BARS constant>` (an int, not
   `"expanding"`). This is what makes your angle eligible for the
   parallel-chunked path (`run_walk_forward_parallel`/
   `run_walk_forward_parallel_batch`) later, with zero extra work — the
   harness only requires a fixed `window`.
2. **Forecaster that genuinely retrains on all history so far** (a true
   expanding-window design): call `run_walk_forward()` with the default
   `window="expanding"`. This is a real methodology choice — full-history
   retraining vs. bounded-lookback retraining — not a default to fall
   into by not thinking about it. It also means your angle can't safely
   use the parallel-chunked path without an explicit decision to switch
   to a bounded window (10 existing angles are in this bucket, tracked as
   an open, undecided item in `parallel-backtest-infra.md`).
3. **Non-forecaster** (a statistic/aggregation over the whole dataset,
   nothing to score against a future bar): custom `backtest.py` glue, no
   `run_walk_forward` at all — see `regime_analysis`, `shock_clustering`,
   `trend_lifecycle` for real examples of this shape.

If your `step_fn` needs to be usable with the parallel harness
(`run_walk_forward_parallel`/`_batch`), it **must be a plain module-level
function**, not a closure or lambda — each worker process pickles a
reference to it, not any captured state. Confirmed directly this
session: a lambda `tag_fn` fails with `AttributeError: Can't get local
object` from the pickler.

## Real-data validation — the actual bar

Every angle in this project was validated against real Alpaca-sourced
market data before being marked done — never synthetic/fabricated data
for the "does this actually work" question (synthetic data is fine for
unit tests of specific logic branches, e.g. edge cases that don't occur
in the cached real window). Concretely:

- Fetch real bars via `vinu_stock.query.engine.fetch_candles()` (or, if
  your angle needs full real history and the corpus is large, aggregate
  directly from the archive/live parquet files the same way
  `vinu_stock.query.aggregate.aggregate_bars()` does).
- Run your angle's real `compute()`/backtest against that real data —
  report the real numbers you get, including inconclusive or
  unimpressive ones (several angles this session reported "no
  significant predictability found" honestly rather than fabricating a
  cleaner-looking result).
- Verify the storage round-trip (`storage.write()` then `storage.read()`,
  confirm the data matches) and, if your angle supports grouped queries,
  that `query_slice()`'s aggregation matches a hand-computed pandas
  `groupby` on the same data.
- Write up what you found in `01-implementation.md` (what was built, what
  bugs were found/fixed, what the tests cover) and `02-real-scenario.md`
  (one concrete real example, with real numbers) inside your angle's own
  `06-implementation-of-each-angles/<NN>-<name>/` folder — every existing
  angle has both; match that structure.

## Testing

- Real unit tests, not fabricated/trivial ones — cover the angle's actual
  decision logic (thresholds, status transitions like
  `insufficient_data`, real edge cases).
- If you found and fixed a real bug while building the angle, add a
  regression test that would have caught it (the project's own pattern:
  `pearson_with_ci`'s degenerate-CI test, `timer_timerxl`'s
  below-PATCH_SIZE test, `_default_n_workers`'s core-count test — every
  fixed bug this session has a test tied to it, not just a docs mention).
- Run the angle's own test file, then the full `vinu-initial-analysis`
  suite, before considering the angle done — confirm the count of
  passed/failed against the baseline in `plan.md`'s most recent entry.

## Fixing bugs found while building — don't just flag them

If you find a real bug (in your new angle's own code, or in shared
infrastructure it depends on) while building, fix it — don't leave a
comment and move on. If the bug is in shared code affecting other
angles, track it in `06-implementation-of-each-angles/known-issues.md`
(one entry per issue, moved from "Open" to "Resolved" once actually
fixed, with the real before/after numbers) rather than burying it inside
your one angle's own doc — that's what makes it discoverable and
combinable with other cross-cutting fixes later.

## Checklist

- [ ] `spec.yaml` — timeframes, purpose, output shape declared
- [ ] `compute.py` — `ANGLE_NAME` constant, thresholds via `get_angle_setting()`
- [ ] `backtest.py` — right pattern for your angle's real shape (see above)
- [ ] Real unit tests, including a regression test for any bug found
- [ ] Real-data validation against real Alpaca-sourced data (not synthetic)
- [ ] Storage round-trip and (if applicable) `query_slice()` verified
- [ ] `01-implementation.md` + `02-real-scenario.md` written
- [ ] `plan.md`'s status table row added/updated
- [ ] Any cross-cutting bug found tracked in `known-issues.md`
- [ ] Full `vinu-initial-analysis` test suite run, pass count confirmed against baseline

## Related files

- `plan.md` — the status table every angle (including yours, once done) gets a row in.
- `known-issues.md` — cross-cutting bugs, tracked separately from any one angle.
- `parallel-backtest-infra.md` — the parallel-chunking group table (fixed-window vs. expanding-window vs. not-applicable) and what makes an angle eligible.
- `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/config.py` — `get_angle_setting()`, `DEFAULT_MIN_OBSERVATIONS`.
- `../00-project-understanding/03-stage1-planning.md` — where adding angles fits in the project's own build sequence (Step 3).
