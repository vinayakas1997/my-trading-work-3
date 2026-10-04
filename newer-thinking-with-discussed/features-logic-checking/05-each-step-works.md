# Does each step do its role?

One entry per step on the money path, in the order the data flows (`../how-system-implemented.md`). Each has small hand-made numbers, the answer worked out by hand, and the test that asserts it. **Evidence** says whether I wrote and ran the test here (`new`), or relied on an existing test whose exact numbers I read (`existing`), or only read the code (`read`). Anything marked `read` is not proven.

## The chain with one set of numbers

Account equity 100,000; reserve 10%; drawdown status `ok`; regime bull; AAPL 200, MSFT 400.

```
base weights (two strategies, calm has half the volatility)   HRP default: 0.8 / 0.2   (inverse-vol mode: 0.6667 / 0.3333)
 tilts (A trending + bull + accuracy 0.8; B ranging)          A 0.6867   B 0.3133
 deployable = 100,000 x 0.9 x drawdown 1.0 x maturity 1.0     90,000     (halve: 45,000   flat: 0)
 scheduler scales each weight by 90,000 / 100,000 = 0.9       A 0.61803  B 0.28197
 translator: weight x 100,000 / price, whole shares (buys round down, sells nearest)    AAPL 309 shares   MSFT 70 shares
 TWAP, 6 slices                                               AAPL 51, 51, 51, 51, 51, 54
 halve: fraction 0.45                                         AAPL 154, MSFT 35         flat: no buys, held positions sold
```

Every arrow is asserted: `vinu-portfolio/tests/test_logic_allocation_by_hand.py` and `vinu-live/tests/test_logic_money_chain_by_hand.py`.

---

