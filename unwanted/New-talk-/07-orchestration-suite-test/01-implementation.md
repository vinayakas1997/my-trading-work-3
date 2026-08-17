---
name: orchestration-suite-test-implementation
status: phase-1-done
purpose: the real record of building the angle registry, a real classification mistake found and corrected when directly asked to account for it, and the bugs found and fixed along the way.
---

# 07 — Orchestration Suite Test — Implementation Record

## What was built

**`vinu-initial-analysis/vinu_initial_analysis/storage/orchestration_registry.py`**
(new) — `ANGLE_REGISTRY` (24 entries, final: angle name → its real
backtest entry point + a call-shape tag), `build_work_fn()` (assembles
the right positional/keyword call for one angle/symbol), `build_batch_jobs()`
(cross-product of symbols × angles → `(symbol, angle_name, work_fn)`
tuples for `run_batch()`). Deliberately kept separate from
`orchestration.py` (the generic tracker built in
`06-implementation-of-each-angles`), the same separation `backtest.py`
files keep from the generic `walk_forward.py` harness — the registry is
angle-specific glue, not part of the generic tracking layer.

Every angle's real `backtest.py` signature was read directly (not
assumed) before writing the registry — they fall into 4 call shapes:

| Shape | Angles | Real call |
|---|---|---|
| `std` | `chronos`, `drawdown_deep_dive`, `exponential_smoothing`, `garch`, `kalman_filters`, `kronos`, `lag_llama`, `moirai`, `moment`, `timesfm`, `timer_timerxl`, `backtesting_44_metrics` | `run_fn(symbol, timeframe, bars)` |
| `std_data_root` | `arima`, `dlinear`, `itransformer`, `lpatchtst`, `lstm`, `patchtst`, `tft`, `tips_regime_aware_transformer` | `run_fn(symbol, timeframe, bars, data_root)` (trained-from-scratch angles needing `WeightsStore(data_root)`) |
| `bars_time_format` | `regime_analysis`, `trend_lifecycle`, `shock_personality` | `run_fn(symbol, bars, time_format=timeframe)` — **keyword**, not positional (see the classification-correction section below for why this matters) |
| `bars_only` | `shock_clustering` | `run_fn(symbol, bars)` |

## Classification correction — found by being asked to account for the rest

The first version of this registry had 22 angles, built from a
classification that turned out to have a real mistake. Asked directly
why only 22 (not more) of the 28 already-built angles were included,
re-checking surfaced it:

**Mistake found**: `drawdown_deep_dive` and `shock_personality` had both
been lumped into an "excluded" bucket ("no backtest.py at all" /
"needs extra data") without actually reading their real signatures.
Both were wrong:

