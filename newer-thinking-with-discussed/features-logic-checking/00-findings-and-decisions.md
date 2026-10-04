# Findings and decisions (one list)

Everything this folder's checks found. `FIXED` = code changed, test added, mutation-checked. `DECISION` = needs your call, options given with a recommendation. Updated after every question answered.

## Fixed

| ID | Where found | What was wrong | Fix | Tests |
|---|---|---|---|---|
| F1 | `01` Q2 | **Strategy-decay detection was starved.** `bench_history` (the Sharpe series the decay scan reads) had one production writer, which writes one entry at approval; the scan needs at least two. Re-validation computed a fresh Sharpe and discarded it. So no real strategy could ever reach the decay logic, and "detect degradation → cut allocation" (vision A12) could not fire. | `revalidate_artifact` appends its Sharpe as a bench entry (every response mode; never fails the revalidation) | `vinu-research/tests/test_service.py::TestRevalidateFeedsDecay` (3; mutation-checked) |
| F2 | `01` Q2 | **A losing strategy could read as healthy.** The ratio `rolling Sharpe ÷ baseline Sharpe` turns positive when both are negative: approved at 1.5, then −0.5 every time → ratio 3.75 → HEALTHY. | an average re-backtest Sharpe ≤ the existing `sharpe_critical` floor (0.0) is `CRITICAL` | `vinu-research/tests/test_decay.py::TestStrategyDecayLogicByHand` |
| F3 | `01` Q3 | **A closed live-decision position recorded no outcome.** Only `closed_reason` and the bar; no exit price, no return. `trade_audit_log` is written only by the trade-plan orchestrator, so the live-decision path (the loop the vision describes) left no loss to learn from, and the consecutive-loss cooldown only ever saw plan-path losses. | closed positions record `exit_price` and `return_pct` (reference price = close of the newest processed candle; before costs; `None` rather than a guess) for both exit routes. Schema migration v6, old databases upgrade. | `vinu-live/tests/test_live_decision_position_rules.py` (13 new; mutation-checked) |

## Decisions for you

### D1. How fast should strategy decay be noticed?

Today (pinned by a test): baseline = first 5 re-backtest Sharpes, rolling = mean of **all** of them, so the baseline is diluted by the decay it should catch. Approved at 1.5, then 0.0 forever: HEALTHY until 7 entries, WARNING at 8, DECAYED at 11, and then 3 consecutive bad readings before the status changes. A drop from 1.5 to 0.4 is never flagged.

| Option | What changes | Trade-off |
|---|---|---|
| **A (recommended)** | compare the **latest** re-backtest Sharpe with the **approval** Sharpe (the first bench entry); the existing 3-consecutive-readings rule already smooths noise | no new constants; reacts after 3 re-validations; one noisy backtest cannot demote on its own |
| B | baseline = approval Sharpe, rolling = mean of the last K re-backtests | smoother than A, but K is a new number to guess |
| C | leave as is (plus the F2 floor) | slow and blind to partial decay |

### D2. Who should read a live-decision trade's return?

`return_pct` now exists (F3) but nothing reads it.

| Option | What it does | Trade-off |
|---|---|---|
| **A (recommended first)** | show each past decision's outcome in `past_live_decisions` so the deciding agent sees "last EXECUTE lost 6%" | read-only context, smallest change; the agent may over-weight a single outcome |
| B | feed live-decision losses to the consecutive-loss cooldown (`scheduler._apply_entry_guards`) | closes the gap the code itself names; changes entry behaviour (when the guard flag is on) |
| C | let reflection's `loss_attribution` read the live-decision database too | one learning loop for both paths; a bigger change |

Both decisions can wait for paper data; neither blocks the other work.

## Gaps noted, not changed

* The vision's data-error and model-error loss causes have no tag in `loss_classifier.py` (they land in `unclassified`).
* Stop and time-stop are off unless a strategy sets them (`live_decision_stop_pct` / `_max_hold_bars` default `0.0`). Deliberate ("no safe invented default"), but it means out of the box the only protection on a live-decision position is the agent's review every 5 bars plus the account-level layers.
