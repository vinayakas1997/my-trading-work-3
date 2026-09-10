# The Vina Trade Lifecycle — The Real Story

This traces what Vina's own code *actually does*, end to end — not a design doc, a fact-finding pass with file:line citations (full trace saved in this session; every claim below is grounded in real code). The story is the skeleton. At each stage: **what Vina does today** → **native gaps found** (real issues in Vina's own code, found independent of any other-repo comparison) → **what the 13 audited repos do at this same point** (pulled from `adoption-tracker.md`). A final section catches capabilities that don't map onto this story at all — the safeguard against only thinking from Vina's own perspective.

---

## Entry Points — how does a trade idea originate?

Vina has **five** distinct entry points, not one clean pipeline. That's the first thing worth internalizing before anything else.

### 1. LLM research → strategy artifact → promotion gate

`ResearchService.run_research()` proposes an idea (LLM-generated from "angle context," or a templated fallback), runs `StrategyResearchLoop` (iterative filter/backtest/refine), carves out a true holdout slice never seen during refinement, runs a stress test against configured crisis windows, computes a deflated Sharpe ratio (`n_trials` counted cumulatively per symbol — this is the multiple-testing correction VectorBT also implements), and computes PBO (probability of backtest overfitting).

**Native gap found**: `meets_promotion_bar()` — the function that's *supposed* to be the single AND-of-all-gates promotion check (deflated Sharpe threshold, holdout required, stress-test required, PBO ≤ 0.7, correlation eligibility) — is fully implemented but **has no call site wiring it into `run_research`**. The actual gating logic that runs is `validated = holdout.passed OR stress_test.passed` — an OR of two checks, not the full AND-of-five the promotion-bar function encodes. This means the documented, designed promotion bar and the promotion bar that actually executes are two different things.

**What other repos do here**: abu's correlation-aware CV-fold construction (don't let correlated symbols span train/test) and VectorBT's explicit `nb_trials`-parameterized deflated Sharpe are both listed in the tracker as items to cross-check against `vinu-research`'s gate — this dead-code finding makes that cross-check more urgent, not less: fix the wiring bug first, then verify the formula against VectorBT's reference implementation.

### 2. Two independent, unreconciled BENCHING→ACTIVE paths

Vina's own code docstring (`ArtifactStatus.PEND`) explicitly states this is a "still-open question": `ShadowEvaluator` in vinu-live promotes BENCHING→ACTIVE directly via HTTP based on paper-trading Sharpe degradation vs. backtest, completely independent of a second path — `capital_allocator_hook.py` → PENDBLOCK/ACTIVE via `mark_active()`/`mark_pendblock()`, gated by the kill switch. Two different mechanisms can both promote the same artifact type, and the code itself flags that reconciling them hasn't been done.

**What other repos do here**: this is a case where the fix isn't "adopt a feature," it's "pick one path or formally merge them." Qlib's Recorder pattern (persist every promotion decision as an artifact with its supporting metrics) would at least make it visible *which* path promoted a given artifact and why — worth adopting regardless of which path wins.

### 3. Trade-plan authoring/approval — an orphaned code path

`author_trade_plan()` → `freeze_trade_plan()` → `approve_trade_plan()` is a fully built pipeline (forecast, risk bands, contingency rules, invalidation conditions, gated by a `CalibrationGate`) with real HTTP routes. But **nothing in the codebase calls it** — no scheduler, no vinu-agent tool, no CLI command. Meanwhile, `TradePlanOrchestrator.cycle()` — vinu-live's entire automated trading loop — only ever acts on ACTIVE `type="trade_plan"` artifacts. If nothing authors and approves a trade plan, **the entire automated trading loop may currently have nothing to act on**, unless this is triggered manually/externally in a way not present in this codebase.

This is the single most important finding of the whole trace. Worth confirming directly with whoever knows the deployment: is this triggered by something outside the repo, or is it genuinely dead?

### 4. Manual trade tool (`submit_order`) — bypasses research, not guards

