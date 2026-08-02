---
name: the-premarket-agents-questions
status: definition-phase
purpose: the questions a quant PM would ask before letting this agentic system trade premarket/live — grounded in what's actually built vs. dormant vs. missing in vinu-components today, not generic trading platitudes. Answering these is the prerequisite for turning any of this into a skill the agent actually consults.
---

# Pre-Premarket Readiness — The Questions, Not Yet the Answers

This is a checklist of open questions, not a plan and not a status report.
Every question below is anchored to something concrete already found in
this codebase (verified, not assumed) — either a real gate that exists, a
mechanism that's built but dormant, or a genuine hole with nothing behind
it. The goal is: answer these honestly, one at a time, the same way
`live-safety/SKILL.md` was built — read the actual source, don't infer
from a docstring — and the answers become the next skill(s) the agent
consults before acting in a premarket or live session.

**Do not treat "we haven't built X yet" as a reason to skip a question.**
An honest "not built, here's the risk of running without it" is a valid
answer. The point is nobody discovers the gap by watching it fail with
real orders in flight.

---

## 1. Signal & Strategy Validity — is there actually an edge, or a backtest?

- **Has this specific strategy cleared Stage 1's promotion bar** (`vinu_research/promotion.py::meets_promotion_bar` — deflated Sharpe, true out-of-sample holdout, stress test, correlation gate), or is it going live on backtest results alone that never passed the multiple-comparisons-corrected bar?
  *Why:* Stage 1 is the one part of the whole live-safety chain confirmed "real, enforced." Skipping it means trading on a number that could be the best of many random trials, not real skill.
- **Has this strategy ever been checked against real paper-trading performance** before being trusted with the premarket session specifically? (`ShadowEvaluator` exists, does exactly this, and is confirmed dormant — nothing calls it, and the endpoint it needs, `GET /agent/broker/performance/{artifact_id}`, doesn't exist yet.)
  *Why:* Today, an ACTIVE strategy has cleared a statistical bar and nothing else. Premarket is a thinner, gappier, more adversarial regime than regular hours — is backtest-only confidence enough to risk it there first?
- **Does the strategy's entry logic implicitly assume it knows direction from sentiment or novelty?** This session confirmed, twice, on real AAPL/TSLA/JNJ data, that neither rule-based sentiment nor FinBERT sentiment predicts the sign of a price reaction above a coin flip. The `significance_score` classifier predicts *magnitude/surprise*, explicitly not direction.
  *Why:* If a premarket trigger rule reads "high significance_score + positive sentiment = buy," that's using a signal for something it was proven not to do. Confirm the rule doesn't do this before it's live.
- **What's the actual sample size and AUC behind the specific ticker being traded?** AAPL/TSLA sit at 0.85-0.92 AUC on 60+ test positives; JNJ sits at 0.75 AUC on 6 test positives (small-sample, honestly caveated, not a strong result).
  *Why:* "The classifier works" is not one fact — it's a per-ticker fact with very different confidence. A premarket rule shouldn't treat every ticker's score as equally trustworthy.

## 2. Premarket-Specific Conditions — what actually exists for this session type?

- **What premarket data does the agent have access to at all, right now?** (Checked this session: no premarket volume, no premarket gap calculation, no premarket-specific quote handling anywhere in the codebase. This is not a partial gap — it is a zero.)
  *Why:* Before designing a premarket entry rule, confirm the raw data to feed it even exists and is reachable from Alpaca's actual API tier this account has.
- **Has Alpaca's premarket/extended-hours data feed been confirmed reachable and correctly time-stamped for this account**, or is this an assumption? (`vinu-stock-price`'s Alpaca provider has never been checked for extended-hours session tagging in anything reviewed this session.)
- **What premarket condition should actually gate an entry** — a gap size threshold vs. yesterday's close? Premarket volume relative to the ticker's own trailing average? A news catalyst landing within N minutes of the open? Pick one and justify it, don't leave it implicit.
- **How does the system distinguish a premarket gap driven by real news from one driven by thin-liquidity noise?** A handful of premarket trades can move a quoted price a lot without it meaning anything. Is there a minimum-volume floor before a premarket price is trusted as a signal at all?
- **Does the strategy trade the premarket session itself, or wait for the regular-session open print?** These are different liquidity/spread regimes with different risk. This is a decision, not a default — what was chosen and why?

## 3. Risk Management & Loss Adaptation — beyond the one hard stop that exists

