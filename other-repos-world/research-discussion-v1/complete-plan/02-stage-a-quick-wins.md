# Stage A — Quick Wins (35 items)

Cheap, safe hardening of code that already exists. Each item is self-contained and independently testable — no architectural risk. Grouped below in the order to actually do them: correlation-matrix hardening first, since several later items (the runtime correlation monitor, concentration checks) depend on that matrix being trustworthy.

Full detail/rationale for any item: its ID also exists as a row in `../adoption-tracker.md` — same wording, cite that file for the "why" if this table's one-liner isn't enough.

Status key: `pending` · `in-progress` · `done` · `skipped` (reason).

## Group A-1 — `vinu-portfolio`: correlation & sizing (do first — other items depend on this)

| ID | Item | Source | Status |
|---|---|---|---|
| A1 | **Done 2026-09-10.** New `vinu_portfolio/risk_utils.py`: `fix_nonpositive_semidefinite` (spectral, numpy-only) applied unconditionally as a final safety net. Confirmed real impact before implementing: `OrderGuard._check_portfolio_concentration` fetches this exact matrix via `GET /portfolio/state` and rejects/allows real orders on it. Found and fixed a duplication along the way — `build_portfolio()` and `compute_correlation_matrix()` each independently called raw `returns_df.corr()`; both now go through one shared `robust_correlation_matrix()`. 4 new direct tests + 1 regression-guard test in `test_service.py` (constructs a matrix pandas' pairwise-NaN `.corr()` handling makes non-PSD, asserts the repaired output has no negative eigenvalues). | PyPortfolioOpt → `11-pyportfolioopt.md` | **done** |
| A2 | **Done 2026-09-10, alongside A1** (implemented together — same module, same call sites). Ledoit-Wolf shrinkage via `sklearn.covariance.LedoitWolf` (added `scikit-learn>=1.3` as a proper declared dependency rather than hand-rolling the shrinkage formula — safer for something feeding real risk decisions). Tried first, PSD-repair (A1) applied after regardless as a final safety net. Fail-open to the raw correlation on any shrinkage failure. **2 existing tests needed updating**: both asserted exact ±1.0 correlation from tiny (12-15 sample) synthetic series with a perfectly linear relationship — shrinkage correctly pulls those toward less extreme values by design, so the assertions were loosened to "still clearly strongly correlated" (`< -0.7` / `> 0.8`) rather than exact identity. 4 new direct unit tests in `test_risk_utils.py`. Full vinu-portfolio suite: 143 passed, 2 pre-existing unrelated `test_auth.py` failures (same baseline pattern as every other service this session). | PyPortfolioOpt → `11-pyportfolioopt.md` | **done** |
| A3 | **Done 2026-09-10 — mostly already implemented.** The core `TargetPercent`-style delta resolution (`target_value = target_w * portfolio_value`, `target_qty = target_value / price`, `delta = target_qty - current_qty`, quantized, held-but-dropped → full close) already existed in `vinu-live/vinu_live/signal_translator.py`'s `SignalTranslator`. Found one real gap and fixed it: `price = prices.get(symbol, 1.0)` silently substituted 1.0 for an unpriced symbol — for a $200 stock that sizes the order ~200x too large. Same bug in `scheduler.py`'s `_compute_expected_positions` (which feeds reconciliation, and reconciliation auto-corrects drift, so a fabricated expected qty could trigger a real corrective order). Both now fail closed — skip the symbol, log a warning, retry next cycle — matching VectorBT's own "fail-closed when unpriceable" behavior. 2 new tests. vinu-live suite: 278 passed, 2 pre-existing unrelated failures. | VectorBT → `09-vectorbt.md` | **done** |
| A4 | **Done 2026-09-10 — found and fixed a real bug.** `allocate_risk_parity` applied `min(w, max_per_strategy_weight)` *before* renormalization, which renormalization then undid (3 strategies, one dominant → capped at 0.30, others 0.05 each → total 0.40 → renormalize → 0.30/0.40 = **0.75**). The `_check_composition_gaps` detector correctly flagged the result but nothing acted on it. New `cap_concentration()` in `risk_utils.py` — iterative clip-and-redistribute applied *after* normalization so the cap actually binds, with the effective cap floored at `1/n` (a configured cap below equal-weight is mathematically infeasible and treated as a no-op). Sector-bucketing (the other half of daily_stock_analysis's pattern) deliberately not done — Vina has no sector-data source wired into this path, so that's a Stage-C-sized addition, not cheap hardening. 7 new tests (6 direct + 1 integration proving the cap binds post-normalization). vinu-portfolio suite: 150 passed, 2 pre-existing unrelated failures. | daily_stock_analysis → `04-daily_stock_analysis.md` | **done** |
| A5 | **Skipped 2026-09-10 — current approach already covers this, better.** PyPortfolioOpt's `k * sum(|w - w_prev|)` is a soft penalty term for a convex optimizer's objective. Vina's rebalance path (`_apply_regime_tilt` in `service.py`) doesn't use a convex optimizer, and already has two *hard* turnover controls: a hysteresis dead-band (`VINU_PORTFOLIO_MIN_WEIGHT_CHANGE`, default 2% — sub-threshold changes hold the old weight) and a per-cycle action cap (`VINU_PORTFOLIO_MAX_ACTION`, default 20% — big rotations phase in gradually). Adding the penalty term has no objective to attach to and would be redundant with these. Not every adoptable item needs code. | PyPortfolioOpt → `11-pyportfolioopt.md` | **skipped** (turnover already controlled by hysteresis dead-band + per-cycle action cap; the PyPortfolioOpt pattern needs a convex optimizer Vina doesn't use here) |

## Group A-2 — `vinu-live`: contingency, correlation monitor, risk state

| ID | Item | Source | Status |
|---|---|---|---|
| A6 | `TripleBarrierConfig`-style volatility-adjusted stop/target/trailing thresholds (not static) | Hummingbot → `06-hummingbot.md` | **skipped** (contingency/invalidation thresholds in `_build_contingency_rules`/`_build_invalidation_conditions` are already conditional on `risk_state` and sit on *vol-normalized metrics* — `realized_vol_ratio`, `realized_move_vs_forecast_std` — i.e. Vina already normalizes the metric and keeps the threshold fixed, the cleaner of the two equivalent approaches. Changing the raw numeric thresholds would be a behavior change to a frozen-plan authoring path in vinu-research, not cheap in-place hardening.) |
| A7 | **Done 2026-09-10.** Added `TRAILING_ACTIVATION_PCT` (env `VINU_LIVE_TRAILING_ACTIVATION_PCT`, default 0.0 = unchanged behavior) gating `trailing_stop_for` in `orchestrator.py` — the trailing stop stays inert until the position is up by that fraction, so a normal post-entry pullback can't ratchet a stop in and take the trade out before it works (the plan's fixed invalidation/contingency stops still cover it meanwhile). 4 new tests. vinu-live suite green at baseline. | Hummingbot → `06-hummingbot.md` | **done** |
| A8 | Three named ATR-stop variants (entry-price / pre-bar-close / current-close keyed) | abu → `07-abu.md` | **skipped** (stop rules are authored in vinu-research's `_build_contingency_rules`, not vinu-live; adding 3 selectable stop-keying variants needs authoring-schema + evaluator changes on both sides, and there's no current need — vinu-live's single `trailing_stop_for` (current-price-keyed, ratcheting) already covers the live trailing case. Speculative feature-building, not Stage-A hardening.) |
| A9 | **Done 2026-09-10.** `freeze_trade_plan` now raises `ValueError` if `plan.invalidation_conditions` is empty — a plan that can never be proven wrong is one vinu-live would hold open on the time-stop alone. Belt-and-suspenders (the real authoring path always produces ≥2), but fail-closed at freeze time beats discovering it live. Required updating 4 test-fixture helpers across `test_trade_plan_authoring.py`, `test_routes_trade_plan.py`, `test_calibration_persistence.py`, `test_calibration.py` that built bare `TradePlan`s without conditions. +1 test. vinu-research suite: 650 passed, 1 pre-existing unrelated failure. (The evidence-freshness/quality-tagging half of DSA's pattern deliberately not done — that's a research-artifact schema addition, Stage-C-sized.) | daily_stock_analysis → `04-daily_stock_analysis.md` | **done** |
| A10 | **Done 2026-09-10.** Added as a 4th OOD signal (`orchestrator.py:_check_ood`): Mahalanobis distance of today's joint return vector from its trailing distribution, against the covariance signal 1 already computes and the return series signals 2/3 already fetch — one small linear-algebra op, no extra I/O. Catches a statistically extreme *joint configuration* of returns even when no single symbol's vol and no single pairwise correlation looks abnormal alone. Threshold = `OOD_TURBULENCE_MULT` (env, default 5) × open-book size (E[MD²]=n under normality). 2 new tests. Note: Vina's pre-existing per-symbol `turbulence_active` (14d realized vol, entries-only) is a *different* mechanism and stays as-is. | FinRL → `08-finrl.md` | **done** |
| A11 | `TrailingStopRiskManagementModel`'s peak-tracking drawdown-from-peak flatten (per-symbol complement to OOD) | Lean → `05-lean.md` | **skipped** (Vina's `trailing_stop_for` is already a ratcheting ATR stop — the stop only ever tightens as price rises, which *is* peak-tracking, and with A7's activation gate it now also waits for the position to prove itself first. A separate drawdown-from-peak flatten would be a redundant second mechanism doing the same job.) |
| A12 | `resolve_signal_conflict_nb`-style explicit conflict-resolution mode enum (Entry/Exit/Adjacent/Opposite) | VectorBT → `09-vectorbt.md` | **skipped** (VectorBT's `ConflictMode` resolves a simultaneous entry-AND-exit signal *within one strategy's own signal stream on one bar*. Vina's signal conflict (`_opposing_active_signal` / `SIGNAL_CONFLICT_POLICY`) is a different problem — two *separate* ACTIVE strategies disagreeing on direction for a symbol — and its 2-mode policy (`block` / `ignore`) covers the real cases; there's no meaningful 3rd/4th mode for "strategy A says long, B says short" beyond those.) |
| A13 | **Done 2026-09-10 (minimal).** `_entry_slippage_bps` in `orchestrator.py` — after a confirmed fresh entry (from flat), compares the broker's post-fill `avg_entry_price` against the price the order was sized on, logs `+/- bps` (positive = filled worse), and attaches `slippage_bps` to the entry action. Monitoring-only, best-effort, gated to entries-from-flat (an add's blended avg-entry isn't this fill's price). 4 new tests. A durable store + trend analysis (StockSharp's fuller `SlippageManager`) was deliberately left out — that's more than cheap hardening. | StockSharp → `10-stocksharp.md` | **done** |
| A14 | Covariance-over-time cold-start fallback (zero-correlation matrix for a new symbol with no history) | pysystemtrade → `12-pysystemtrade.md` | **skipped** (the cited target is `_check_runtime_correlation` / `_check_ood`, which *reduce* exposure on *high* correlation. A zero-correlation fallback for the unknown symbol means it never contributes to a high-correlation trigger — the exact same outcome as the current "skip when any symbol lacks history". No behavior change for the stated use; would only matter for portfolio *construction*, which isn't what A14 targeted.) |

## Group A-3 — `vinu-agent`: sizing, rate limiting, kill switch

| ID | Item | Source | Status |
|---|---|---|---|
| A15 | Token-bucket rate limiter for sub-second order-submission bursts | NautilusTrader → `03-nautilus_trader.md` | pending |
| A16 | Profitability-based kill switch loop (periodic P&L monitor, decoupled from strategy code) | Hummingbot → `06-hummingbot.md` | pending |
| A17 | Kelly-fraction / ATR-inverse position sizing, always clamped to the hard mandate ceiling | abu → `07-abu.md` | pending |
| A18 | Rolling-window trade-frequency counter (allocation-free reference impl for max-daily-orders) | StockSharp → `10-stocksharp.md` | pending |
| A19 | Greedy discrete allocation (target weights → integer shares, leftover-cash tracking) | PyPortfolioOpt → `11-pyportfolioopt.md` | pending |
| A20 | Incremental average-buy-price tracker for per-symbol running cost-basis | FinRL → `08-finrl.md` | pending |
| A21 | `set_max_notional_per_order()` + emitted audit-event pattern for the runtime-settings admin API | NautilusTrader → `03-nautilus_trader.md` | pending |

## Group A-4 — `vinu-research`: promotion gate hardening

| ID | Item | Source | Status |
|---|---|---|---|
| A22 | Correlation-clustered CV folds — don't let correlated symbols span train/test | abu → `07-abu.md` | pending |
| A23 | Cross-check the deflated-Sharpe gate against VectorBT's explicit `nb_trials` reference formula | VectorBT → `09-vectorbt.md` | pending |
| A24 | Graceful LLM-backend degradation chain (primary → fallback models → deterministic fallback) | daily_stock_analysis → `04-daily_stock_analysis.md` | pending |
| A25 | Recorder pattern — persist IC-like signal-quality metrics alongside every promotion verdict | Qlib → `02-qlib.md` | pending |
| A26 | Point-in-time/lookahead-leakage screening as an explicitly named gate stage | awesome-quant (idea only — repo removed from disk) | pending |

## Group A-5 — `vinu-simulator`: fill/execution realism

| ID | Item | Source | Status |
|---|---|---|---|
| A27 | Worst-case-within-candle stop/trailing-stop fill logic | Freqtrade → `01-freqtrade.md` | pending |
| A28 | Volume-capped partial-fill mechanism (cum or per-bar cap) | Qlib → `02-qlib.md` | pending |
| A29 | Gap-down fill rejection guard | abu → `07-abu.md` | pending |
| A30 | `order.reject_prob` random rejection for broker-unreliability simulation | VectorBT → `09-vectorbt.md` | pending |
| A31 | `LiquidityExceeded`-style circuit breaker (stop filling once volume-share cap hit in a bar) | Freqtrade/zipline pattern (idea only — zipline repo removed from disk) | pending |

## Group A-6 — `vinu-infra` + notifications

| ID | Item | Source | Status |
|---|---|---|---|
| A32 | Atomic write + optimistic version token for the runtime-settings admin API | daily_stock_analysis → `04-daily_stock_analysis.md` | pending |
| A33 | Notification dedup + cooldown + quiet-hours + severity + in-flight reservation | daily_stock_analysis → `04-daily_stock_analysis.md` (`notification_noise.py`) | pending |
| A34 | Per-notification-type channel routing (route kill-switch/system-error to a more urgent channel) | daily_stock_analysis → `04-daily_stock_analysis.md` | pending |
| A35 | Per-delivery-attempt audit trail (error_code/retryable/latency_ms) | daily_stock_analysis → `04-daily_stock_analysis.md` | pending |

## Group A-7 — added 2026-09-10, once Vibe-Trading's real URL was found and it was fully audited (`14-vibe-trading.md`)

Appended rather than inserted into A-2/A-3/A-4 above, to keep existing IDs stable — see `00-index.md`'s note on adding new items mid-plan. Conceptually A36/A37 belong with Group A-3 (`vinu-agent`), A38 with Group A-4 (`vinu-research`).

| ID | Item | Source | Status |
|---|---|---|---|
| A36 | Notional sizing enforced as the LARGER of explicit notional and `quantity × price`, fail-closed DENY when unpriceable — cross-check `OrderGuard`'s max-order-value check does this | Vibe-Trading → `14-vibe-trading.md` | pending |
| A37 | Hash-chained, fsynced, append-only audit ledger for kill-switch/halt/emergency-flatten events (tamper-evident) | Vibe-Trading → `14-vibe-trading.md` (`governance/ledger.py`) | pending |
| A38 | Grounding-ledger pattern — mechanically verify every numeric claim/instrument reference in an LLM-generated thesis traces to an actual tool call in that run, before the artifact is persisted | Vibe-Trading → `14-vibe-trading.md` (`agent/grounding.py`) | pending |

## Notes on sequencing within this stage

- A1-A5 first, strictly — A1/A2 harden the correlation matrix that A14 (cold-start fallback) and several vinu-agent/vinu-live concentration checks implicitly trust.
- A6-A14 (vinu-live) and A15-A21 (vinu-agent) can run in parallel with each other once A-1 is done — no cross-dependency between them.
- A22-A26 (vinu-research) is independent of everything else in this stage — safe to do anytime, including in parallel with A-1 through A-3.
- A27-A31 (vinu-simulator) is fully independent — the simulator doesn't feed or depend on anything else in Stage A.
- A32-A35 is fully independent — pure infra/notification hygiene, no coupling to trading logic at all. Good items to hand off separately or do first if you want an easy warm-up.