A user or the ReAct agent can call `submit_order` directly with a raw symbol/qty/side — no reference to any research artifact. But it still runs through the **full** `OrderGuard` chain, including `require_active_artifact` (default True), so a bare manual order is actually blocked unless the symbol already has an ACTIVE strategy artifact — the guard chain, not the research pipeline, is what actually gates this path. `require_confirmation` (default True) adds a human-in-the-loop step before live execution.

**What other repos do here**: FinceptTerminal's `DeploymentRunner` also gates live orders on human approval as a *separate concern* from its scanner — validates that Vina's confirmation-gate pattern here is a reasonable, independently-arrived-at design, not a gap.

### 5. Rebalance intake (`submit_rebalance_request`)

A request-only queue — the module docstring is explicit: "the rebalancer can only request, never act directly." Consumed only when a position's own invalidation/contingency rules found nothing to trigger that cycle, always `.consume()`d whether honored or not, declined if unrealized gain > 5% unless marked `critical`.

**What other repos do here**: pysystemtrade's Override taxonomy (typed, precedence-resolved per-instrument states) is a more general version of the same idea — worth considering once/if rebalance requests need more nuance than accept/decline.

### Cycles, HTTP triggers, and shock batches also feed entries

`vinu-live-worker`, `trade-plan-worker` (every 300s), `feedback-worker`, `shadow-worker` all run unconditionally on boot. A separate shock-event/shock-batch path reprioritizes symbols by a shock-correlation score before the main loop runs.

### `vinu-screener` doesn't exist yet — and its natural position is upstream of entry point #1, not a new order-placement path

No `vinu-screener` package exists. There *is* a read-only `teams/screener` LLM team inside vinu-agent today (synthesizes vinu-initial-analysis's 28 angles per watchlist symbol, `tools: []`), which is a different, narrower thing. The trace confirms the planned `vinu-screener` conceptually belongs **feeding `ResearchService._propose_idea()`** as a richer source of candidates — not touching `OrderGuard`, `TradeTool`, or the book at all. This matches the architecture principle both FinceptTerminal and daily_stock_analysis independently arrived at (screener stays decoupled from the order/research pipeline until a symbol is explicitly selected) — Vina's planned design is already aligned with the two best references audited.

---

## The Middle — idea approved → order sits in the book

### Sizing and correlation (vinu-portfolio)

Correlation matrix (Pearson + DCC shock correlation), concentration flagging, vol-targeted position sizing capped by max leverage. vinu-live's own entry sizing is separate and simpler — plan-authored `size_pct` scaled by forecast confidence and vol targeting.

**Native note**: two separate sizing computations exist (vinu-portfolio's vol-targeting, vinu-live's plan-based sizing) with no confirmed reconciliation between them — worth checking whether they're meant to agree or serve genuinely different purposes.

**What other repos do here**: PyPortfolioOpt's `fix_nonpositive_semidefinite` and Ledoit-Wolf shrinkage directly harden the correlation-matrix computation this stage depends on — still the single highest-priority Bucket-A item in the tracker, and this trace confirms exactly where it plugs in (`vinu-portfolio`'s `compute_correlation_matrix`). VectorBT's `TargetPercent`/`TargetValue` order-delta resolution is a cleaner algorithm than hand-rolling the weight→order-size conversion.

### OrderGuard — 14 checks, in order, every order passes through

Kill switch → throttle (10/sec) → blocked/allowed tickers → short-selling permission → max order value → daily orders per-symbol → daily orders portfolio-wide → max position pct → max capital utilization → active-artifact requirement → market-hours → symbol/correlation concentration → risk-budget TIER_HALT → daily trade volume cap. `pre_approve()` re-runs the whole chain a second time immediately before broker submission, inside the kill-switch lock, closing a check-then-act race.

