# Adoption Tracker

Every adoptable item found across the 13-repo audit, grouped by **which Vina file/service it targets** — not by source repo — because that's the question that actually comes up while building ("anything relevant here from the other repos?"). Each row cites its source so provenance survives long after this research session is forgotten.

**Bucket key:** `A` = cheap/safe hardening of existing code (do first) · `B` = part of the `vinu-screener` build (new capability) · `C` = bigger architectural change, not urgent — revisit only when something in A/B specifically needs it.

**Status key:** `pending` · `in-progress` · `done` · `skipped` (with a one-line reason if skipped).

How to use this while building: before starting work on a Vina file, filter this table to its Target section below. If nothing there answers your question, the source repo is still cloned at `../repos/<name>/` — a scoped grep/read of just that repo is cheap; don't re-trigger a full research sweep unless the area is genuinely uncovered by any of the 8 capabilities in `global-repo-comparison-by-8-capability.md`.

---

## `vinu-screener` (new build — Bucket B items, sequence roughly top-to-bottom)

| Item | Bucket | Status | Source |
|---|---|---|---|
| Condition JSON schema (leaf: indicator/params/field/offset/operator/compare_mode; group: children/logic/negate) | B | pending | FinceptTerminal → `13-fincept-terminal.md` § Adopt (`ConditionEvaluator.h/.cpp`) |
| Non-finite-value guard as a single choke point before any comparison | B | pending | FinceptTerminal → `13-fincept-terminal.md` § Adopt |
| Auto-computed required lookback from the condition tree (warm-up buffer sizing) | B | pending | FinceptTerminal → `13-fincept-terminal.md` § Adopt (`required_bars()`) |
| Two-tier execution — poll mode (batch, rate-limit-floored interval) as the default for ~8000 symbols, not realtime-subscription mode | B | pending | FinceptTerminal → `13-fincept-terminal.md` § Adopt (`ScanMonitor` vs `RealtimeScanRunner`) |
| Edge-gated per-symbol cooldown firing (armed bool + cooldown_min) | B | pending | FinceptTerminal → `13-fincept-terminal.md` § Adopt |
| Keep scanner fully decoupled from order/research/news pipeline until user selects a symbol | B | pending | FinceptTerminal + daily_stock_analysis → `13-fincept-terminal.md`, `04-daily_stock_analysis.md` (both independently confirm this boundary) |
| `actions` JSON bag on each rule for per-rule notification routing | B | pending | FinceptTerminal → `13-fincept-terminal.md` § Adopt |
| Fired-watch audit retention split (permanent history table separate from live rule state) | B | pending | FinceptTerminal → `13-fincept-terminal.md` § Adopt |
| One-shot vs persistent mode as a per-rule config choice | B | pending | FinceptTerminal → `13-fincept-terminal.md` § Adopt |
| Pipeline shape: cached snapshot → hard filter → factor score → risk overlay → concentration overlay → near-score rotation → top-N enrichment | B | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| `HardFilterConfig`-style dataclass as the shape of user-defined rule conditions | B | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| `call_with_timeout` daemon-thread guard for bounding flaky upstream fetch calls at ~8000-symbol scale | B | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt (`source_guard.py`) |
| Risk-overlay-as-penalty-not-filter (bounded additive score + optional hard veto) | B | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| Dry-run/test-rule-before-enable UX (per-target trigger/degraded/skipped counts) | B | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| Coarse→Fine two-stage universe selection (cheap filter over all ~8000, expensive rules only on survivors) | B | pending | Lean → `05-lean.md` § Adopt |
| `IPairList` filter-chain pattern (each rule = class, declared param schema, `supports_backtesting` marker) | B | pending | Freqtrade → `01-freqtrade.md` § Adopt |
| `RemotePairList`'s bearer+TTL-cache+fail-open pattern for exposing screener output over HTTP | B | pending | Freqtrade → `01-freqtrade.md` § Adopt |
| Rolling-operator expression engine as shared, cached feature library (Rank/Slope/Std/WMA/EMA etc.) | B | pending | Qlib → `02-qlib.md` § Adopt |
| Turnover-limiting `n_drop`/`hold_thresh` pattern (avoid candidate list flip-flopping every cycle) | B | pending | Qlib → `02-qlib.md` § Adopt |
| `IndicatorFactory` broadcasting pattern (one calc fn + declared inputs/params, broadcast across all columns) | B | pending | VectorBT → `09-vectorbt.md` § Adopt |

