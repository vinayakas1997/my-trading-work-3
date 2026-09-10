# What Vina Gains — Capability-Forward Projection

The lifecycle story asked, at each point in Vina's real flow, "what do the other repos do here" — flow-forward. This does the reverse: for each of the 8 capability buckets in `global-repo-comparison-by-8-capability.md`, if the adoption-tracker items in that bucket get implemented, **what new power does Vina actually get, and what would it end up excelling at** — grounded in the specific items already cataloged, not aspirational language.

---

## 1. Backtesting — from "looked good" to "honestly simulated"

**Today**: `vinu-simulator` has an Almgren-Chriss execution model. The lifecycle trace found `vinu-simulator` untouched by anything in the adoption-tracker so far — none of its 7 tracker items are implemented yet.

**What implementing them unlocks**: worst-case-within-candle fills (Freqtrade), volume-capped partial fills (Qlib), a gap-down rejection guard (abu), random reject-probability (VectorBT), and a liquidity-exceeded circuit breaker together mean a backtest can no longer silently assume a strategy could execute at a size or speed the real market wouldn't have allowed. Right now a strategy could clear the promotion gate on an unrealistically generous fill assumption and only have that surface later, live, as the exact kind of backtest-vs-paper Sharpe degradation `ShadowEvaluator` already watches for — after real capital risk, not before.

**What Vina would excel at**: catching a bad backtest *before* promotion instead of *after* shadow-trading degradation. This directly strengthens `vinu-research`'s gate rather than sitting next to it — a strategy that only worked because the simulator was too generous would fail the deflated-Sharpe/holdout check honestly, instead of passing on paper and degrading in the ShadowEvaluator weeks later.

## 2. Live Trading — from "executes correctly" to "executes at scale without degrading"

**Today**: Vina already has a full live path with a real guard chain (14 checks), bracket-order support in the broker client, and idempotent submission. This is a strength, not a gap.

**What implementing the remaining items unlocks**: `TripleBarrierConfig`-style bundling (stop/target/time/trailing as one object, volatility-scaled) replaces scattered per-rule contingency logic with one coherent, reusable barrier set per position. Iceberg/TWAP slicing (StockSharp) means a larger order doesn't have to go out as one clumsy market order. Executor-as-state-machine (Hummingbot) gives each concurrent open position its own independently auditable lifecycle instead of one big orchestrator loop reasoning about all of them at once.

**What Vina would excel at**: handling *more capital and more simultaneous positions* without execution quality degrading — right now the system is correct at a modest scale; these items are what let it stay correct as position count and order size grow.

## 3. LLM Capabilities — from "the differentiator" to "the resilient differentiator"

**Today**: only 2 of 13 repos audited (daily_stock_analysis, FinceptTerminal) have real LLM integration at all — this is already a genuine moat, not a catch-up area.

**What implementing the one relevant item unlocks**: DSA's graceful LLM-backend degradation chain (primary model → validated fallback models → deterministic non-LLM fallback, with the failure reason surfaced in the result) means an LLM outage or a bad/malformed response degrades the research pipeline instead of halting it silently or producing garbage.

**What Vina would excel at**: this isn't a new capability, it's protecting the existing one. Vina's edge over every non-LLM repo (11 of 13) only holds if the LLM path is actually reliable in production — this closes the one operational risk to that edge that the audit specifically surfaced.

## 4. Screener/Scanner — the one genuinely new capability

**Today**: doesn't exist. Confirmed by the lifecycle trace — no `vinu-screener` package, and its natural position (feeding `ResearchService._propose_idea()`) is architecturally clear but unbuilt.

**What implementing the 20-item Bucket B unlocks**: the ability to discover trade candidates across the full ~8000-symbol US equity universe on a schedule, instead of only researching tickers a human already thought to name. This changes the shape of entry point #1 in the lifecycle story from "user/LLM proposes one idea" to "system continuously surfaces a ranked shortlist, user/LLM picks from it."

**What Vina would excel at**: this is the one place Vina can end up ahead of *every* repo audited, not just catching up. Only daily_stock_analysis and FinceptTerminal have a comparable scanner, and **neither has a statistical promotion gate on top of it** — DSA's gate is an LLM-rerank + risk-penalty score, not a deflated-Sharpe/holdout/stress-test bar; FinceptTerminal's scanner is alert-only with no validation layer at all. A Vina screener feeding an already-existing, rigorous promotion gate would be a combination none of the 13 repos actually has.

## 5. Broker Integration — deliberately not expanding

**Today**: Alpaca-only, US equities only, by design.

**What's in the tracker**: nothing actionable — the only broker-breadth pattern noted (vn.py's gateway abstraction) belongs to a repo that was cut from the kept set specifically because this capability isn't needed.

**What Vina would excel at**: staying narrow on purpose. Worth stating explicitly rather than leaving unaddressed — the "gap" here is not a gap, it's a scope boundary, and every hour not spent on multi-broker abstraction is an hour spent hardening the one broker path that actually matters.