| # | Step | Role | Worked example | Evidence | Verdict |
|---|---|---|---|---|---|
| 1 | **Screener** history gate | a thin or recent listing never reaches research | a ticker with fewer than `min_history_bars` is rejected with a category and shown in the rejected samples | read; `test_dry_run.py`, `test_evaluator.py` (insufficient history fails closed) | WORKS (not re-proven here) |
| 2 | **Point-in-time data** (`clamp_to_as_of`) | a replay never sees data after its boundary | value beyond `as_of` is clamped and reported clamped; exactly at `as_of` is not clamped | existing: `vinu-infra/tests/test_point_in_time.py` | WORKS |
| 3 | **Signal evidence outcome** | what happened after a trigger | trigger bar closes 100; next 20 closes peak 108, trough 97, last 103 → best +0.08, worst −0.03, return +0.03 | new, mutation-checked (`test_live_decision_signal_outcomes.py`) | WORKS (after F4) |
| 4 | **Market-memory analogues** | find earlier peaks like today's | hot peak matches the three hot peaks, never a future one | new, mutation-checked (`test_logic_analogues_by_hand.py`) | WORKS, WITH A LIMIT (D7) |
| 5 | **Move detection** (Track 2) | notice a real move nobody watched | ATR 2.0 → threshold 4.0; +5 is a move, +3 and exactly +4 are not; one bar or no ATR → `None` | new (`test_logic_detect_move_by_hand.py`) | WORKS |
| 6 | **TradeScore** tiers and the reward:risk veto | decide how big, or whether, to trade a plan | total > 110 strong, 90-110 moderate, 70-90 watch, below 70 no trade; reward:risk 1.0 on a 126/135 plan forces `no_trade` | existing: `test_trade_score_gate.py` (`test_tier_boundaries`, `test_forces_no_trade_even_when_composite_would_be_strong`) | WORKS |
| 7 | **Score-weight calibration** | move weights toward what wins | correlations 0.6 / 0.3 / −0.2 / 0.0 → maxes 48 / 42 / 24 / 24, cutoffs untouched | new (`test_trade_score_calibration.py`) | WORKS |
| 8 | **Risk-parity base weights** | calmer strategy gets more | σ ratio 1:2 → inverse-vol 2/3 : 1/3; default HRP 0.8 : 0.2 | new, `test_logic_allocation_by_hand.py` | WORKS (the default is HRP; old docs said inverse-vol) |
| 9 | **Concentration cap** | no sleeve above the cap | 0.6 / 0.3 / 0.1 with cap 0.4 → 0.4 / 0.4 / 0.2 | new | WORKS |
| 10 | **Regime and outcome tilts** | favour what fits the market and what has worked | 0.5 × 1.3 × 1.18 = 0.767 vs 0.5 × 0.7 = 0.35 → 0.6867 / 0.3133 | new | WORKS (needs the tags file: F5) |
| 11 | **Drawdown ladder** | de-risk as the account falls | peak 100,000: 97,000 ok, 89,000 halve, 84,000 flat, 79,000 halt | existing: `test_circuit_breakers.py:201-223` | WORKS |
| 12 | **Deployable capital** | one number for how much may be used | 100,000 × 0.9 × 0.5 = 45,000 on a halve | new + read | WORKS |
| 13 | **Per-symbol risk tiers** | cut or stop a symbol that is losing today | equity 100,000: −900 tier 0; −1,000 tier 1; −2,000 tier 2 × 0.5; −3,000 halt × 0.0; bear regime × 0.8 | run here (numbers printed), existing `test_risk_budget.py` | WORKS |
| 14 | **Scheduler scaling + translator + netting** | weight → shares | see the chain; +2% and −1% on one symbol → one buy of 5 | new | WORKS (buys round down, F7) |
| 15 | **TWAP slicing** | spread an order | 309 over 6 → 51 × 5, then 54; slices always add up | new | WORKS |
| 16 | **Breaker** | stop trading after too large a loss | daily loss −5,000 on 100,000 against a 1% limit → HALT | existing: `test_breaker.py::test_halt_on_daily_loss` | WORKS (blind to scheduler positions unless a flag is on; see `01`) |
| 17 | **Candle-close state machine** | turn "condition fired" into "ready to decide" | grace 3 bars × 900 s: fired at 1000 → expires at 3700; confirmed at 1900 → ready; 3800 with no confirmation → expired | existing: `test_live_decision_state_tracker.py` | WORKS |
| 18 | **Rule stop / time stop** | exit a losing or stale position | entry 100, stop 5%: 95.00 exits, 95.01 does not; short mirrored; return −6% at 94 | existing + new (`test_live_decision_position_rules.py`) | WORKS |
| 19 | **Decay** | notice a strategy that stopped working | approved 1.5, then 0.0: HEALTHY to entry 7, WARNING 8, DECAYED 11; a negative average is CRITICAL | new (`test_decay.py`) | FIXED (F1, F2), speed D1 |
| 20 | **Uncertainty** | say how much is unknown | novelty high + no outcomes = 4 → high; snapshot and config missing = 3 → medium | run here; existing tests | WORKS |
| 21 | **Order guard** | last line before the broker | no ACTIVE artifact → reject (default); halted symbol → reject new orders; reduce-only passes a halt | existing: `test_order_guard.py` | WORKS (D5 on the artifact rule) |

## What was not proven here

* Steps 1, 2 and the indicator single-implementation claim were read, and existing tests cover them; I did not re-derive their numbers.
* The strategy `WeightPipeline`, the options and fundamentals tools, and the reflection analysts were not hand-checked in this pass. They are listed so nobody reads this table as complete coverage.
* Everything that needs real trades: whether any threshold above is a good one, whether the agent judges well, whether the system actually improves.

## Limits found while working these examples

* **D9 (rounding), fixed (F7).** A buy that grows a long position now rounds **down**, so it never exceeds the deployable money (7,000 a share with a 90,000 allowance: 12 shares = 84,000, was 13 = 91,000). Sells, closes and covers still use the nearest whole share so they match what is held.
* **Doc drift.** The default allocator is `hrp`, not inverse-volatility as several docs and the method's docstring said. Docstring corrected.
