---
name: orchestration-suite-test-real-scenario
status: phase-1-done
purpose: the real 72-job run — 3 real symbols x 24 real angles through the actual orchestrator, real numbers, real pass/fail breakdown, not a synthetic demo. Includes the corrected registry after a classification mistake was found and fixed.
---

# 07 — Orchestration Suite Test — Real Scenario

Real AAPL/JNJ/TSLA daily bars (the same 3 real cached symbols used
throughout `06-implementation-of-each-angles`), 150-bar tail window per
symbol (a deliberately bounded real slice, not the full ~1025-bar
history, to keep the full batch's total wall-clock reasonable — several
of the 24 angles train a model per step).

This scenario was run **three times** as the registry was corrected —
the numbers below are the final, 24-angle version; see
`01-implementation.md` for the classification correction and the two
real bugs (`kronos`, `shock_personality`) found across the earlier runs.

## The call

```python
from vinu_initial_analysis.storage.orchestration import AngleRunStatus, run_batch
from vinu_initial_analysis.storage.orchestration_registry import build_batch_jobs

jobs = build_batch_jobs(["AAPL", "JNJ", "TSLA"], bars_by_symbol, data_root)
# 72 real jobs (3 symbols x 24 registered angles)

tracker = AngleRunStatus(tracker_db_path)
summary = run_batch(tracker, "full-suite-<ts>", jobs, max_attempts=2)
```

## Real result (final, 24-angle registry)

```
=== DONE in 398.8s ===
ok: True
succeeded: 72/72
failed:    0/72
remaining tracked rows: 0
```

All 72 real jobs succeeded — after fixing both real bugs found along the
way (`kronos`'s config-completeness gap, `shock_personality`'s call-shape
bug — see `01-implementation.md`). The tracking table cleaned itself up
automatically: 0 rows remaining, exactly the "delete the rows, don't
keep them" behavior asked for when this feature was designed.

## Per-angle real row counts (AAPL; JNJ/TSLA the same shape unless noted)

| Angle | Rows | Note |
|---|---|---|
| `arima` | 50 | |
| `backtesting_44_metrics` | 50 | |
| `chronos` | 0 | Correct: `MIN_OBSERVATIONS=512`, this test's 150 bars < 512 — the real pretrained model's own context requirement, not a bug. |
| `dlinear` | 50 | |
| `drawdown_deep_dive` | 5 | **Newly added** (was wrongly excluded originally) — 5 real detected drawdown episodes per symbol. |
| `exponential_smoothing` | 50 | |
| `garch` | 50 | |
| `itransformer` | 50 | |
| `kalman_filters` | 50 | |
| `kronos` | 0 | Same real reason as `chronos` — `WALK_FORWARD_MIN_OBSERVATIONS=512`. The config-wiring gap found here (see `01-implementation.md`) was about the constant not being configurable, not about this 0 being wrong — 0 rows is the correct answer for a 150-bar window either way. |
| `lag_llama` | 46 | |
| `lpatchtst` | 50 | |
| `lstm` | 50 | |
| `moirai` | 46 | |
| `moment` | 46 | |
| `patchtst` | 50 | |
| `regime_analysis` | 10 | Its own real, derived 141-observation floor (`VOL_BASELINE_WINDOW + VOL_WINDOW`) leaves few usable steps in a 150-bar window — expected, not a bug. |
| `shock_clustering` | 21 (AAPL) / 16 (JNJ) / 11 (TSLA) | Real per-symbol shock counts — genuinely different across real tickers, as expected. |
| `shock_personality` | 21 (AAPL) / 16 (JNJ) / 11 (TSLA) | **Newly added** (was wrongly excluded, then had a real call-shape bug — see `01-implementation.md`). Matches `shock_clustering` exactly on every symbol — both detect shocks via the same real gap/vol-spike methodology on the same bars, a real cross-validation the fix is correct. |
| `tft` | 50 | |
| `timer_timerxl` | 46 | |
| `timesfm` | 46 | |
| `tips_regime_aware_transformer` | 30 | |
| `trend_lifecycle` | 1 | Real peak-detection signal count on a short 150-bar window — few real peaks/troughs form that quickly, expected. |

Every one of these is a **real** number from a **real** call — no
fabricated or placeholder rows.

## What this proves, and what it doesn't

**Proven**: the full orchestrator (registry + tracker + retry +
cleanup-on-success) works end to end, for real, across a real
multi-symbol, multi-angle batch — 72 real jobs, not the earlier 5-job
demo. Every angle's own real threshold/insufficient-data logic ran
correctly (0 rows for `chronos`/`kronos` is the *angles'* own honest
answer for this window size, not an orchestrator bug). Two real bugs
(one config-completeness gap in `kronos`, one call-shape bug in
`shock_personality`) were found because real runs surfaced them, and
both are now covered by regression tests, not just fixed once.

**Not proven here**: the 2 extra-data angles (`news_price_causality`,
`peer_relative_strength`), the 1 dependent angle
(`trend_session_structure`), and the 4 non-bars-driven angles
(`ml_model_pipeline`, `news_first_analysis`,
`cross_attention_gcn_news_price_fusion`, `pnl_attribution`) — all
explicitly out of scope for this pass (see `plan.md` for the precise,
corrected reason each one stays excluded). Nor does this pass wire the
parallel-batch harness into `run_batch` — still a separate, undecided
integration question.

## Verification

`tests/test_orchestration_registry.py`: 30 tests, all pass — registry
shape correctness for every one of the 24 angles (checked before any
real compute was spent), plus a regression test for the
`shock_personality` keyword-vs-positional bug.

`tests/test_kronos.py`/`test_kronos_backtest.py`: 11 tests, all pass
after the `WALK_FORWARD_MIN_OBSERVATIONS` config fix.

`tests/test_drawdown_deep_dive*.py` (15 tests), `tests/test_shock_personality.py`:
all pass unchanged — neither angle's own code was modified, only how the
registry calls them.

Full `vinu-initial-analysis` suite: **427 passed, 2 skipped, 0 failed**
(up from 386 before this whole pass — the +41 is `test_orchestration.py`'s
11 tests plus `test_orchestration_registry.py`'s final 30 tests; zero
regressions anywhere else across three full-suite runs as the registry
was corrected).

## Related files

- `01-implementation.md` — the build record, the classification correction, and both real bugs found and fixed.
- `plan.md` — the pre-implementation plan and the corrected angle classification.
- `../06-implementation-of-each-angles/parallel-backtest-infra.md` — the group-split table this scope was checked against.