## 6. Risk/Portfolio Management — from "has guards" to "has an auditable risk control plane"

**Today**: `OrderGuard`'s 14-check chain works and is well-tested, but it's one long inline method — not independently inspectable, not live-editable per-rule, and (per the lifecycle trace) has at least one side-effect exemption (concentration check being buy-only) that may not be deliberate.

**What implementing this bucket unlocks** — the largest cluster of tracker items (`vinu-agent` + `vinu-portfolio` combined, ~19 items): StockSharp's rule-object + action-enum decoupling turns each mandate limit into an independently testable, Save/Load-able unit. pysystemtrade's min-of-4-multipliers pattern replaces binary reject/allow with a smoothly-scaling response. pysystemtrade's persisted trade-limit objects and Override taxonomy make every risk decision queryable and reasoned, not just enforced. PyPortfolioOpt's PSD-repair and Ledoit-Wolf shrinkage make the correlation matrix feeding the concentration checks and the runtime correlation monitor statistically trustworthy instead of noisy.

**What Vina would excel at**: this is the bucket that closes the gap with the three most institutionally mature repos audited (pysystemtrade — Carver's actual live capital system; StockSharp — full serializable risk-rule DSL; NautilusTrader — Rust risk engine with live-mutable, audited limits). Implementing it moves Vina from "has risk limits that work" to "has a risk control plane a real operator could audit line by line, mid-incident, and understand exactly why any specific action fired."

## 7. Promotion/Validation Rigor — Vina's strongest axis, made honest

**Today**: per the capability matrix, this is already the one area where Vina leads almost everything audited — deflated Sharpe, holdout, stress test, PBO all exist. But the lifecycle trace found the actual gate that *runs* is a weaker OR-of-two, not the designed AND-of-five (`meets_promotion_bar()` isn't wired in).

**What implementing the remaining tracker items unlocks**: fixing the wiring gap alone would make the existing design actually enforce itself. On top of that: correlation-aware CV folds (abu) stop correlated symbols from leaking signal across train/test; cross-checking the deflated-Sharpe formula against VectorBT's explicit `nb_trials` reference catches a subtle but easy-to-get-wrong multiple-testing correction; Qlib's recorder pattern makes every promotion decision an auditable artifact with its supporting IC/Sharpe metrics, not just a boolean; point-in-time/lookahead-leakage screening adds a named gate for a failure mode currently not explicitly checked.

**What Vina would excel at**: not "catching up" — extending a lead. Only abu (correlation-aware CV) and VectorBT (explicit deflated Sharpe) come close to what Vina already has designed; none of the 13 repos has PBO, stress-test-window backtesting, and a holdout carve-out all in one gate the way Vina's is *supposed* to work. Wiring the bug fix makes that lead real instead of aspirational.

## 8. Execution/Fill Realism — closing the backtest-to-live gap on both ends

**Today**: this bucket overlaps with #1 (backtest side) but also has a live-side finding from the lifecycle trace: `_maybe_enter()` never passes bracket-order params to the broker, so contingency-rule stops only live in vinu-live's own book, not as a real resting order.

**What implementing this unlocks**: on the live side, using the broker's bracket-order support (already present in `AlpacaBroker.submit_order()`, just unused at entry) means an open position stays protected even if vinu-live's process goes down — closing a real operational risk, not a backtest nicety. On the backtest side, StockSharp's realized-slippage-from-planned-price tracker gives a post-hoc measurement of *actual* execution quality vs. what was intended, independent of the pre-trade Almgren-Chriss cost model — a feedback signal currently missing entirely.

**What Vina would excel at**: closing the loop between "what the backtest promised," "what the live broker actually did," and "did those two match" — right now only the *first* two of those three are measured (via `ShadowEvaluator`'s Sharpe-degradation check); this bucket adds the missing piece of *why* they diverged, order by order, not just in aggregate.

---

## Summary — where the real payoff concentrates

Ranked by how much new capability (not just polish) implementing each bucket would actually add:

1. **Screener/Scanner** — the only bucket that's a genuinely new capability from zero, and the one place Vina could end up with a combination (screener + real promotion gate) none of the 13 repos has.
2. **Risk/Portfolio Management** — the largest bucket, and the one that moves Vina from "works" to "auditable," closing the gap with the three most production-hardened repos audited.
3. **Execution/Fill Realism** — smaller in item count, but contains a live-trading risk (non-resting stops) that matters more than its bucket size suggests.
4. **Promotion/Validation Rigor** — already Vina's strongest axis; the payoff here is making an existing lead real (fix the wiring bug) rather than building something new.
5. **Backtesting** — currently the most neglected bucket (0 of 7 items implemented); its main value is upstream of #4, making the gate it feeds more trustworthy.
6. **Live Trading** — a scale/robustness multiplier on an already-working system, not a new capability.
7. **LLM Capabilities** — protects an existing moat against one specific operational risk.
8. **Broker Integration** — deliberately not pursued; correctly out of scope.