- **The -20% portfolio drawdown circuit breaker is real and running by default** (`vinu_portfolio/circuit_breakers.py`, started via `entrypoint.sh`). Is a 20% loss of total equity actually the right threshold to accept before trading is halted, or should premarket specifically have a tighter session-level stop given its higher gap risk?
- **The graduated risk-budget tiers exist as data but nothing reads them** (`risk_budget.py`'s -1%/-2%/-3% tiers are computed on every `GET /portfolio/risk/status` call but never consumed automatically — confirmed by tracing every caller). Who or what is going to own actually reading this and reducing size before the -20% hard stop fires? This needs an explicit owner (a scheduled service, or a skill instruction telling the agent to check it every N minutes) — right now it's a number nobody looks at.
- **Are per-position stop-loss/take-profit bracket orders actually used**, given `AlpacaBroker.submit_order()` already supports them (`stop_loss_price`, `take_profit_price` → real bracket/OTO orders at Alpaca)? Or is every order currently a naked market order with no resting exit?
  *Why:* Premarket gaps can move fast and far before anyone (human or agent) reacts. A resting stop is the only exit that works when nobody's watching in real time.
- **Is the portfolio-concentration check actually enforcing now?** (`_check_portfolio_concentration` was found silently failing open — always allowing the order — due to a missing URL prefix, since fixed.) Has this been re-verified live, with a real test that deliberately tries to over-concentrate and confirms it gets blocked, not just re-read in source?
- **Do `max_daily_orders` / `max_order_value` / `max_position_pct` in the trading mandate reflect a deliberate, sized-for-real-risk decision**, or are they still whatever default value was set during development/testing?

## 4. Execution & Market Microstructure

- **What order type fires at the open** — market, limit, or a TWAP/VWAP slice? `vinu-live` has slicing config (`twap_slices`, `max_slippage_pct`) — has a specific choice actually been made and tested, or is this still an unconfigured default?
- **Alpaca paper fills are unrealistically clean** (typically filled at quoted price with no real slippage). Has anyone modeled how much worse a real premarket/open fill would be, so the strategy's expected edge isn't quietly assuming paper-trading-quality execution?
- **What happens when an order is rejected** — outside trading hours, symbol halted, PDT (pattern day trader) rule triggered on a small account? Does the agent detect the rejection and adapt (retry, skip, alert), or does it silently move on assuming the order went through?

## 5. Data & Infrastructure Readiness for an Unattended Session

- **Is there an actual scheduled trigger to run the daily allocation/game-plan cycle before market open**, or does a human have to manually kick it off every trading day? (Confirmed earlier: `vinu-live`'s auto-start from `entrypoint.sh` is deliberately not wired — "on-demand only," consistent with this codebase's "consequential actions stay manual" pattern. Is that still the right call for a premarket-timed strategy, where a human might not be awake to trigger it?)
- **What happens if `news-api` goes down mid-session?** It's SQLite/WAL-mode and has crashed once already this session under concurrent load. Does the strategy layer fail open (keep trading blind to news) or halt? Has this actually been tested, or assumed?
- **Are corporate actions (splits, dividends, trading halts) accounted for anywhere?** A stale or unadjusted price feed around an ex-dividend date or a split could manufacture a false "gap" signal.
- **What happens if a service container restarts mid-session** — not at a quiet moment like the smoke test already run, but during an open order or an in-flight TWAP slice sequence? That specific scenario has not been tested; only a clean "restart while flat" case has.

## 6. Human-in-the-Loop & Governance — policy decisions, not technical ones

- **`require_confirmation: true` is the mandate default.** For premarket trading specifically — where gaps can close in minutes — does a human actually intend to sit and approve every trade via Telegram/Discord in real time? If not, flipping this off is a real risk-appetite decision that needs to be made explicitly, not discovered by the first missed confirmation window.
- **What's the actual cost of a missed confirmation?** `ConfirmationHandler` times out at 5 minutes. In a fast premarket move, is losing the trade to a timeout the acceptable failure mode, or does that need to be faster/different for this session type specifically?
- **Is the kill switch itself durable across a restart?** `/tmp/vinu-trading-halt` — is `/tmp` on a bind mount or `tmpfs` in the actual deployed containers? (This is exactly the kind of claim that turned out to be wrong twice already this session for other components — check it directly, don't assume either way.)
- **Who gets notified, and how fast, when the kill switch fires or the drawdown breaker trips?** A halt that nobody notices until hours later defeats some of the point of having it.

## 7. Promotion Path / Trust Escalation for This Specific Session Type

- **Given Stage 2 (ShadowEvaluator) is confirmed dormant, should any strategy be allowed to trade the premarket session at all before that gap is closed** — or is the honest answer here "block premarket specifically until paper-performance validation is real," even if regular-session trading proceeds?
- **Should premarket trading require a *longer or stricter* proven paper-trading track record than regular-session trading**, given its thinner liquidity and larger gap risk? If so, what's the actual bar (N days, N trades, a max-drawdown-free streak) — pick a number and justify it, don't leave it as "eventually."

## 8. What This Becomes — turning answers into a skill

Once the above have real, source-verified answers (not assumptions), the
natural next artifact is a new skill — call it `premarket-readiness/SKILL.md`,
same rigor as `live-safety/SKILL.md` — that the agent is instructed to
consult every session before acting, checking at minimum:
- Kill switch status and drawdown-breaker state (Stage 3/4, already real).
- Whether ShadowEvaluator-equivalent validation exists for each strategy
  it's about to size up for premarket specifically (until Stage 2 is
  wired, the honest answer is "no strategy has this" — the skill should
  say so plainly rather than silently proceed).
- Current regime and the graduated risk-budget tier (once something is
  actually reading it — see Section 3).
- Whether premarket data for the specific symbol is actually available
  and passes whatever minimum-volume/gap-size bar Section 2 settles on.

This document does not answer any of the above — it exists so the answers
get found deliberately, one at a time, against real source and real data,
the same discipline every other plan in this project has used, instead of
being discovered live with real orders in flight.