## `vinu-live` (contingency/invalidation rules, halt policy, correlation monitor, signal-conflict, OOD, reconciliation)

| Item | Bucket | Status | Source |
|---|---|---|---|
| `TripleBarrierConfig`-style volatility-adjusted stop/target/trailing thresholds (not static) | A | pending | Hummingbot → `06-hummingbot.md` § Adopt |
| Trailing-stop state machine (activation price + trailing delta) for OOD/emergency-flatten and reduce_only trims | A | pending | Hummingbot → `06-hummingbot.md` § Adopt |
| Three named ATR-stop variants (entry-price / pre-bar-close / current-close keyed) as explicit rule-engine options | A | pending | abu → `07-abu.md` § Adopt |
| Mandatory ≥1 invalidation-condition-per-thesis schema check (with evidence freshness/quality tagging) | A | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| Turbulence index (Mahalanobis-distance regime/stress signal) to cross-check against the OOD detector | A | pending | FinRL → `08-finrl.md` § Adopt (`calculate_turbulence`) |
| `TrailingStopRiskManagementModel`'s peak-tracking drawdown-from-peak flatten, as a per-symbol complement to OOD | A | pending | Lean → `05-lean.md` § Adopt |
| `resolve_signal_conflict_nb`-style explicit conflict-resolution mode enum (Entry/Exit/Adjacent/Opposite) | A | pending | VectorBT → `09-vectorbt.md` § Adopt |
| Realized-slippage-from-planned-price tracker for fill/reconciliation monitoring | A | pending | StockSharp → `10-stocksharp.md` § Adopt |
| Covariance-over-time cold-start fallback (zero-correlation matrix when a new symbol has no history yet) | A | pending | pysystemtrade → `12-pysystemtrade.md` § Adopt |
| Override taxonomy (untradeable/reduce_only/ignored per symbol, with reasons + precedence resolution) generalizing the halt policy | C | pending | pysystemtrade → `12-pysystemtrade.md` § Adopt (`diagOverrides`) |
| Executor-as-state-machine architecture for managing concurrent frozen trade plans | C | pending | Hummingbot → `06-hummingbot.md` § Adopt |
| `IProtection`/`ProtectionReturn` lock abstraction generalizing halt-policy/cooldown into pluggable objects | C | pending | Freqtrade → `01-freqtrade.md` § Adopt |
| Iceberg/TWAP client-side execution algorithms for large-order slicing | C | pending | StockSharp → `10-stocksharp.md` § Adopt |
| Ump-style GMM outcome-cluster veto as an additional statistical pre-trade gate | C | pending | abu → `07-abu.md` § Adopt |

## `vinu-agent` (TradingMandate, kill switch, position sizing, order rate limiting)

