# A live-decision strategy must pass research and simulation before it can trade

Written for: whoever owns the paper/real trading decision. This records a mistake and the fix.

## The mistake

The system already had the right idea: a strategy trades only after research and simulation validated it (`require_active_artifact`). Two things bypassed it on 2026-10-04:

1. The seeded paper mandate set `require_active_artifact: false` so live-decision orders could go through.
2. Live-decision strategies are YAML trigger rules, and nothing sent them through research at all. 15-minute and 1-hour versions went live next to the daily one although the simulator shows they have no edge (see `07`).

## The fix

| Layer | What it does |
|---|---|
| Mandate | `require_active_artifact: true` again, with a guard test (`test_stack_guards.py`). |
| Bridge (`vinu_research/strategy_validation.py`) | Turns a strategy's `must_conditions` into a research candidate (`UserStrategy`: long, held N bars after each setup), runs the research loop on the strategy's **own bar size** for **each ticker** in its universe, **one iteration** (tested exactly as written, never "improved"), and judges each result with the system's own promotion bar (`promotion.meets_promotion_bar`: deflated Sharpe, out-of-sample holdout, stress windows, PBO). |
| Verdict | `validated` when at least 60% of the universe passes; `rejected` otherwise; `unvalidatable` when it cannot be tested (a condition with no backtest equivalent, no conditions, an unknown bar size). Stored in `strategy_validations.db` and served at `GET /research/strategy-validations`. |
| Fingerprint (`vinu_infra/strategy_fingerprint.py`) | The verdict covers the exact conditions, bar size and hold length. Edit any of them and the old approval no longer matches. |
| Live gate (`poller._validated_tickers`) | New entries are evaluated only for strategies validated for their current rules, and only on the tickers that passed. Never validated, rules changed, rejected, unvalidatable, still running: all blocked, each logged with its reason. If the verdicts cannot be read, nothing new enters (fail closed). Reviews and exits of open positions never depend on it. |
| Connection panel | `research.strategy_validations->live.poller`, with a contract, shows whether the gate is being read. |
| Guards | the gate defaults on; compose and env files may not switch it off (`test_stack_guards.py`). |

Run it: `VINU_API_KEY=... python scripts/validate_strategies.py` (after adding or editing a strategy). `--status` prints the verdicts.

## What it does not do

* It tests the **setup**, not the stop or the RSI-style confirmation conditions.
* Only conditions the backtester can compute are testable (`sma_N`, `ema_N`, `rsi_N`, `adx_N` and `dist_from_sma_N` / `dist_from_ema_N`). Anything else is `unvalidatable`, which is blocked, not waved through.
* A validated strategy is not a profitable one. The promotion bar is the system's existing one; passing it is the minimum to be allowed to trade paper money, not evidence of an edge.
* The order guard's `require_active_artifact` is ticker-level (an ACTIVE artifact for the ticker). The new gate is strategy-level, in the live loop. Both are on; neither replaces the other.
