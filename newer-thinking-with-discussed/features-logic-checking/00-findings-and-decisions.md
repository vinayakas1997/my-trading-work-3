# Findings and decisions (one list)

Everything this folder's checks found. `FIXED` = code changed, test added, mutation-checked. `DECISION` = needs your call, options given with a recommendation. Updated after every question answered.

## Fixed

| ID | Where found | What was wrong | Fix | Tests |
|---|---|---|---|---|
| F1 | `01` Q2 | **Strategy-decay detection was starved.** `bench_history` (the Sharpe series the decay scan reads) had one production writer, which writes one entry at approval; the scan needs at least two. Re-validation computed a fresh Sharpe and discarded it. So no real strategy could ever reach the decay logic, and "detect degradation → cut allocation" (vision A12) could not fire. | `revalidate_artifact` appends its Sharpe as a bench entry (every response mode; never fails the revalidation) | `vinu-research/tests/test_service.py::TestRevalidateFeedsDecay` (3; mutation-checked) |
| F2 | `01` Q2 | **A losing strategy could read as healthy.** The ratio `rolling Sharpe ÷ baseline Sharpe` turns positive when both are negative: approved at 1.5, then −0.5 every time → ratio 3.75 → HEALTHY. | an average re-backtest Sharpe ≤ the existing `sharpe_critical` floor (0.0) is `CRITICAL` | `vinu-research/tests/test_decay.py::TestStrategyDecayLogicByHand` |
| F3 | `01` Q3 | **A closed live-decision position recorded no outcome.** Only `closed_reason` and the bar; no exit price, no return. `trade_audit_log` is written only by the trade-plan orchestrator, so the live-decision path (the loop the vision describes) left no loss to learn from, and the consecutive-loss cooldown only ever saw plan-path losses. | closed positions record `exit_price` and `return_pct` (reference price = close of the newest processed candle; before costs; `None` rather than a guess) for both exit routes. Schema migration v6, old databases upgrade. | `vinu-live/tests/test_live_decision_position_rules.py` (13 new; mutation-checked) |

| F4 | `02` Q2 | **Live signal triggers never got an outcome.** The poller records each firing of a strategy's own must-condition with the outcome empty; no job anywhere resolved it (`get_unresolved_triggers` had no caller; the store's docstring says "not built yet"). Only the hard-coded SMA5/50 angle produced outcomes, so for any other condition the evidence "last-N → decision" had none, ever. Also: the poller did not send the timeframe, so a 1d trigger was stored as `15min`. | poller resolves open triggers once 20 closed bars have passed (same formulas and horizon as the angle), triggers carry their timeframe; new connection `research.unresolved_triggers->live.poller` with a contract; on by default, recording only, never raises | `vinu-live/tests/test_live_decision_signal_outcomes.py` (13; mutation-checked), `vinu-research/tests/test_routes_signal_evidence.py` (producer side) |

| F5 | `03` Q1 | **The regime had no effect on allocation in the Docker deployment.** The regime-alignment tilt and the sleeve split read `vinu-agent/skills/strategy-tags/tags.yaml`; `portfolio-api` neither copied nor mounted it (only `agent-api` did), so tags loaded empty, every regime multiplier was 1.0 and every sleeve `untagged`. | read-only mount of `vinu-agent/skills` into `portfolio-api` in `docker-compose.yml` | `vinu-infra/tests/test_compose_wiring.py` (2), `vinu-portfolio/tests/test_logic_allocation_by_hand.py` (2, includes the fault in miniature). Not run in Docker (Docker was not running) |

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

### D3. How should a closed live-decision trade count toward the maturity tier?

The tier (cold_start → mature) counts a "real trade" only as a calibration entry, which exists only for a position linked to a research **artifact**. The live-decision loop trades strategy YAMLs, so none of its trades counts and the tier cannot advance from it (capital multiplier stays at the cold-start 0.1 if capital gating is on).

| Option | What it does | Trade-off |
|---|---|---|
| **A (recommended)** | `assess()` also counts closed live-decision positions (read from vinu-live over a new read route), a trade "correct" when `return_pct > 0`; regime coverage unknown for them, so the tier caps at `early_live` until regimes are tagged | uses the number F3 now records; cannot reach `mature` on this path alone |
| B | register each live-decision strategy as a research artifact so the existing path counts it | one mechanism, but a larger structural change |
| C | leave it; capital scaling stays opt-in and manual for this loop | nothing to build; the loop never "earns" trust automatically |

### D4. Should the agent's evidence be filtered to the strategy's own must-condition?

`get_signal_evidence` returns every trigger for the symbol, whatever its condition, and the `outcomes_recorded` count behind the uncertainty flag `no_recorded_outcomes` is symbol-wide. A strategy with no outcomes of its own can look evidenced because the SMA angle backfilled other rows for the ticker. The angle's names (`sma5_cross_sma50`) and the live names (`live_indicators.adx_14_gt_20`) differ.