| Item | Bucket | Status | Source |
|---|---|---|---|
| Token-bucket rate limiter for sub-second order-submission bursts (complements existing max-daily-orders caps) | A | pending | NautilusTrader → `03-nautilus_trader.md` § Adopt |
| Profitability-based kill switch loop (periodic P&L monitor, decoupled from strategy code) | A | pending | Hummingbot → `06-hummingbot.md` § Adopt |
| Kelly-fraction / ATR-inverse position sizing, always clamped to the hard mandate ceiling as a final step | A | pending | abu → `07-abu.md` § Adopt |
| Rolling-window trade-frequency counter (allocation-free reference impl for max-daily-orders) | A | pending | StockSharp → `10-stocksharp.md` § Adopt (`RiskTradeFreqRule`) |
| Greedy discrete allocation (target weights → integer shares with leftover-cash tracking) for order sizing | A | pending | PyPortfolioOpt → `11-pyportfolioopt.md` § Adopt |
| Incremental average-buy-price tracker for per-symbol running cost-basis | A | pending | FinRL → `08-finrl.md` § Adopt |
| `set_max_notional_per_order()` + emitted audit-event pattern for the runtime-settings admin API | A | pending | NautilusTrader → `03-nautilus_trader.md` § Adopt |
| Notional sizing enforced as the LARGER of explicit notional and `quantity × price`, fail-closed DENY when unpriceable — cross-check `OrderGuard`'s max-order-value check actually does this | A | pending | Vibe-Trading → `14-vibe-trading.md` § Adopt |
| Hash-chained, fsynced, append-only audit ledger for kill-switch/halt/emergency-flatten events (tamper-evident: editing any record breaks every record chained after it) | A | pending | Vibe-Trading → `14-vibe-trading.md` § Adopt (`governance/ledger.py`) |
| Rule object + action enum decoupling — model each TradingMandate limit as an independent Save/Load-able object | C | pending | StockSharp → `10-stocksharp.md` § Adopt |
| Persisted, queryable, independently-resettable per-instrument trade-limit storage | C | pending | pysystemtrade → `12-pysystemtrade.md` § Adopt (`dataTradeLimits`) |
| Min-of-4-independent-risk-multipliers scalar applied to order size, instead of binary reject/allow | C | pending | pysystemtrade → `12-pysystemtrade.md` § Adopt |
| Exhaustive risk-override reason-code enum + valid-transition set for auditable kill-switch/reduce-only decisions | C | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| Refactor TradingMandate checks into an independent, always-invoked checkpoint outside the agent loop | C | pending | NautilusTrader → `03-nautilus_trader.md` § Adopt |
| `PAUSE_FOR_REAUTH` as a third OrderGuard outcome (between allow and reject) for borderline quantitative breaches, distinct from the existing unconditional `require_confirmation` gate | C | pending | Vibe-Trading → `14-vibe-trading.md` § Adopt |
| Mandate consent expiry (`expires_at`) routing to re-authentication, instead of a mandate loaded once and trusted indefinitely | C | pending | Vibe-Trading → `14-vibe-trading.md` § Adopt |
| Five-layer ReAct context-management pipeline (prune → fold → LLM-summarize → explicit-trigger → incremental-update) for long multi-tool-call agent sessions | C | pending | Vibe-Trading → `14-vibe-trading.md` § Adopt (`agent/loop.py`) |

## `vinu-portfolio` (correlation matrix, rebalancing, concentration caps)

| Item | Bucket | Status | Source |
|---|---|---|---|
| `fix_nonpositive_semidefinite` (spectral) — harden the correlation matrix before it feeds any risk check ⭐ highest-priority quick win, directly reduces the bug class already found once this session in the runtime correlation monitor | A | pending | PyPortfolioOpt → `11-pyportfolioopt.md` § Adopt |
| Ledoit-Wolf shrinkage covariance to replace/augment the raw sample correlation matrix | A | pending | PyPortfolioOpt → `11-pyportfolioopt.md` § Adopt |
| `SizeType.TargetPercent`/`TargetValue`-style order-delta resolution for the rebalancer | A | pending | VectorBT → `09-vectorbt.md` § Adopt |
| Portfolio/sector concentration bucket-penalty pattern (graduated, not binary) | A | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| Transaction-cost-aware objective term (`k * sum(|w - w_prev|)`) in the rebalancing objective | A | pending | PyPortfolioOpt → `11-pyportfolioopt.md` § Adopt |
| HRP as a backstop when the correlation matrix is ill-conditioned (small universe/short history) | C | pending | PyPortfolioOpt → `11-pyportfolioopt.md` § Adopt |
| Risk-management-as-target-rescaling stage — operate on the full proposed target set post-construction, not one order at a time | C | pending | Lean → `05-lean.md` § Adopt |

## `vinu-research` (promotion gate, holdout/CV, artifact recorder)

