# How does the system handle a failure or a loss in a trade?

Vision: *"exit on invalidation; never let one trade hurt the portfolio; risk little when uncertain; know why we lost"* (`../vision-trding-system.md` A6, A9, A12, A15, A16). Followed here as one chain: the position goes against us, then the stop and review layers, then the account-level layers, then what is recorded, then what is learned. Running example: AAPL, long `0.05` of the book, entry `100.00`.

---

## Q1. A position starts losing. What stops it, in order?

Five independent layers. Each one can end the trade on its own; none depends on the model being right.

| # | Layer | Fires when | Verdict |
|---|---|---|---|
| 1 | **Rule stop** (`position_rules.evaluate_position_rules`) | newest close ≤ entry × (1 − stop%) (a short: ≥ entry × (1 + stop%)) | **WORKS, WITH A LIMIT:** off unless the strategy sets `live_decision_stop_pct` (default `0.0` = no stop, by design: no invented default) |
| 2 | **Time stop** (same function) | bars held ≥ `live_decision_max_hold_bars` | **WORKS, WITH A LIMIT:** also off by default |
| 3 | **Agent thesis review** (`poller._review_open_positions`) | every `review_cadence_bars` (5) the same deciding agent is asked HOLD or EXIT | mechanism **WORKS**; whether the agent judges well **waits for data** |
| 4 | **Per-symbol daily loss tiers** (`portfolio/risk_budget.py`, enforced in `order_guard._check_risk_budget`) | symbol's day P&L ≤ −1% / −2% / −3% of equity | **WORKS** |
| 5 | **Account-level breakers** (daily-loss breaker in `live/breaker/engine.py`, drawdown ladder in `portfolio/circuit_breakers.py`) | day loss > 5%, or drawdown from peak −10% / −15% / −20% | **WORKS** |

### 1. Rule stop: worked example

Entry `100.00`, `live_decision_stop_pct = 0.05` → stop level `95.00`.

| Newest close | Expected | Why |
|---|---|---|
| `95.01` | no exit | above the level |
| `95.00` | `EXIT stop_loss` | at the level counts |
| `94.00` | `EXIT stop_loss`, **exit price 94.00, return −6.0%** | 94/100 − 1 |
| short, entry `100`, close `106` | `EXIT stop_loss`, return **−6.0%** | a short stops on a rise; loses when price rises |
| short, entry `100`, close `90` (time stop) | `EXIT max_hold`, return **+10.0%** | a short gains when price falls |
| no entry price known yet | stop disabled, time stop still works, return recorded as `None` | a rule only exits when it can fully justify it |

Tests: `vinu-live/tests/test_live_decision_position_rules.py` (rule function, poller close, full cycle through the real loop; the `F3` tests at the end assert the return numbers above). Mutation-checked: removing the exit price from the poller makes 5 tests fail.

### What happens after the exit is decided (verified chain)

`close_position` marks the row `closed` → the next scheduler cycle no longer emits that position's weight → `SignalTranslator`'s existing "held but not targeted → close to 0" rule sells it (`live_decision/storage.py close_position`, `vinu-live/vinu_live/scheduler.py`). No special sell code. Exits are never blocked by halts: `reduce_only` orders bypass the halted-symbol check (`order_guard`, `test_reduce_only_bypasses_halted_symbol`; `test_scheduler_exits_exempt.py`), which is the right logic: a risk limit must never trap you in a losing position.

### 4. Per-symbol tiers: worked example (equity 100,000)

| Day P&L of the symbol | Tier | `suggested_size_multiplier` (bull) | Effect |
|---|---|---|---|
| −900 (−0.9%) | 0 | 1.0 | nothing |
| −1,000 (−1.0%) | 1 warning | 1.0 | flagged |
| −2,000 (−2.0%) | 2 reduce | 0.5 | new orders sized by half |
| −3,000 (−3.0%) | 3 **halt** | 0.0, `halted=true` | `order_guard` rejects new/increasing orders until tomorrow (`test_blocks_new_order_for_halted_symbol`) |
| bear regime, tier 1 | 1 | 0.8 | the regime tightens bands on top (`REGIME_SIZING_MULTIPLIERS`) |

