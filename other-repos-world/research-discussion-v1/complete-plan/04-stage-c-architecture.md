# Stage C — Bigger Architecture (19 items)

**Decision 2026-09-11 (user):** do these properly rather than leaving them as a vague "revisit eventually" — a system that can only halt-or-continue, reject-or-allow, and trusts a mandate indefinitely is too immature to handle real incidents. Stage C is now a **committed** stage, not an optional one.

**But sequencing still matters.** "Do it right" for a few of these means building them at the point their shape is actually determined — not speculatively. Building the concurrent-trade-plan state machine or the agent context pipeline *before* `vinu-screener` exists to define their load/concurrency requirements means guessing at the interface and rebuilding it. So Stage C is split into three tiers:

- **C-now** — shape is fully determined by code that exists today, and the change makes the system meaningfully more robust regardless of the screener. Do these right after Stage A, before Stage B.
- **C-with-B** — correct shape depends on `vinu-screener`'s requirements. Build as part of Stage B, at the point that B forces the interface.
- **C-signal** — genuinely need a real-world signal (a real incident, or backtests demonstrably wrong in a specific way) to get the requirements right. Doing these blind is a guess. Keep the sharpened trigger; revisit when it fires.

This list is **not internally sequenced** within a tier — pick by what the preceding work surfaces as the real need.

Status key: `pending` · `in-progress` · `done` · `skipped` (reason) · `deferred` (trigger not yet fired).

---

## Tier C-now — do after Stage A, before Stage B (12 items; 7 done, 1 skipped, 4 pending)

Done: C4/C8/C9/C17 (OrderGuard-expressiveness cluster), C18 (mandate consent expiry), C10 (audit — nothing bypasses OrderGuard; froze it with a tripwire test), C11 (HRP allocation mode). Skipped: C6. **Remaining: C12, C13, C16, C5.**

Status key: `pending` · `in-progress` · `done` · `skipped`.

