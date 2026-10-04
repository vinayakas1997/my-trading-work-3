# How does the system get ready for what comes next?

Vision: *"regime-first; WAIT-first; right to say 'I don't know'; event-driven → suspend; risk little when uncertain; learn which regimes the edge holds in"* (`../vision-trding-system.md` A1, A5, A6, A18). Four kinds of "next": the market changes character, the system does not know enough, a known risky event is coming, or a strategy stops working. Each answer says what is on by default and what needs a flag (`../the-inconsistencies-v2/06-live-behavior-flags.md`).

---

## Q1. The market changes character. What notices, and what changes?

**Verdict: WORKS, WITH A LIMIT, and one deployment fault FIXED (F5).**

| What reads the regime | Effect | On a fresh install? |
|---|---|---|
| **Portfolio tilt** (`PortfolioService._regime_alignment_multiplier`) | a strategy whose tag matches the regime gets `1 + 0.3`, one that does not gets `1 − 0.3`; `high_vol` or an unknown regime = no tilt | tags **yes after F5** (see below); reaches orders only with `scheduler_use_daily_allocation` (**off**) |
| **Per-symbol risk band** (`risk_budget.REGIME_SIZING_MULTIPLIERS`, order guard) | bull 1.0, sideways 0.9, bear 0.8, high_vol 0.6, multiplies the tier size cut | **on** |
| **Backtest sizer** (`RegimeAwareSizer`) | same idea inside simulations | on in research |
| **Evidence tagging** (`signal_evidence`) | every recorded trigger carries the regime it fired in, so later analysis can ask "does this edge hold in bear markets?" | on |

**Worked example** (`vinu-portfolio/tests/test_logic_allocation_by_hand.py`, passes against the real service). Two strategies, equal volatility, base 0.5 / 0.5; regime **bull**; A tagged `trending`, accuracy 0.8; B tagged `ranging`, untracked.

| | regime × | outcome × | tilted | normalised |
|---|---|---|---|---|
| A | 1.3 | 1 + 0.3·(2·0.8 − 1) = 1.18 | 0.5·1.3·1.18 = 0.767 | **0.6867** |
| B | 0.7 | 1.0 | 0.5·0.7·1.0 = 0.35 | **0.3133** |

Capital in the same example: equity 100,000, reserve 10% → deployable **90,000** (drawdown `ok`, maturity gating off).

**Deployment fault found and fixed (F5).** The tilt and the sleeve split read `vinu-agent/skills/strategy-tags/tags.yaml` at `/app/vinu-agent/skills/...` inside the container. `portfolio-api` neither copied nor mounted it (only `agent-api` did), and the code's own comment admits the file is "already absent in the running Docker deployment". With the file absent every regime multiplier is 1.0 and every sleeve is `untagged`: the system ran, and the market regime had **no effect on allocation**. Fixed with a read-only mount in `docker-compose.yml`; tests `test_compose_wiring.py` (the mount exists and the default path lands inside it) and `test_without_the_tags_file_the_regime_tilt_is_silently_neutral` (the fault in miniature). Not run in Docker (Docker was not running).

**Limits:** tags exist only for YAML strategies listed in `tags.yaml`; LLM-written strategies get no regime tilt. `bull` and `bear` both favour `trending` (a bear trend is still a trend). Whether 0.3 is the right tilt waits for data.

---

## Q2. The system does not know enough. Does it say so, and what does it do?

**Verdict: WORKS.** Three separate mechanisms, none of which is a hidden gate:

1. **`uncertainty`** (`vinu-infra/uncertainty.py`, in the live-decision context): points per missing or weak input: live snapshot missing 2, evidence unavailable 2, no recorded outcomes 2, input novelty high 2, few outcomes (< 20) 1, maturity not `mature` 1, precondition untested 1, strategy config missing 1. Levels: 0-1 low, 2-3 medium, 4+ high. It also lists `missing_inputs`, so "I don't know because the input was missing" differs from "I looked and I am neutral".

   | Situation | Points | Level |
   |---|---|---|
   | everything present, nothing wrong | 0 | low |
   | novelty high (ratio 2.6) **and** no recorded outcomes | 2 + 2 = 4 | **high** |
   | live snapshot and strategy config both missing | 2 + 1 = 3 | medium |

   The prompt tells the agent: a `high` level, or a missing live snapshot / evidence / config, means say so and **lean to SKIP unless the case is clearly strong**; and "if you truly cannot tell, default to SKIP". Advisory only, never overrides a risk limit. (Verified by running the function on those inputs.)