Tests: `vinu-portfolio/tests/test_risk_budget.py` (tier thresholds, regime composition, a breach latches for the day even after recovery).

### 5. Drawdown ladder: worked example (peak 100,000)

| Portfolio value | Drawdown | Action | `deployable_equity` multiplier |
|---|---|---|---|
| 97,000 | −3% | ok | 1.0 |
| 89,000 | −11% | halve | 0.5 |
| 84,000 | −16% | flat | 0.0 |
| 79,000 | −21% | **halt** (real kill switch via the agent's `/broker/halt`) | 0.0 |

Tests: `vinu-portfolio/tests/test_circuit_breakers.py` lines 201-223 assert exactly these numbers. With reserve 10% and a halve, deployable equity is 100,000 × 0.9 × 0.5 = **45,000** (`service.py _drawdown_action_multiplier`).

**Waits for data:** whether −1%/−2%/−3%, −10%/−15%/−20% and the review cadence of 5 bars are the right numbers. They are guessed defaults; Phase 2 paper data is what tunes them.

---

## Q2. If a *strategy* keeps losing, who notices and what happens to it?

**Verdict: FIXED (2 defects found and corrected here), plus 1 DECISION.**

Vision A12: *"Sharpe 2.1 → 0.4 + slippage ↑ → detect degradation → cut allocation → investigate → retrain → paper → restore"*.

Intended chain: hourly `decay_scan` (`vinu-research/scheduled/executor.py:195`) reads each ACTIVE strategy's `bench_history` (a series of re-backtest Sharpe ratios) → `compute_strategy_decay_metrics` → `evaluate_strategy_health` → `transition_status` (3 consecutive bad readings) → status `MONITORING`/`DECAYED` → portfolio asks research only for `status=ACTIVE` strategies (`vinu-portfolio/service.py:182`) so the strategy drops out of the book → on `DECAYED` re-research is triggered (`cli._trigger_re_research`).

What I found when I traced it:

1. **The chain was starved (fixed).** `bench_history` had exactly one writer in production, `_create_artifact_from_run`, which writes **one** entry at approval. The scan skips any artifact with fewer than two entries (`cli.py`: `only N bench entries (need >= 2)`). Re-validation computed a fresh Sharpe (`result.metrics.sharpe_ratio`) and then threw it away. So no real strategy could ever reach the decay logic. **Fix:** every re-validation now appends its Sharpe as a bench entry (best-effort, recorded in every response mode, never fails the revalidation). `vinu-research/vinu_research/service.py revalidate_artifact`; tests `test_service.py::TestRevalidateFeedsDecay` (3, one mutation-checked: 2 fail without the fix).
2. **A losing strategy could read as healthy (fixed).** The health ratio is `rolling Sharpe ÷ baseline Sharpe`. Once the baseline average turns negative, negative ÷ negative is a large *positive* number. Hand example: approved at Sharpe 1.5, then −0.5 on every re-backtest. From the 5th entry the ratio was **3.75 → HEALTHY**. **Fix:** an average re-backtest Sharpe at or below the existing `sharpe_critical` floor (0.0) is always `CRITICAL` (`decay.py evaluate_strategy_health`). Tests `test_decay.py::TestStrategyDecayLogicByHand`.
3. **The detection is slow, by design of the metric (DECISION D1).** Baseline = the first 5 entries; rolling = the mean of **all** entries, which includes those baseline entries. So the baseline is diluted by the very decay it should detect. Hand numbers for approval Sharpe 1.5 followed by 0.0 forever: HEALTHY until 7 entries (ratio 0.71), WARNING at 8, DECAYED at 11 entries (0.45), and then 3 consecutive bad readings are needed before the status changes. A fall from 1.5 to 0.4 (−73%) never leaves HEALTHY (ratio settles near 0.76). This is pinned in `test_known_lag_a_collapse_to_zero_is_only_noticed_on_the_8th_and_11th_entry` so any change is deliberate. See `00-findings-and-decisions.md` D1 for options.

**Waits for data:** how many re-validations happen per week decides how long "11 entries" takes in calendar time.

---

## Q3. After a loss, can we answer "why did we lose?"

**Verdict: WORKS for the trade-plan path. FIXED (recording) for the live-decision path. DECISION for reading it back.**

Vision A15/A16: every trade carries its reasoning, size, exit reason and P&L so the loss can be classified.

* **Trade-plan path (the orchestrator):** `record_entry` / `record_exit` write one audit row per trade (`vinu-infra/trade_audit_log.py`, called from `trade_plan/orchestrator.py`), keyed by `trade_id`, with trade-score tier, risk band, fills, exit rule and realized P&L, and a **loss cause tag** from `trade_plan/loss_classifier.py classify_exit_cause` (`risk_error`, `regime_change_error`, `prediction_error` for a failed thesis re-check, `time_decay` for a time stop, `execution_error` added when slippage exceeded its limit, else `unclassified`; a winning trade is always `expected_outcome`). The vision's data-error and model-error causes have no tag yet (they fall into `unclassified`). `read_by_trade_id` rebuilds the whole story. Reflection's `loss_attribution` reads these rows to detect that the loss rate of a trade-score tier has drifted from its own recent history (PSI, 30-trade windows). **WORKS** (existing tests).
* **Live-decision path (the SMA-cross style loop the vision's "live decision" describes):** a closed position stored only `closed_reason` and the bar it closed on. **No exit price, no return.** `trade_audit_log` is written only by the orchestrator, so this path left no outcome at all, and the code itself admits one consequence: *"the cooldown reads the trade-plan book's closed positions, and this path does not write its own fills to that book, so on this path it reflects plan-path losses only"* (`scheduler.py _apply_entry_guards`). **Fix:** a closed live-decision position now records `exit_price` (close of the newest processed candle at the exit decision) and `return_pct` (`exit/entry − 1`, flipped for a short, before costs), for both exit routes (rule stop and agent review). Unusable prices record nothing, never a guess. `vinu-live/vinu_live/live_decision/{schema,storage,poller}.py`; 13 tests, mutation-checked. Why now: this data cannot be recovered later for the first paper trades.
* **Still not read back (DECISION D2):** nothing yet reads `return_pct` (the consecutive-loss cooldown, reflection's loss attribution, the agent's `past_live_decisions`). The number exists from now on; wiring it to a reader needs your choice (see `00`).

**Waits for data:** all of it. The recording is now in place; the *analysis* of real losses needs real losses.

---

## Q4. What does the system learn from a loss, and who uses it?

**Verdict: WORKS, WITH A LIMIT.**

| Learning signal | Source | Who reads it | Status |
|---|---|---|---|
| Signal evidence: each time the must-condition fires, the forward return at +20 bars (win/loss, positive ratio) | `signal_evidence` angle → `SignalEvidenceStore` | the deciding agent (`get_signal_evidence`, e.g. "34 triggers, 58% positive"), the sizing evidence-confidence | **WORKS.** This is the live-decision loop's real learning source, measured on the *signal*, independent of whether a trade was taken |
| Trade-score tier loss-rate drift | `trade_audit_log` rows | reflection `loss_attribution`, `threshold_calibration` | **WORKS** for trade-plan trades only |
| Rejected / failed candidates | graveyard (generation, sweep, hypothesis) | the idea generator avoids repeats | **WORKS** (read-time union) |
| Strategy decay | re-backtest Sharpe series | `decay_scan` → status → portfolio | **FIXED** in Q2, **DECISION D1** on speed |
| Live-decision trade return | `return_pct` | nobody yet | **DECISION D2** |

**Waits for data:** every learning loop needs enough rows to mean anything (the code's own floors: 30 trades for calibration, 5 samples for the evidence-confidence sizer, 70 observations for signal evidence). Until then the system behaves as the "child" the rules ask for: it believes a fact only in proportion to its evidence, and says `insufficient_evidence` or falls back to raw counts instead of a made-up score.