| ID | Item | Status |
|---|---|---|
| C4 | **Done 2026-09-11.** New `vinu_agent/broker/symbol_overrides.py` — `SymbolOverrideStore` (SQLite-backed, shared, persistent — also covers C7's storage half): per-symbol `UNTRADEABLE` / `REDUCE_ONLY` / `IGNORED`, each with a reason + `set_by` + timestamp, transitions validated against C9's `ALLOWED_OVERRIDE_TRANSITIONS`, `clear()` resets one symbol at a time. `OrderGuard.check()` consults it *before* any mandate check (fail-open if the store errs). HTTP: `GET/PUT/DELETE /agent/broker/overrides[/{symbol}]`. 7 store tests + 4 guard-integration tests. |
| C9 | **Done 2026-09-11.** New `vinu_agent/broker/guard_codes.py` — `ReasonCode` (one stable string code per decision cause, on every `GuardResult` now), `GuardOutcome` (ALLOW / REJECT / PAUSE_FOR_REAUTH), `OverrideState` + `OVERRIDE_PRECEDENCE` + `ALLOWED_OVERRIDE_TRANSITIONS` + `transition_allowed()`. 6 tests. Built together with C4/C17 as planned. |
| C6 | **skipped 2026-09-11** — `TradingMandate`-into-rule-objects refactor. Its only stated justification was "enabler for C4/C8/C17" — and all four of C4/C8/C9/C17 shipped *without* it: C8's multipliers read the flat mandate fields directly in one method, no per-rule structure needed. A structural rewrite of a safety-critical dataclass with no remaining consumer that needs it, and real regression risk, is exactly what the plan's "skip when the trigger doesn't fire" note covers. `vinu-agent`; StockSharp → `10-stocksharp.md`. |
| C8 | **Done 2026-09-11.** `MultiplierResult` + `OrderGuard.position_size_multiplier()` — a `[0,1]` scalar from `min()` of the soft quantitative limits (`max_order_value`, `max_position_pct`, `max_capital_utilization_pct`, and vinu-portfolio's per-symbol risk-budget `suggested_size_multiplier` via new `_risk_budget_multiplier()`). Hard gates stay in `check()`, unconditional. `trade_tool.py` (opt-in `VINU_AGENT_GUARD_SOFT_LIMITS`, default off, non-`reduce_only` only): asks for the multiplier, floors `qty × multiplier`, submits the *smaller* order through the still-fail-closed `check()`, rejects only if it scales below one share, and reports `size_scaled` + an `order_size_scaled` audit event. 6 guard tests + 3 trade-tool tests. |
| C17 | **Done 2026-09-11.** `GuardResult` gained `code` + `outcome` (both default consistently with `allowed`, so every existing call site is unchanged) and a `needs_reauth` property. `REAUTH_BAND_FRACTION` (env `VINU_AGENT_GUARD_REAUTH_FRACTION`, default 1.0 = disabled): an order whose value / position size lands in the top band below `max_order_value` / `max_position_pct` returns `PAUSE_FOR_REAUTH` — `bool(result)` is still False so a bool-only caller fails safe, and `trade_tool.py` routes it to the confirmation flow with the *reason* as the message + a `reason_code`, distinct from the unconditional `require_confirmation`. 5 tests. |
| C18 | **Done 2026-09-11.** `TradingMandate.consent_expires_at` (ISO-8601; naive treated as UTC; empty = never) + `consent_expired()`. `load()` reads it from `mandate.yaml` and logs a WARNING if already expired; `to_dict()` surfaces `consent_expires_at` + a live `consent_expired` bool. `OrderGuard.check()` blocks new/increasing positions with `ReasonCode.MANDATE_EXPIRED` once expired — `reduce_only` (de-risking) is always exempt, same posture as the kill switch. Renewal without a restart: `POST /agent/broker/mandate/renew` (`{days}` or `{until}`) rewrites only the `consent_expires_at` key in `mandate.yaml`, preserving the rest, and audits it; `GET /agent/broker/mandate` shows current state. 4 mandate/guard tests + 5 route tests. |
| C10 | **Done 2026-09-11 (audit + tripwire; no refactor needed).** Audited every order-submission path: the only two `broker.submit_order(` calls in `vinu_agent/` are both in `tools/trade_tool.py` (replay branch + live branch, the latter after `guard.check()` + `guard.pre_approve()` inside `kill_switch_lock()`), and `POST /broker/order` delegates to that same `TradeTool`. Nothing bypasses `OrderGuard` — so per C10's own revisit trigger this is "process/audit hardening, not a functional fix". Froze the invariant with a new `test_order_submission_always_guarded.py` (AST-scans the package, fails CI on any new `submit_order`/`replace_order` call site outside `trade_tool.py`). |
| C11 | **Done 2026-09-11.** New `hrp_weights()` in `risk_utils.py` — Hierarchical Risk Parity (López de Prado 2016): correlation-aware allocation via single-linkage clustering + recursive bisection, **never inverts the covariance matrix**, so an ill-conditioned correlation estimate degrades to a flatter dendrogram instead of a blow-up; uses the A1/A2-hardened `robust_correlation_matrix` for the distance metric; returns `None` (→ caller falls back to inverse-vol) when there's too little history to cluster. Wired into `allocate_risk_parity` as `allocation_mode="hrp"` (config + `VINU_PORTFOLIO_ALLOCATION_MODE`, **default `"inverse_vol"` = unchanged**). Note: Vina's default inverse-vol allocator is *already* immune to a bad matrix (it only reads the diagonal), so HRP is offered as the correlation-aware upgrade path rather than a literal "backstop". 5 `risk_utils` tests + 2 service tests. | `vinu-portfolio` |
| C12 | **pending** — Risk-management-as-target-rescaling stage: operate on the full proposed target-weight set *after* construction, catching multi-order sector/concentration breaches no single-order check sees. `vinu-portfolio`; Lean → `05-lean.md`. |
| C13 | **pending** — Data-derived regime labeling (drawdown / run-up / slope-based) as an additional automatic stress-test dimension alongside the fixed crisis windows. `vinu-research`; TradeMaster (repo removed). Purely additive to `meets_promotion_bar()`. |
| C16 | **pending** — Field-metadata-as-single-source-of-truth config registry for the runtime-settings admin API (type, range, description, default, category — one declaration feeding validation + docs + any future UI). `vinu-infra`; daily_stock_analysis → `04-daily_stock_analysis.md`. Builds on A21. |
| C5 | **pending** — Ump-style GMM outcome-cluster veto as an additional statistical pre-trade gate. `vinu-live` / `vinu-agent`; abu → `07-abu.md`. Sits on top of G1's (now stable) promotion-gate wiring. |

## Tier C-with-B — build during Stage B, when the screener forces the interface (4 items)

| ID | Item | Target | What B needs to reveal first | Source |
|---|---|---|---|---|
| C1 | Executor-as-state-machine architecture for concurrent frozen trade plans | `vinu-live` | The screener will drive many more concurrent plans than today; its concurrency + lifecycle needs define whether this is one shared state object or something lighter | Hummingbot → `06-hummingbot.md` |
| C14 | `FillModel` trait's four hooks (`is_limit_filled` / `is_slipped` / `fill_limit_inside_spread` / synthetic book) as a swappable interface | `vinu-simulator` | Do alongside Stage A-5 (A27–A31, imminent) — if those individual fill-realism items start needing a shared interface rather than separate bolt-ons, that's the trigger, and A-5 will show it | NautilusTrader → `03-nautilus_trader.md` |
| C19 | Five-layer ReAct context-management pipeline (prune → fold → LLM-summarize → explicit-trigger → incremental-update) for long multi-tool-call agent sessions | `vinu-agent` | Explicitly tied to `vinu-screener`'s LLM re-rank step (and/or `vinu-agent`'s ReAct loop) hitting real context-window limits — the pipeline's stages should be shaped by the actual overflow pattern | Vibe-Trading → `14-vibe-trading.md` |
| C7 | Persisted, queryable, independently-resettable per-instrument trade-limit storage | `vinu-agent` | `DailyLimitStore` covers the counting need today; the screener's auditability requirements (per-symbol limit history, selective reset) will define the query surface | pysystemtrade → `12-pysystemtrade.md` |

## Tier C-signal — needs a real incident or a specific observed failure to scope correctly (3 items)

| ID | Item | Target | Trigger that must fire first | Source |
|---|---|---|---|---|
| C2 | `IProtection` / `ProtectionReturn` lock abstraction generalizing halt-policy / cooldown | `vinu-live` | The current ad hoc halt logic actually becoming hard to extend for a new halt-policy need — building the abstraction before that is premature generalization | Freqtrade → `01-freqtrade.md` |
| C3 | Iceberg / TWAP client-side execution algorithms for large-order slicing | `vinu-live` | Real position sizes growing enough to move the market noticeably on a single order — the slicing parameters are untestable guesses without real fill data at scale | StockSharp → `10-stocksharp.md` |
| C15 | Per-security-type fill-model dispatch (illiquid small-cap vs liquid large-cap get different fill assumptions) | `vinu-simulator` | Backtest results looking *systematically* wrong specifically for small/illiquid names — the per-type assumptions need that evidence to be calibrated rather than invented | Lean → `05-lean.md` |

---

*(C17–C19 added 2026-09-10 once Vibe-Trading's real URL was found and it was fully audited. Three-tier split added 2026-09-11 per the user's decision to commit to Stage C.)*

## Notes

- The tier a "C-signal" item sits in is itself revisable — if Stage A/B work makes one of them clearly shape-determined, promote it to C-now/C-with-B.
- A "C-signal" item whose trigger never fires across all of Stage B is a candidate to mark `skipped` rather than carry indefinitely.
- C-now items still get individually re-verified against current code immediately before implementation, same habit as Stages 0 and A — several Stage A items turned out already-done on that check.