| Option | What it does | Trade-off |
|---|---|---|
| **A (recommended)** | the context tool filters to rows whose `must_condition` list matches the strategy's own condition names (exact match), and counts outcomes on that subset | small and read-only; angle-backfilled SMA rows stop counting for strategies that use other conditions |
| B | add a name mapping so angle rows count for the equivalent live condition | keeps the backfill useful, but a mapping table to maintain |
| C | leave as is | the uncertainty flag can under-report missing evidence |

### D5. Should a live-decision order need an ACTIVE research artifact for its ticker?

The order guard's `require_active_artifact` defaults to **true**: a buy for a ticker with no ACTIVE research artifact is rejected (`test_order_guard.py::test_rejects_when_no_active_artifact_for_symbol`). The live-decision loop trades strategy YAMLs, not artifacts, so with default settings its EXECUTE on AAPL is rejected unless AAPL happens to have an ACTIVE artifact from the research loop. The rejection is visible (reason text, execution ledger) but the loop cannot trade by itself out of the box.

| Option | What it does | Trade-off |
|---|---|---|
| **A (recommended for paper trading)** | set `require_active_artifact: false` in the mandate while only paper trading | one setting, no code; drops the "only promoted strategies trade" guard for every path |
| B | exempt orders that come from a live-decision position (a flag on the order) | keeps the guard for everything else; needs a new order field and a trust decision |
| C | leave it, and only trade tickers that have an ACTIVE artifact | strictest; the live-decision loop then depends on the research loop |

### D6. Should the reviewing agent be told the position's P&L?

The review prompt says the agent has no unrealized P&L and must judge only the thesis (a deliberate deferral until a bucket table exists). In a slow bleed that never reaches a configured stop, no layer except the account-level ones ever sees the loss.

| Option | What it does | Trade-off |
|---|---|---|
| **A (recommended)** | pass the real facts in `position_context` (entry price, last close, return since entry, bars held) and change prompt step 3 to "you may cite these numbers; never invent others" | uses numbers the poller already has; the agent may exit on noise, so keep "default HOLD when uncertain" |
| B | add a hard rule: exit when the return since entry falls below a limit the strategy configures | that is the existing `live_decision_stop_pct`; just needs to be set per strategy |
| C | leave as designed | the thesis-only judgement stays pure; slow losses are caught only by account-level layers |

### D7. Should the analogue output become the vision's summary?

The vision's market memory is an aggregate over many matches ("37 situations: 23 up, 14 down, average +1.3%, worst −2.8%"). The code returns the 5 nearest peaks with their individual drawdown and recovery time, no up/down count and no average return, and the live-decision context does not include them.

| Option | What it does | Trade-off |
|---|---|---|
| **A (recommended)** | add a summary over the matches (count, share that recovered within N bars, mean and median drawdown) as a new read-only field in the angle row and in the live-decision context | no change to the persisted library; honest raw counts, no invented win rate |
| B | also store the forward return after each peak and summarise that | closer to the vision; needs a new stored field and a migration decision for the library |
| C | leave as is | analogues stay visible only through stored angle rows |

### D8. Should unconfirmed moves feed the idea generator?

The system notices real moves no strategy was watching (`unconfirmed moves`) and shows them to the deciding agent, but never to the research loop, so "something moved and none of my conditions saw it" cannot become a new idea.

| Option | What it does | Trade-off |
|---|---|---|
| **A (recommended later)** | give the idea generator the last N unconfirmed moves (ticker, direction, size in ATR, regime) as read-only context | cheap; only useful once enough moves are recorded, so it waits for paper data |
| B | turn each repeated unconfirmed move pattern into a candidate must-condition automatically | the vision's full loop, but it needs a matching rule that does not exist yet |
| C | leave as is | the system finds nothing it was not told to look for |

### Flags worth switching on now (not decisions, already documented)

For paper trading with the aim of behaving like real money: `scheduler_exits_exempt_from_halts` (otherwise a halt, the spread gate or the earnings gate can stop a closing sell: see `01` Q1) and `scheduler_breaker_uses_broker_account` (otherwise the 5% daily-loss breaker does not see the scheduler's own positions). Both are listed in `../the-inconsistencies-v2/06-live-behavior-flags.md`.

All eight decisions can wait for paper data; none blocks the other work.

## Gaps noted, not changed

* The vision's data-error and model-error loss causes have no tag in `loss_classifier.py` (they land in `unclassified`).
* Stop and time-stop are off unless a strategy sets them (`live_decision_stop_pct` / `_max_hold_bars` default `0.0`). Deliberate ("no safe invented default"), but it means out of the box the only protection on a live-decision position is the agent's review every 5 bars plus the account-level layers.