**Confirmed reduce_only exemptions** (verified, not assumed): kill switch (when `HALT_POLICY=entries_only`), portfolio-wide daily order cap, risk-budget TIER_HALT. **Not exempt**: max order value, daily orders per-symbol, max position pct, max capital utilization, daily trade volume — these apply to every order regardless of reduce_only. Symbol/pairwise-correlation concentration is **buy-only by construction**, which incidentally exempts all sells including reduce_only ones — this is a side effect of the check's design, not a deliberate reduce_only exemption, worth confirming is intentional.

**What other repos do here**: StockSharp's rule-object + action-enum decoupling and pysystemtrade's persisted, queryable trade-limit objects are both listed in the tracker as ways to make this 14-check chain independently inspectable/auditable/live-editable per-rule, rather than one long inline `check()` method. NautilusTrader's `set_max_notional_per_order()` + emitted audit event is the closest match to what the runtime-settings admin API should grow into for these specific limits.

### Broker submission

All external callers — including vinu-live's own automated exits — route through one HTTP front door (`POST /agent/broker/order`), explicitly documented as reusing the exact same guard chain as the LLM's tool, "not a shortcut around them." `AlpacaBroker.submit_order()` supports real bracket orders (`take_profit_price`+`stop_loss_price` → `order_class="bracket"`) and `client_order_id` idempotency. Fill confirmation polls broker positions up to N times, comparing observed qty change against intended, tolerant of genuine partial fills; fails open (never blocks) on an unreadable broker snapshot.

**Native gap found**: `_maybe_enter()` — the function that opens a new position from a trade plan — does **not** pass `stop_loss_price`/`take_profit_price` to the broker, even though `AlpacaBroker.submit_order()` supports real bracket orders. This means contingency-rule stops (`tighten_stop`) only ever update a `stop_loss` field inside vinu-live's own book — **not** a real resting order at the broker. If vinu-live's process is down when price hits that level, nothing protects the position; only `TradeTool`'s separate manual path actually uses broker-native brackets.

**What other repos do here**: this is exactly the class of gap Lean's per-security-type `FillModel`, StockSharp's iceberg/TWAP execution algorithms, and Hummingbot's `TripleBarrierConfig` (which explicitly bundles stop/target/trailing into one object checked every tick, independent of whether it's also resting at the broker) all address from different angles. The concrete fix worth considering: either pass bracket params on entry so the broker itself enforces the stop, or explicitly document that vinu-live's book-tracked stop is deliberately soft (evaluated every 300s, not broker-instant) and accept the gap as a known trade-off.

### Book tracking

Fill confirmed → `open_position()` inserts using the **actually-filled** qty, not the intended qty — a deliberate, correct design choice already in place.

---

## Exit Points — every way a position can close

Checked in this order per cycle, first match wins: **time-stop → invalidation conditions → contingency rules → rebalance request → trailing-stop ratchet → 1R bracket partial**. All of these are dynamic/per-plan, not fixed numeric TP/SL — authored once at plan-freeze time from live risk state, then mechanically re-evaluated every cycle (default 300s).

Separately and independently: **runtime correlation monitor** (reduce_only trim of correlated pairs — the bug fixed this session was exactly the `None`-vs-`0.0` cooldown sentinel, now documented in-line in the code), **OOD emergency-flatten detector** (3 fail-open stress signals, needs ≥2 to fire, acts at most once per process lifetime), **halt policy** (entries_only exempts exits; "all" blocks everything, documented as debug rollback), **cooldown-after-losses** (never blocks exits, only entries), **emergency flatten/resume** (manual panic switch — resolves against the *live broker holding*, never over-asks or flips a position), and **book↔broker reconciliation**.

**Native gap found**: **manual close has no dedicated tool.** The only path is calling `submit_order` with a closing side — which runs the full guard chain, but does **not** touch vinu-live's book at all. A manual close via the trade tool creates drift that only gets caught (and only *partially* auto-corrected — see below) on the next reconciliation cycle.

**Native finding, not a gap**: reconciliation is more nuanced than "detects drift" — it genuinely auto-corrects the *safe* cases (broker flat → close stale book position; broker qty < book qty → reduce to match; broker qty > book qty within a sanity ratio → increase to match), but is alert-only, never-auto-acts for the two dangerous cases: a phantom broker position with nothing in the book, and book/broker holding opposite sides. This is a genuinely well-reasoned design already — worth documenting explicitly as intentional rather than assuming it's incomplete.