| Item | Bucket | Status | Source |
|---|---|---|---|
| Correlation-clustered CV folds — don't let correlated symbols span train/test in holdout testing | A | pending | abu → `07-abu.md` § Adopt |
| Cross-check the existing deflated-Sharpe gate against vectorbt's explicit `nb_trials` reference formula | A | pending | VectorBT → `09-vectorbt.md` § Adopt |
| Graceful LLM-backend degradation chain (primary → fallback models → deterministic fallback, failure reason surfaced) | A | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| Recorder pattern — persist IC-like signal-quality metrics alongside every promotion run's pass/fail verdict | A | pending | Qlib → `02-qlib.md` § Adopt |
| Point-in-time/lookahead-leakage screening as an explicitly named gate stage | A | pending | awesome-quant (catalog pointer, `pit-release-gate`) (idea only — awesome-quant repo removed from disk, and the consolidated findings doc it was cited from no longer exists either; this note is the only surviving record) |
| Grounding-ledger pattern — mechanically verify every numeric claim/instrument reference in an LLM-generated thesis traces back to an actual tool call made during that generation run, before the artifact is persisted; a structural complement to the deflated-Sharpe/holdout/stress-test gate (that validates the strategy, this validates the thesis text isn't hallucinated) | A | pending | Vibe-Trading → `14-vibe-trading.md` § Adopt (`agent/grounding.py`) |
| Data-derived regime labeling (drawdown/run-up/slope-based) as an additional automatic stress-test dimension | C | pending | TradeMaster (repo removed from disk — idea only, see `repo-list.md` cut-repos table) |

## `vinu-simulator` (fill/slippage/execution realism)

| Item | Bucket | Status | Source |
|---|---|---|---|
| Worst-case-within-candle stop/trailing-stop fill logic | A | pending | Freqtrade → `01-freqtrade.md` § Adopt |
| Volume-capped partial-fill mechanism (cum or per-bar cap) | A | pending | Qlib → `02-qlib.md` § Adopt |
| Gap-down fill rejection guard (reject fills after large opening gaps) | A | pending | abu → `07-abu.md` § Adopt |
| `order.reject_prob` random rejection for broker-unreliability simulation | A | pending | VectorBT → `09-vectorbt.md` § Adopt |
| `LiquidityExceeded`-style circuit breaker (stop filling once volume-share cap hit in a bar) | A | pending | Freqtrade/zipline pattern (idea only — zipline repo removed from disk, and the consolidated findings doc it was cited from no longer exists either; this note is the only surviving record) |
| `FillModel` trait's four hooks (is_limit_filled/is_slipped/fill_limit_inside_spread/synthetic book) as a swappable interface | C | pending | NautilusTrader → `03-nautilus_trader.md` § Adopt |
| Per-security-type fill model dispatch (illiquid small-cap vs liquid large-cap get different assumptions) | C | pending | Lean → `05-lean.md` § Adopt |

## `vinu-infra` / runtime-settings admin API (just shipped — these extend it)

| Item | Bucket | Status | Source |
|---|---|---|---|
| Atomic write + optimistic version token (`get_config_version()` = hash+mtime, diff-only PATCH, skip masked-sensitive overwrites) | A | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| Field-metadata-as-single-source-of-truth registry (title/description/category/ui_control/validation/examples per knob) | C | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |

## Notifications (Telegram/Discord — cross-cutting, no dedicated Vina service)

| Item | Bucket | Status | Source |
|---|---|---|---|
| Dedup + cooldown + quiet-hours + severity + in-flight reservation (stop duplicate kill-switch/halt alerts) | A | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt (`notification_noise.py`) |
| Per-notification-type channel routing (route system-error/kill-switch alerts to a more urgent channel) | A | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |
| Per-delivery-attempt audit trail (error_code/retryable/latency_ms — confirm an alert actually landed) | A | pending | daily_stock_analysis → `04-daily_stock_analysis.md` § Adopt |

---

## How to update this file as work progresses

- Flip `Status` to `in-progress` when you start an item, `done` when it lands (link the commit/PR in the cell if useful), `skipped` with a one-line reason if you decide against it.
- If a new adoptable idea turns up while implementing something (common — you'll re-read a source file for detail and spot something not captured here), add a row under the right target section rather than a new file.
- If an entirely new Vina target emerges that isn't one of the 8 sections above, add a new `##` section rather than shoehorning it into an existing one.
