# Global Repo Comparison — Capability Matrix

Segregates the 14 kept repos — the original 13 plus Vibe-Trading, added 2026-09-10 once its real URL was found and it was confirmed as the actual source of Vina's own LLM-agent design — (see `../repo-list.md` and the per-repo files in `../comprison-other-vinu/`) by eight capabilities: the original five (backtesting, live trading, LLM capability, screener/scanner, broker integration) plus three added after reviewing what else recurred across the actual research — risk/portfolio management, promotion/validation rigor, and execution/fill realism. A repo can and often does sit in multiple buckets — this file is a fast lookup, not a replacement for the per-repo detail files.

## Quick-reference matrix

| Repo | Backtesting | Live Trading | LLM Capability | Screener/Scanner | Broker Integration | Risk/Portfolio Mgmt | Promotion/Validation Rigor | Execution/Fill Realism |
|---|---|---|---|---|---|---|---|---|
| Freqtrade | ✅ | ✅ | ❌ (FreqAI is ML, not LLM) | ✅ (pairlist filter chain) | ✅ (20+ exchanges via CCXT, crypto) | ✅ (Protection framework: StoplossGuard, MaxDrawdown, Cooldown) | ❌ (no promotion gate; user just enables a strategy) | ✅ (worst-case-within-candle stop fills) |
| Qlib | ✅ | ⚠️ research-first, no confirmed live-broker path | ✅ (RD-Agent LLM R&D loop) | ❌ | ❌ | ⚠️ (portfolio strategies exist, no dedicated risk-rule engine) | ⚠️ (rich IC/Sharpe recorder metrics, but no enforced blocking gate found) | ✅ (cost/impact-aware exchange, volume-capped fills) |
| NautilusTrader | ✅ | ✅ | ❌ | ❌ | ✅ (broker/exchange adapters) | ✅ (Rust RiskEngine, live-mutable knobs, TradingState) | ❌ | ✅ (trait-based swappable FillModel) |
| daily_stock_analysis | ✅ (text-based forward backtest) | ❌ (analysis/dashboard only, no order execution) | ✅ (heavily LLM-driven core) | ✅ (most mature of all 13) | ❌ | ✅ (penalty-based risk overlay + concentration overlay) | ❌ (LLM re-rank + risk scoring, not a statistical overfitting gate) | ❌ (no live orders, nothing to fill) |
| Lean | ✅ | ✅ | ❌ | ✅ (coarse→fine universe selection) | ✅ (IBKR/Coinbase/Binance/OANDA) | ✅ (dedicated Risk Management pipeline stage) | ❌ | ✅ (per-security-type FillModel/SlippageModel/FeeModel) |
| Hummingbot | ⚠️ limited, live-focused | ✅ | ❌ | ❌ | ✅ (many exchanges, crypto-focused) | ⚠️ (per-position TripleBarrier + P&L kill switch, not a portfolio risk engine) | ❌ | ⚠️ (partial-fill-aware order renewal, no dedicated slippage model) |
| abu | ✅ | ❌ (backtest/research only) | ❌ | ⚠️ (similarity-based stock picking, not rule-based screening) | ❌ | ✅ (Ump veto layer + Kelly/ATR sizing with caps) | ✅ (grid search + correlation-aware CV against overfitting — closest of all 13) | ✅ (intraday slippage models + gap-down guard) |
| FinRL | ✅ (Gym envs) | ✅ (paper trading via Alpaca — same broker as Vina) | ❌ (RL, not LLM) | ❌ | ✅ (Alpaca) | ✅ (turbulence-index kill switch, reward-shaped stop-loss) | ⚠️ (validation-Sharpe model selection, RL-specific not general) | ❌ (simplistic cash-clipped sizing, no dedicated fill model) |
| VectorBT | ✅ (core purpose) | ❌ | ❌ | ❌ | ❌ | ⚠️ (order-level SL/TP/trailing-stop state machine, not portfolio-level) | ✅ (Deflated Sharpe Ratio with explicit `nb_trials` correction) | ✅ (numba-JIT order engine, `reject_prob`, full validation) |
| StockSharp | ✅ (own matching engine) | ✅ | ❌ | ❌ | ✅ (multi-broker/exchange, FIX) | ✅ (composable serializable risk-rule engine, margin/stop-out) | ❌ | ✅ (realized-slippage tracker, iceberg/TWAP/VWAP algos) |
| PyPortfolioOpt | ❌ (pure optimization math, no simulation) | ❌ | ❌ | ❌ | ❌ | ✅ (HRP, Black-Litterman, shrinkage, PSD repair — this is its entire purpose) | ❌ | ❌ (no simulation at all) |
| pysystemtrade | ✅ | ✅ (Carver's own live capital system) | ❌ | ❌ | ✅ (futures broker, production control plane) | ✅ (min-of-4-multipliers overlay, formal Override taxonomy) | ❌ (production control plane, not strategy vetting) | ✅ (layered execution-algo hierarchy with timeout policies) |
| FinceptTerminal | ✅ | ✅ (human-approval-gated) | ✅ (37 AI agents, multi-provider) | ✅ (algo_engine — 2nd most mature) | ✅ (16 broker integrations incl. Alpaca) | ⚠️ (per-strategy daily-loss-limit pause, not a full portfolio risk engine) | ❌ (human approval only, no statistical gate) | ❌ (not confirmed in audit) |
| Vibe-Trading | ❌ (no backtest engine found — live-first) | ✅ (multi-broker via MCP + direct-SDK incl. Alpaca) | ✅ (sophisticated ReAct core: 5-layer context mgmt, grounding ledger anti-hallucination gate) | ⚠️ (market_screener_tool.py, shadow_account/scanner.py — narrower than DSA/FinceptTerminal) | ✅ (Robinhood via MCP + tiger/alpaca/okx/binance/futu via direct-SDK) | ✅ (near-exact structural analog to Vina's own OrderGuard/TradingMandate, plus hash-chained tamper-evident audit ledger) | ❌ (evidence-presence checking on recommendations, not overfitting-correction statistics) | ❌ (not confirmed — live-first, no simulator found) |

**Legend:** ✅ has it · ❌ doesn't · ⚠️ partial/qualified

---

## 1. Backtesting-only (no live trading)

Repos whose value is entirely in simulation/research — nothing here places a real order.

- **VectorBT** — vectorized, numba-JIT backtesting engine; this is its entire purpose, no live path exists.
- **PyPortfolioOpt** — not even a backtester in the simulation sense; it's pure portfolio-construction math (weights in, weights out). No order simulation, no live path.
- **abu** — grid search, cross-validation, and historical trade simulation, but confirmed no live order submission anywhere in the codebase.
- **daily_stock_analysis** — has a forward-looking text-based backtest engine (parses LLM recommendation text, walks forward bars) but this evaluates *past recommendations*, not live capital; there is no broker/order-execution layer at all.

**Adoptable items grouped here** (from `adoption-tracker.md`'s `vinu-simulator` section — same underlying work as §8 below, viewed from the backtest-honesty angle rather than the live-fill-quality angle):

| Item | Target | Bucket | Source |
|---|---|---|---|
| Worst-case-within-candle stop/trailing-stop fill logic | `vinu-simulator` | A | Freqtrade → `../comprison-other-vinu/01-freqtrade.md` § Adopt |
| Volume-capped partial-fill mechanism (cum or per-bar cap) | `vinu-simulator` | A | Qlib → `../comprison-other-vinu/02-qlib.md` § Adopt |
| Gap-down fill rejection guard | `vinu-simulator` | A | abu → `../comprison-other-vinu/07-abu.md` § Adopt |
| `order.reject_prob` random rejection | `vinu-simulator` | A | VectorBT → `../comprison-other-vinu/09-vectorbt.md` § Adopt |
| `LiquidityExceeded`-style circuit breaker | `vinu-simulator` | A | Freqtrade/zipline pattern (idea only — zipline repo removed from disk, and the consolidated findings doc it was cited from no longer exists either; this note is the only surviving record) |
| `FillModel` trait's four hooks (swappable fill/slip/synthetic-book strategies) | `vinu-simulator` | C | NautilusTrader → `../comprison-other-vinu/03-nautilus_trader.md` § Adopt |
| Per-security-type fill model dispatch | `vinu-simulator` | C | Lean → `../comprison-other-vinu/05-lean.md` § Adopt |

## 2. Live Trading (real or paper broker execution)

- **Freqtrade** — dry-run/live parity, real exchange execution via CCXT.
- **NautilusTrader** — Rust-core deterministic engine, live and backtest share the same compiled code path.
- **Lean** — broker adapters for IBKR, Coinbase, Binance, OANDA; full live/paper/backtest CLI.
- **Hummingbot** — built primarily *for* live market-making/arbitrage; live execution is its main use case.
- **FinRL** — has a live paper-trading loop specifically against **Alpaca** (Vina's own broker), with turbulence-triggered liquidation.
- **StockSharp** — full live platform with its own margin/stop-out simulation and broker connectivity.
- **pysystemtrade** — Rob Carver's actual live capital system; DB-backed order stack, overrides, locks — the most production-hardened control plane of any repo audited.
- **FinceptTerminal** — live trading exists but is deliberately human-approval-gated (`DeploymentRunner`), a distinct, more conservative posture than the others.
- **Vibe-Trading** — multi-broker live trading via two parallel gate implementations (MCP-wrapped remote tools for Robinhood, direct-SDK for tiger/alpaca/okx/binance/futu), both sharing identical fail-closed ceremony: mandate validity → consent expiry → halt-flag → order-intent parse → position/balance read → ALLOW/DENY/PAUSE_FOR_REAUTH.

**Adoptable items grouped here** (robustness/scale multipliers on Vina's already-working live path — from `vinu-live` and `vinu-agent` sections of `adoption-tracker.md`):

| Item | Target | Bucket | Source |
|---|---|---|---|
| `TripleBarrierConfig`-style volatility-adjusted stop/target/trailing thresholds (not static) | `vinu-live` | A | Hummingbot → `../comprison-other-vinu/06-hummingbot.md` § Adopt |
| Trailing-stop state machine (activation price + trailing delta) | `vinu-live` | A | Hummingbot → `../comprison-other-vinu/06-hummingbot.md` § Adopt |
| Executor-as-state-machine architecture for concurrent frozen trade plans | `vinu-live` | C | Hummingbot → `../comprison-other-vinu/06-hummingbot.md` § Adopt |
| `IProtection`/`ProtectionReturn` lock abstraction generalizing halt-policy/cooldown | `vinu-live` | C | Freqtrade → `../comprison-other-vinu/01-freqtrade.md` § Adopt |
| Iceberg/TWAP client-side execution algorithms for large-order slicing | `vinu-live` | C | StockSharp → `../comprison-other-vinu/10-stocksharp.md` § Adopt |
| Profitability-based kill switch loop (periodic P&L monitor, decoupled from strategy code) | `vinu-agent` | A | Hummingbot → `../comprison-other-vinu/06-hummingbot.md` § Adopt |
| Token-bucket rate limiter for sub-second order-submission bursts | `vinu-agent` | A | NautilusTrader → `../comprison-other-vinu/03-nautilus_trader.md` § Adopt |
| `set_max_notional_per_order()` + emitted audit-event pattern | `vinu-agent` | A | NautilusTrader → `../comprison-other-vinu/03-nautilus_trader.md` § Adopt |
| Three named ATR-stop variants (entry-price / pre-bar-close / current-close keyed) as explicit rule-engine options | `vinu-live` | A | abu → `../comprison-other-vinu/07-abu.md` § Adopt |
| Turbulence index (Mahalanobis-distance regime/stress signal) to cross-check against the OOD detector | `vinu-live` | A | FinRL → `../comprison-other-vinu/08-finrl.md` § Adopt (`calculate_turbulence`) |
| `TrailingStopRiskManagementModel`'s peak-tracking drawdown-from-peak flatten, per-symbol complement to OOD | `vinu-live` | A | Lean → `../comprison-other-vinu/05-lean.md` § Adopt |
| `resolve_signal_conflict_nb`-style explicit conflict-resolution mode enum (Entry/Exit/Adjacent/Opposite) | `vinu-live` | A | VectorBT → `../comprison-other-vinu/09-vectorbt.md` § Adopt |
| Notional sizing enforced as the LARGER of explicit notional and `quantity × price`, fail-closed DENY when unpriceable | `vinu-agent` | A | Vibe-Trading → `../comprison-other-vinu/14-vibe-trading.md` § Adopt |
| `PAUSE_FOR_REAUTH` as a third OrderGuard outcome for borderline quantitative breaches | `vinu-agent` | C | Vibe-Trading → `../comprison-other-vinu/14-vibe-trading.md` § Adopt |
| Mandate consent expiry routing to re-authentication, instead of a mandate trusted indefinitely | `vinu-agent` | C | Vibe-Trading → `../comprison-other-vinu/14-vibe-trading.md` § Adopt |

*(Correction: these 4 rows were missing from this file's first pass — found by a completeness check against `adoption-tracker.md` after the fact. Confirmed no longer missing as of this edit.)*

## 3. LLM Capabilities

Only two of the 13 have genuine LLM integration — everything else in this list is ML/RL (a meaningfully different technique, not LLM-based reasoning/generation).

- **daily_stock_analysis** — LLM is the core of the product: LLM re-ranking of screened candidates (with graceful multi-model degradation), LLM-generated research theses with structured invalidation conditions, multi-agent disagreement reconciliation between LLM-driven opinion agents.
- **FinceptTerminal** — 37 "AI Agents" modeled on named investors (Buffett, Graham, Lynch, Munger, Klarman, Marks…) plus economic/geopolitics frameworks, multi-provider (OpenAI, Anthropic, Gemini, Groq, DeepSeek, MiniMax, OpenRouter, Ollama), local LLM support.
- **Qlib** — has RD-Agent, a separate companion project doing LLM-driven autonomous factor/model R&D — worth noting as LLM-adjacent, though it's a bolted-on research-automation tool, not core to Qlib's own architecture the way it is for the two above.
- Everything else (Freqtrade's FreqAI, FinRL, TradeMaster-class RL frameworks) uses classical ML/RL — no LLM reasoning or generation anywhere in these systems.
- **Vibe-Trading** — the most sophisticated LLM-agent *engineering* (not research capability) of anything audited: a five-layer ReAct context-management pipeline, and a grounding ledger that mechanically validates the LLM's final answer against actual tool-call evidence rather than trusting the model's citations. Confirmed as the actual source repo the LLM-agent concept in Vina's own `vinu-agent` was adopted from.

**Adoptable items grouped here** (from `adoption-tracker.md`'s `vinu-research` section — protecting Vina's existing LLM moat, not building a new one):

| Item | Target | Bucket | Source |
|---|---|---|---|
| Graceful LLM-backend degradation chain (primary → fallback models → deterministic fallback, failure reason surfaced) | `vinu-research` | A | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| Grounding-ledger pattern — mechanically verify every numeric claim/instrument reference in an LLM-generated thesis traces to an actual tool call in that generation run, before the artifact is persisted | `vinu-research` | A | Vibe-Trading → `../comprison-other-vinu/14-vibe-trading.md` § Adopt (`agent/grounding.py`) |
| Five-layer ReAct context-management pipeline for long multi-tool-call agent sessions | `vinu-agent` | C | Vibe-Trading → `../comprison-other-vinu/14-vibe-trading.md` § Adopt (`agent/loop.py`) |

## 4. Screener / Scanner

- **daily_stock_analysis** — the most mature of all 13: declarative `HardFilterConfig` (~35 knobs) → factor score → risk overlay → concentration overlay → optional LLM re-rank → dry-run test-before-enable. Full production pipeline with ~2 years of iteration.
- **FinceptTerminal** — the cleanest condition-schema/scan-mechanics reference: nested AND/OR JSON rule trees, auto-computed lookback, non-finite-value guard, edge-gated cooldown firing, two scan modes (poll vs event-driven) sharing one evaluator.
- **Freqtrade** — pairlist filter chain (`VolumePairList`, `AgeFilter`, `PriceFilter`, etc.) is a real screening mechanism, though scoped to narrowing a trading universe, not a general rule-based alert scanner.
- **Lean** — coarse→fine two-stage universe selection (~8000 symbols → ~1000 → ~500) is screening in spirit, built for periodic universe rebalancing rather than continuous rule-based alerting.
- **abu** — similarity/correlation-based stock picking exists but is narrower (find symbols with similar historical price paths), not a general declarative rule engine.

**Vina's `vinu-screener` should draw primarily from daily_stock_analysis (pipeline shape) and FinceptTerminal (condition schema + scan mechanics)** — see those two files in `../comprison-other-vinu/` for the full breakdown.

**Adoptable items grouped here** — the entire `vinu-screener` section of `adoption-tracker.md` maps 1:1 onto this capability, since it's the one bucket that's a wholly new build rather than hardening something that exists:

| Item | Target | Bucket | Source |
|---|---|---|---|
| Condition JSON schema (leaf: indicator/params/field/offset/operator/compare_mode; group: children/logic/negate) | `vinu-screener` | B | FinceptTerminal → `../comprison-other-vinu/13-fincept-terminal.md` § Adopt (`ConditionEvaluator.h/.cpp`) |
| Non-finite-value guard as a single choke point before any comparison | `vinu-screener` | B | FinceptTerminal → `../comprison-other-vinu/13-fincept-terminal.md` § Adopt |
| Auto-computed required lookback from the condition tree (warm-up buffer sizing) | `vinu-screener` | B | FinceptTerminal → `../comprison-other-vinu/13-fincept-terminal.md` § Adopt (`required_bars()`) |
| Two-tier execution — poll mode as the default for ~8000 symbols, not realtime-subscription mode | `vinu-screener` | B | FinceptTerminal → `../comprison-other-vinu/13-fincept-terminal.md` § Adopt (`ScanMonitor` vs `RealtimeScanRunner`) |
| Edge-gated per-symbol cooldown firing (armed bool + cooldown_min) | `vinu-screener` | B | FinceptTerminal → `../comprison-other-vinu/13-fincept-terminal.md` § Adopt |
| Keep scanner fully decoupled from order/research/news pipeline until user selects a symbol | `vinu-screener` | B | FinceptTerminal + daily_stock_analysis → `../comprison-other-vinu/13-fincept-terminal.md`, `04-daily_stock_analysis.md` (both independently confirm this boundary) |
| `actions` JSON bag on each rule for per-rule notification routing | `vinu-screener` | B | FinceptTerminal → `../comprison-other-vinu/13-fincept-terminal.md` § Adopt |
| Fired-watch audit retention split (permanent history table separate from live rule state) | `vinu-screener` | B | FinceptTerminal → `../comprison-other-vinu/13-fincept-terminal.md` § Adopt |
| One-shot vs persistent mode as a per-rule config choice | `vinu-screener` | B | FinceptTerminal → `../comprison-other-vinu/13-fincept-terminal.md` § Adopt |
| Pipeline shape: cached snapshot → hard filter → factor score → risk overlay → concentration overlay → near-score rotation → top-N enrichment | `vinu-screener` | B | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| `HardFilterConfig`-style dataclass as the shape of user-defined rule conditions | `vinu-screener` | B | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| `call_with_timeout` daemon-thread guard for bounding flaky upstream fetch calls at ~8000-symbol scale | `vinu-screener` | B | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt (`source_guard.py`) |
| Risk-overlay-as-penalty-not-filter (bounded additive score + optional hard veto) | `vinu-screener` | B | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| Dry-run/test-rule-before-enable UX (per-target trigger/degraded/skipped counts) | `vinu-screener` | B | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| Coarse→Fine two-stage universe selection (cheap filter over all ~8000, expensive rules only on survivors) | `vinu-screener` | B | Lean → `../comprison-other-vinu/05-lean.md` § Adopt |
| `IPairList` filter-chain pattern (each rule = class, declared param schema, `supports_backtesting` marker) | `vinu-screener` | B | Freqtrade → `../comprison-other-vinu/01-freqtrade.md` § Adopt |
| `RemotePairList`'s bearer+TTL-cache+fail-open pattern for exposing screener output over HTTP | `vinu-screener` | B | Freqtrade → `../comprison-other-vinu/01-freqtrade.md` § Adopt |
| Rolling-operator expression engine as shared, cached feature library (Rank/Slope/Std/WMA/EMA etc.) | `vinu-screener` | B | Qlib → `../comprison-other-vinu/02-qlib.md` § Adopt |
| Turnover-limiting `n_drop`/`hold_thresh` pattern (avoid candidate list flip-flopping every cycle) | `vinu-screener` | B | Qlib → `../comprison-other-vinu/02-qlib.md` § Adopt |
| `IndicatorFactory` broadcasting pattern (one calc fn + declared inputs/params, broadcast across all columns) | `vinu-screener` | B | VectorBT → `../comprison-other-vinu/09-vectorbt.md` § Adopt |

## 5. Broker / Exchange Integration

- **Freqtrade** — 20+ crypto exchanges via CCXT.
- **NautilusTrader** — broker/exchange adapters, built for institutional multi-venue use.
- **Lean** — IBKR, Coinbase, Binance, OANDA.
- **Hummingbot** — many crypto exchanges, connector architecture designed for easy addition of new ones.
- **FinRL** — Alpaca (same broker Vina uses).
- **StockSharp** — multi-broker/exchange with FIX dialect support, built for regulatory-heavy institutional markets.
- **pysystemtrade** — a live futures broker (production system), plus the three-tier order-stack reconciliation architecture.
- **FinceptTerminal** — 16 broker integrations per its README (Zerodha, Angel One, Upstox, Fyers, Dhan, Groww, Kotak, IIFL, 5paisa, AliceBlue, Shoonya, Motilal, IBKR, Alpaca, Tradier, Saxo) — includes Alpaca.
- **Vibe-Trading** — Robinhood via MCP, plus tiger/alpaca/okx/binance/futu via direct-SDK connectors (includes Alpaca, Vina's own broker).
- **Qlib, daily_stock_analysis, abu, VectorBT, PyPortfolioOpt** — no broker integration; these are research/analysis/optimization tools only.

**Adoptable items grouped here**: none. This capability is deliberately not being pursued — Vina is Alpaca-only by design, and the one broker-breadth pattern noted during research (vn.py's gateway abstraction) belongs to a repo that was cut from the kept 13 specifically because this capability isn't needed. Stated explicitly rather than left silent.

## 6. Risk / Portfolio Management

Most repos have *some* risk logic, but the bar here is a dedicated, reusable risk-rule/portfolio-construction layer — not just an inline check.

- **PyPortfolioOpt** — this is its entire purpose: HRP, Black-Litterman, shrinkage estimators, PSD repair, discrete allocation. The deepest, most citation-backed portfolio-construction math of any repo audited, but with zero simulation or execution around it.
- **pysystemtrade** — the min-of-4-independent-multipliers risk overlay (applied as one conservative portfolio-wide scalar) plus a formal Override taxonomy (bad/duplicate/ignored/untradeable instrument, with precedence resolution) is the most production-hardened *operational* risk-control layer found — DB-persisted, queryable, auditable.
- **StockSharp** — a composable, serializable risk-rule engine (`IRiskRule` objects, `Save`/`Load` round-trippable) with risk *actions* (ClosePositions/StopTrading/CancelOrders) decoupled from the rule that triggered them.
- **NautilusTrader** — a Rust-native `RiskEngine` with live-mutable limits and an audit-event-emitting `TradingState` — the closest match to where Vina's new runtime-settings admin API is heading.
- **Freqtrade, Lean, abu, FinRL, daily_stock_analysis** — each has a real risk layer (Protection framework, dedicated Risk Management pipeline stage, Ump veto + capped position sizing, turbulence-index kill switch, penalty-based risk overlay respectively) but narrower in scope than the four above.
- **Hummingbot, VectorBT, FinceptTerminal** — partial: per-position or per-strategy risk controls exist, but nothing at full-portfolio scope.
- **Vibe-Trading** — a near-exact structural analog to Vina's own OrderGuard/TradingMandate (`live/mandate/`, `live/order_guard.py`, `live/halt.py`), independently arrived at, plus two ideas none of the other 13 have: a `PAUSE_FOR_REAUTH` third outcome between allow/deny, and a hash-chained tamper-evident audit ledger for every gate decision.

**Adoptable items grouped here** — the largest bucket by item count: all of `adoption-tracker.md`'s `vinu-agent` (12 items) + `vinu-portfolio` (7 items) sections, combined:

| Item | Target | Bucket | Source |
|---|---|---|---|
| Kelly-fraction / ATR-inverse position sizing, always clamped to the hard mandate ceiling | `vinu-agent` | A | abu → `../comprison-other-vinu/07-abu.md` § Adopt |
| Rolling-window trade-frequency counter (allocation-free reference impl for max-daily-orders) | `vinu-agent` | A | StockSharp → `../comprison-other-vinu/10-stocksharp.md` § Adopt (`RiskTradeFreqRule`) |
| Greedy discrete allocation (target weights → integer shares with leftover-cash tracking) | `vinu-agent` | A | PyPortfolioOpt → `../comprison-other-vinu/11-pyportfolioopt.md` § Adopt |
| Incremental average-buy-price tracker for per-symbol running cost-basis | `vinu-agent` | A | FinRL → `../comprison-other-vinu/08-finrl.md` § Adopt |
| Rule object + action enum decoupling — each TradingMandate limit as an independent Save/Load-able object | `vinu-agent` | C | StockSharp → `../comprison-other-vinu/10-stocksharp.md` § Adopt |
| Persisted, queryable, independently-resettable per-instrument trade-limit storage | `vinu-agent` | C | pysystemtrade → `../comprison-other-vinu/12-pysystemtrade.md` § Adopt (`dataTradeLimits`) |
| Min-of-4-independent-risk-multipliers scalar applied to order size, instead of binary reject/allow | `vinu-agent` | C | pysystemtrade → `../comprison-other-vinu/12-pysystemtrade.md` § Adopt |
| Exhaustive risk-override reason-code enum + valid-transition set | `vinu-agent` | C | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| Refactor TradingMandate checks into an independent, always-invoked checkpoint outside the agent loop | `vinu-agent` | C | NautilusTrader → `../comprison-other-vinu/03-nautilus_trader.md` § Adopt |
| Hash-chained, fsynced, append-only audit ledger for kill-switch/halt/emergency-flatten events | `vinu-agent` | A | Vibe-Trading → `../comprison-other-vinu/14-vibe-trading.md` § Adopt (`governance/ledger.py`) |
| `fix_nonpositive_semidefinite` (spectral) — harden the correlation matrix ⭐ highest-priority quick win, directly reduces the bug class already found once this session in the runtime correlation monitor | `vinu-portfolio` | A | PyPortfolioOpt → `../comprison-other-vinu/11-pyportfolioopt.md` § Adopt |
| Ledoit-Wolf shrinkage covariance to replace/augment the raw sample correlation matrix | `vinu-portfolio` | A | PyPortfolioOpt → `../comprison-other-vinu/11-pyportfolioopt.md` § Adopt |
| `SizeType.TargetPercent`/`TargetValue`-style order-delta resolution for the rebalancer | `vinu-portfolio` | A | VectorBT → `../comprison-other-vinu/09-vectorbt.md` § Adopt |
| Portfolio/sector concentration bucket-penalty pattern (graduated, not binary) | `vinu-portfolio` | A | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| Transaction-cost-aware objective term in the rebalancing objective | `vinu-portfolio` | A | PyPortfolioOpt → `../comprison-other-vinu/11-pyportfolioopt.md` § Adopt |
| HRP as a backstop when the correlation matrix is ill-conditioned | `vinu-portfolio` | C | PyPortfolioOpt → `../comprison-other-vinu/11-pyportfolioopt.md` § Adopt |
| Risk-management-as-target-rescaling stage — operate on the full proposed target set post-construction | `vinu-portfolio` | C | Lean → `../comprison-other-vinu/05-lean.md` § Adopt |

Three `vinu-live`-targeted items also belong conceptually here (portfolio-wide/instrument-wide risk state, not per-order):

| Item | Target | Bucket | Source |
|---|---|---|---|
| Override taxonomy (untradeable/reduce_only/ignored per symbol, with reasons + precedence resolution) | `vinu-live` | C | pysystemtrade → `../comprison-other-vinu/12-pysystemtrade.md` § Adopt (`diagOverrides`) |
| Covariance-over-time cold-start fallback (zero-correlation matrix when a new symbol has no history yet) | `vinu-live` | A | pysystemtrade → `../comprison-other-vinu/12-pysystemtrade.md` § Adopt |
| Realized-slippage-from-planned-price tracker for fill/reconciliation monitoring | `vinu-live` | A | StockSharp → `../comprison-other-vinu/10-stocksharp.md` § Adopt |

## 7. Promotion / Validation Rigor

The axis where **Vina is already strongest** relative to everything audited — this is exactly what `vinu-research`'s deflated-Sharpe + holdout + stress-test gate does, and almost nothing else in this list has a real equivalent.

- **abu** — the closest match: grid search combined with correlation-aware cross-validation (builds CV folds from similarity clustering, not random symbol splits) specifically targets the same overfitting risk deflated-Sharpe/holdout testing is meant to catch.
- **VectorBT** — implements the Deflated Sharpe Ratio itself (López de Prado's multiple-testing correction, explicit `nb_trials` parameter) — a reference formula worth cross-checking Vina's own implementation against.
- **Qlib, FinRL** — both produce rich validation *metrics* (IC/ICIR/Rank IC via Qlib's recorder; validation-Sharpe-based model selection in FinRL's ensemble), but neither was confirmed to have a hard, enforced gate blocking promotion the way Vina's does — they measure quality, they don't necessarily refuse to deploy on a bad score.
- **Freqtrade, NautilusTrader, Lean, Hummingbot, StockSharp, pysystemtrade, daily_stock_analysis, FinceptTerminal, PyPortfolioOpt** — none has anything resembling a statistical anti-overfitting gate before a strategy goes live. A strategy is live the moment a user configures/approves it.
- **Vibe-Trading** — its strategy-discovery layer gates *recommendations* on evidence sufficiency (explicitly refuses to present insufficient evidence as a recommendation) but this is evidence-presence checking, not overfitting-correction statistics — no deflated-Sharpe/holdout/stress-test equivalent found.

**Adoptable items grouped here** (from `adoption-tracker.md`'s `vinu-research` section, excluding the LLM-degradation item already placed under §3):

| Item | Target | Bucket | Source |
|---|---|---|---|
| Correlation-clustered CV folds — don't let correlated symbols span train/test in holdout testing | `vinu-research` | A | abu → `../comprison-other-vinu/07-abu.md` § Adopt |
| Cross-check the existing deflated-Sharpe gate against VectorBT's explicit `nb_trials` reference formula | `vinu-research` | A | VectorBT → `../comprison-other-vinu/09-vectorbt.md` § Adopt |
| Recorder pattern — persist IC-like signal-quality metrics alongside every promotion run's pass/fail verdict | `vinu-research` | A | Qlib → `../comprison-other-vinu/02-qlib.md` § Adopt |
| Point-in-time/lookahead-leakage screening as an explicitly named gate stage | `vinu-research` | A | awesome-quant (catalog pointer, `pit-release-gate`) (idea only — awesome-quant repo removed from disk, and the consolidated findings doc it was cited from no longer exists either; this note is the only surviving record) |
| Data-derived regime labeling (drawdown/run-up/slope-based) as an additional automatic stress-test dimension | `vinu-research` | C | TradeMaster (repo removed from disk — idea only, see `../repo-list.md` cut-repos table) |
| Mandatory ≥1 invalidation-condition-per-thesis schema check (with evidence freshness/quality tagging) | `vinu-live` (research-artifact schema) | A | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| Ump-style GMM outcome-cluster veto as an additional statistical pre-trade gate | `vinu-live`/`vinu-agent` | C | abu → `../comprison-other-vinu/07-abu.md` § Adopt |

Not in the tracker, but the most important item in this bucket: the `meets_promotion_bar()` wiring gap found by tracing Vina's own code (see `vinu-lifecycle-story.md`) — the designed AND-of-five gate isn't the one that actually runs. Fixing that is higher priority than any item above.

## 8. Execution / Fill Realism

Distinct from "has live trading" — this is specifically about modeling *how realistically* an order fills (slippage, market impact, partial fills, reject probability).

- **Lean** — the deepest: per-security-type pluggable `FillModel`/`SlippageModel`/`FeeModel`, plus execution-layer algos (VWAP/StdDev/Spread-based order slicing) distinct from the fill model itself.
- **StockSharp** — realized-slippage-from-planned-price tracking (measures actual vs. intended fill quality) plus iceberg/TWAP/VWAP client-side execution algorithms.
- **VectorBT** — numba-JIT order engine with full size/price/fee/slippage/reject-probability validation and typed rejection reasons.
- **Qlib, NautilusTrader, pysystemtrade, abu, Freqtrade** — each has a real, distinct fill-realism mechanism (volume-capped fills, swappable `FillModel` trait, layered execution-algo hierarchy, gap-down fill rejection guard, worst-case-within-candle stop fills respectively).
- **daily_stock_analysis, PyPortfolioOpt, FinceptTerminal** — no fill-realism modeling; the first two never place orders at all, and FinceptTerminal's audit didn't surface one despite its live trading capability.

**Adoptable items grouped here**: identical to §1's table above (same `vinu-simulator` tracker items — this section is the live-fill-quality framing of the same work, §1 is the backtest-honesty framing). Not duplicated here; see §1.

One item is live-side rather than backtest-side and isn't in the tracker at all: `_maybe_enter()` never passes bracket-order params to the broker even though `AlpacaBroker.submit_order()` supports them, so contingency-rule stops only live in vinu-live's book, not as a real resting order — found by tracing Vina's own code (`vinu-lifecycle-story.md`), not from another repo. Worth fixing alongside whichever `vinu-simulator` items get picked up, since both are "is the fill/protection actually what it claims to be" issues.

---

## Tracker items that don't map to any of the 8 capabilities

Worth stating explicitly rather than silently dropping — the 8 capabilities describe *trading system* concerns; these 5 tracker items are operational/infrastructure concerns that sit outside that frame entirely:

| Item | Target | Bucket | Source |
|---|---|---|---|
| Atomic write + optimistic version token for the runtime-settings admin API | `vinu-infra` | A | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| Field-metadata-as-single-source-of-truth config registry | `vinu-infra` | C | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| Notification dedup + cooldown + quiet-hours + severity + in-flight reservation | Telegram/Discord notify paths | A | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt (`notification_noise.py`) |
| Per-notification-type channel routing | Telegram/Discord notify paths | A | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |
| Per-delivery-attempt audit trail | Telegram/Discord notify paths | A | daily_stock_analysis → `../comprison-other-vinu/04-daily_stock_analysis.md` § Adopt |

The notification gap is confirmed, not hypothetical: `vinu-lifecycle-story.md`'s trace found no dedup/cooldown module anywhere, and the same trace found multiple alert-firing paths (kill-switch, halt, OOD) that could plausibly duplicate-fire with nothing currently stopping it.

---

## What this tells us about Vina's actual position

Cross-referencing all 8 capabilities against Vina: Vina is **live trading + broker (Alpaca) + LLM capability**, with real (if not yet fully formalized) **risk/portfolio management** and genuinely strong **promotion/validation rigor** — but **no screener yet**, and **execution/fill realism** limited to the Almgren-Chriss model already in `vinu-simulator`.

Only **FinceptTerminal** sits in the original five buckets simultaneously (backtesting, live trading, LLM, screener, broker) — every other repo is missing at least one. But adding the three new columns changes the picture: **no single repo excels at all eight**. FinceptTerminal has broad *category* coverage but weak promotion rigor and unconfirmed fill realism; abu and pysystemtrade have deep risk/validation rigor but no LLM, no screener, and abu has no live trading at all. Vina's actual differentiator, once `vinu-screener` lands, would be a combination nothing else audited has: **LLM-assisted research → a real statistical promotion gate → live broker execution with a hardened risk stack → a rule-based screener feeding it** — each piece individually matched by 1-2 other repos, but no single repo combining all of them the way Vina's roadmap does.