**What other repos do here**: StockSharp's `RiskActions` enum (ClosePositions/StopTrading/CancelOrders, decoupled from the triggering rule) and pysystemtrade's Override taxonomy (per-symbol untradeable/reduce_only/ignored, with reasons and precedence) both map onto formalizing "manual close" as a first-class, book-aware action instead of a side-effect of the generic order tool. Lean's `TrailingStopRiskManagementModel` peak-tracking pattern is close to what Vina's trailing-stop ratchet already does — worth a direct side-by-side comparison rather than adoption, since Vina's version may already be equivalent.

### Kill switch vs. halt policy — one shared mechanism, one separate local breaker

Confirmed: there is genuinely **one** filesystem-backed kill switch (OS-level `flock`-protected), read by both `OrderGuard.check()` and vinu-live's own halt check — not two independent mechanisms as it might appear from the two codebases. `VINU_LIVE_HALT_POLICY` is the single env var governing both the shared switch's reduce_only exemption and vinu-live's own exit-allowance logic. But vinu-live *also* maintains a **second, independent local breaker** (drawdown/daily-loss limits) that is consulted alongside the shared kill switch but not itself exposed through it — two mechanisms, correctly distinguished in the trace, worth keeping distinguished going forward rather than assuming they're the same thing.

---

## What doesn't map onto this story at all

Capabilities other repos have that don't correspond to any node above — the check against only thinking from Vina's own current shape:

- **A dedicated, formalized universe-scanning entry point** (`vinu-screener` itself) — confirmed above as the one genuinely missing node, not a weak version of something else.
- **A post-construction, full-target-set risk-rescaling stage** (Lean's `IRiskManagementModel` pattern) — Vina's OrderGuard checks one order at a time; nothing currently evaluates the *whole proposed set* of target positions at once the way Lean's Risk Management stage does, which is exactly the kind of check that would catch a multi-order sector-concentration breach that no single order trips.
- **A learned, outcome-informed veto layer** (abu's Ump/GMM-cluster veto) — Vina's gates are all rule-based/statistical-on-artifacts; nothing learns from realized *trade* outcomes to veto a specific instance of an otherwise-approved strategy.
- **A formal execution-algorithm layer** (iceberg/TWAP/VWAP order slicing from StockSharp/pysystemtrade) — Vina's orders appear to go out as single whole orders; there's no large-order-slicing mechanism anywhere in the trace.
- **A notification noise-control layer** — confirmed absent in the trace (no dedup/cooldown/quiet-hours module found anywhere); daily_stock_analysis's `notification_noise.py` remains the clearest reference, and this gap is real: the kill-switch/halt/OOD-alert paths found in this trace could plausibly fire repeated duplicate notifications with nothing currently stopping that.
- **A config-field metadata registry** — the new runtime-settings API (confirmed in the trace, `RuntimeSettings` + `POST /live/admin/settings`) is real and working, but is still the bare whitelisted-numeric-knob shape, not daily_stock_analysis's fuller field-metadata/validation/atomic-optimistic-concurrency version.

---

## What this means for sequencing

Three of the native gaps found here are more urgent than anything in the adoption-tracker, because they're not "missing a nice-to-have feature" — they're places where Vina's own documented intent and its actual running code have already diverged:

1. **`meets_promotion_bar()` not wired in** — the promotion gate that runs is weaker (OR) than the one that's designed and tested (AND-of-five).
2. **Trade-plan authoring/approval has no caller** — if true in the deployed system, the automated trading loop has nothing to act on.
3. **Stops aren't broker-resting** — a process outage leaves open positions with no real protective order at the broker.

Recommend confirming/fixing these three before pulling in anything from the adoption-tracker — they're cheaper to fix than most Bucket-A items, and they affect whether the rest of the system is actually running as designed.