2. **Input novelty** (`live_decision/novelty.py`, opt-in): how far today's feature vector is from that ticker's own recorded history, as a ratio of nearest-neighbour distances (flag at ≥ 2.0 after 30 reference rows; fewer rows = `insufficient_reference`, which is *unknown*, not novel). Tests: `test_input_novelty.py`.
3. **Fail-open and fail-closed postures**, chosen per call and written next to it: a missing read never invents a number (maturity unknown → "state the tier is unknown"), a fetch failure records `missing` on the connection instead of an empty answer, and the paths that touch capital fail closed (`abort_on_equity_read_failure`, the order guard's `no_equity` reject).

**Limit worth knowing:** the `no_recorded_outcomes` input is symbol-wide, not specific to the strategy's own condition (**D4**), and outcomes only exist for live triggers after F4. Until paper data arrives, expect `medium`/`high` almost everywhere: that is the "child" working as intended.

**Waits for data:** whether the point values and the 20-outcome floor separate good from bad setups.

---

## Q3. A known risky event is coming (earnings, macro) or liquidity is thin.

**Verdict: WORKS (both execution paths).**

* **Event blackout** (`trade_plan/guards.event_blackout_reason`): vinu-stock-price keeps a local earnings + US-macro (FOMC, CPI, NFP, PCE) calendar; an entry is skipped when the symbol has an event within 24 hours (`VINU_LIVE_EVENT_BLACKOUT_HOURS`). **Entries only**; open positions keep their own exits. Fails open when the calendar is unavailable.
* **Spread gate:** a slice is skipped when the quote spread exceeds 25 bps (`VINU_LIVE_MAX_SPREAD_BPS`), tightened further by a per-order slippage budget.
* Both run in the hourly scheduler **on every slice, by default** (`scheduler.py` ~1150-1180) and in the trade-plan orchestrator. A risk-reducing slice is exempt **only when `scheduler_exits_exempt_from_halts` is on (default off)**: on a fresh install a closing sell can also be skipped by the spread or earnings gate (see `01`, the halt paragraph). Tests: `test_scheduler.py` (`test_wide_spread_skips_the_slice`, `test_event_blackout_skips_the_slice`).
* Also on entries, opt-in with `scheduler_entry_guards_enabled`: consecutive-loss cooldown, per-symbol loss lockout, stale price data, turbulence pause (14-day realized volatility).

**Dormant, not wired on this path:** the **out-of-distribution flatten** (`VINU_LIVE_OOD_DETECTOR`, default `off`) exists only in the trade-plan orchestrator, not in the scheduler, which is the path the live-decision loop uses. The news-impact and threat classification still feeds nothing (decision D1 from the routing work).

**Waits for data:** whether 24 h and 25 bps are the right thresholds.

---

## Q4. A strategy stops working, or the idea pool runs dry.

**Verdict: FIXED (decay, see `01` Q2), WORKS (renewal).**

* **Decay → demotion → replacement.** Re-validation now feeds the decay scan (F1) and a losing strategy can no longer read healthy (F2); a `DECAYED` strategy leaves the book and triggers re-research for its symbol (`cli._trigger_re_research`). Speed is decision **D1**.
* **New candidates:** the screener ranking feeds the planner-worker's ticker list (screener ∩ bootstrapped, seed list additive), the idea generator drafts three candidates per call, deduplicates against existing hypotheses (TF-IDF then one LLM tie-break), and shows the last evidence for that idea in the prompt; losers are kept in the graveyard so the next idea avoids repeats. K-cap: at most 3 candidates per ticker per week.
* **Trust is earned slowly:** the maturity tier scales capital, limits and prompt caution (`01`/`02`).

---

## Q5. What the system does **not** see when it prepares

Stated so nothing is assumed calm.

| Blind spot | Where | Status |
|---|---|---|
| The reviewing agent is told **not** to use unrealized P&L, so HOLD/EXIT judges the thesis, not the loss (the prompt: "no computed ... unrealized P&L ... available to you") | `live_decision_agent/prompt.md` review step 3 | deliberate deferral in the vision (B13), **DECISION D6** below |
| The agent has **no** drawdown or correlation input (prompt step 10 says so and tells it to state "unknown") | live-decision context | deliberate: the deterministic layers act on those regardless of the agent |
| Live-decision orders pass the order guard's `require_active_artifact` (default **true**): a buy for a ticker with no ACTIVE research artifact is rejected (`test_order_guard.py::test_rejects_when_no_active_artifact_for_symbol`) | `broker/order_guard.py` | **DECISION D5** |
| No loss cause for data or model errors | `loss_classifier.py` | gap noted |
| OOD flatten only in the orchestrator | `orchestrator._check_ood` | dormant by design |