- `drawdown_deep_dive`'s real entry point, `run_drawdown_detection(symbol,
  timeframe, bars, news=None, k=DEFAULT_K)`, fits the exact same `std`
  shape as 11 other registered angles — `news`/`k` are optional with
  real defaults. Confirmed directly with a live call before touching the
  registry: real result, no error.
- `shock_personality`'s real entry point, `run_shock_backtest(symbol,
  bars, news=None, time_format=None)`, also has `news` as a genuinely
  optional param — confirmed against this angle's own real
  `06-implementation-of-each-angles/25-shock_personality/02-real-scenario.md`,
  which already showed the `_no_news` variant carrying the full real
  sample. Not a "needs extra data" angle at all.

Both were added to the registry. `peer_relative_strength` and
`news_price_causality` were re-checked at the same time and correctly
stay excluded, but for more precise reasons than originally written:
`peer_relative_strength` runs fine without a `price_client` but only
ever returns a hollow `status: "no_peers"` row (confirmed directly, not
assumed), and `news_price_causality`'s `articles` parameter is a
required positional argument, not optional. `pnl_attribution` also got
pulled out of the "no backtest.py" bucket into its own row — it's
genuinely built and real-data-validated, just via real trade/position
data instead of `bars`, so it was never a fit for a bars-driven registry
in the first place, which is a different statement than "not built."

**A second real bug the fix itself surfaced**: adding `shock_personality`
with the same `bars_time_format` shape used for `regime_analysis`/
`trend_lifecycle` (`run_fn(symbol, bars, timeframe)`, positional) broke
immediately on real data:

```
FAIL AAPL:shock_personality: AttributeError: 'str' object has no attribute 'get'
```

Root cause: `regime_analysis`/`trend_lifecycle` both happen to have
`time_format` as their real 3rd positional parameter, but
`shock_personality`'s real 3rd parameter is `news` — `time_format` is
4th there. The positional call silently passed the timeframe string
("1D") into the `news` slot, and code deep inside the angle that expects
`news` to be a list of article dicts called `.get()` on the string,
producing an unrelated-looking `AttributeError` instead of a `TypeError`
the earlier generic parametrized test could have caught (that test only
asserts "no `TypeError`", since a `TypeError` specifically means "wrong
argument count" — a wrong *value in the right count* doesn't trip it).

**The fix**: `build_work_fn`'s `bars_time_format` shape now always calls
`time_format=timeframe` **by keyword**, not positionally — correct and
safe for all three angles regardless of where `time_format` actually
sits in each one's real signature. Verified directly with a stub
matching `shock_personality`'s exact (different) parameter order that
`news` stays `None` and `time_format` lands correctly. Re-ran real data
after the fix: `shock_personality` now returns real rows (21/16/11 for
AAPL/JNJ/TSLA) that exactly match `shock_clustering`'s own real per-symbol
counts on the same data — expected, since both detect shocks via the
same real gap/vol-spike methodology, and a real, independent
confirmation the fix is correct, not just "no longer crashes."

## Testing

`tests/test_orchestration_registry.py` — 30 tests (final):

- Registry has exactly the 24 ready angles (`plan.md`'s corrected classification).
- **Parametrized across all 24 angles**: `build_work_fn()` produces a
  real, callable `work_fn`, and calling it on deliberately-too-small junk
  data must fail (if it fails at all) inside the angle's own real
  insufficient-data logic, never with a `TypeError`.
- **New regression test** for the `shock_personality` bug: a stub
  matching its exact real parameter order (`news` 3rd, `time_format`
  4th) confirms `build_work_fn` passes `time_format` by keyword and
  `news` stays at its own default — this is the test that would have
  caught the bug before it ever reached real data, had it existed first.
- `build_batch_jobs()` produces symbols × angles, respects an
  `angle_names` filter, and each job's `work_fn` closure is independently
  bound to its own symbol/angle (not the classic Python
  closure-in-a-loop late-binding bug).
- Unknown angle name raises `KeyError`.

All 30 pass. Full `vinu-initial-analysis` suite: see `02-real-scenario.md`'s
Verification section for the final combined count.

## Real bug found and fixed: `kronos/backtest.py`'s missed threshold constant

Running the real 66-job batch (see `02-real-scenario.md`) surfaced
`chronos` and `kronos` both returning **0 rows** for all 3 real symbols,
against a 150-bar test window. Investigated both rather than assuming
they were both the same story:

- **`chronos`**: 0 rows is correct, expected behavior — `MIN_OBSERVATIONS
  = 512` (a real, already-decided pretrained-context requirement), and
  150 < 512. Not a bug.
- **`kronos`**: also correct behavior on inspection, but revealed a real
  gap in the earlier `06-implementation-of-each-angles` config-wiring
  pass. `kronos/backtest.py` has its own `WALK_FORWARD_MIN_OBSERVATIONS =
  512` — a genuinely different, deliberately-set constant from
  `compute.py`'s own `MIN_OBSERVATIONS = 30` (that one gates the
  fallback-proxy path, which trains a small MLP in-process and doesn't
  need the real pretrained model's full context; `WALK_FORWARD_MIN_OBSERVATIONS`
  gates the real walk-forward backtest, which should only ever exercise
  the genuine pretrained model, not the proxy). **This wasn't caught in
  the earlier config-wiring pass** because that pass searched for
  constants named `MIN_OBSERVATIONS`/`MIN_BARS` — `kronos/backtest.py`'s
  constant has a third, different name (`WALK_FORWARD_MIN_OBSERVATIONS`)
  that the search pattern didn't match. Confirmed via a fresh, broader
  grep across every `backtest.py` file that this was the *only* one
  missed — nothing else was silently skipped the same way.

**The fix**: wired `WALK_FORWARD_MIN_OBSERVATIONS` through
`get_angle_setting("kronos", "walk_forward_min_observations", 512)` —
its own distinct setting name (not reusing `"min_observations"`, which
would have incorrectly conflated two genuinely different real
thresholds under one env var). Verified: default value unchanged (512,
confirmed directly), override works (`VINU_KRONOS_WALK_FORWARD_MIN_OBSERVATIONS`),
`test_kronos.py`/`test_kronos_backtest.py` (11 tests) still pass
unchanged.

**What this means for the 66-job real run's own numbers**: `kronos`'s 0
rows on a 150-bar window is genuinely correct (the real pretrained model
needs 512 real bars, same as `chronos`) — not something the fix changes.
The fix's real value is closing a config-completeness gap the earlier
pass missed, confirmed by a real, unrelated real-data run surfacing it,
not by re-auditing the same angles a second time by hand.

## Related files

- `plan.md` — the pre-implementation plan and the corrected angle classification.
- `02-real-scenario.md` — the real 72-job final run, numbers, and full pass/fail breakdown.
- `../06-implementation-of-each-angles/adding-a-new-angle.md` — the config pattern the `kronos` fix follows.
- `../06-implementation-of-each-angles/25-shock_personality/02-real-scenario.md` — the earlier real-data record that confirmed `shock_personality`'s no-news path carries full real value.
- `../06-implementation-of-each-angles/known-issues.md` — cross-cutting bug tracker (not used here since every bug in this pass was found and fixed within the same session, not left open).
