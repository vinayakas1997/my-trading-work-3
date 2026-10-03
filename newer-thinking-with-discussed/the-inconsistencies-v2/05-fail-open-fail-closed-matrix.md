# Fail-open / fail-closed matrix — what each check does when its input is missing

Closes v1 C3 (the-inconsistencies-v2 plan item 2.4 / "write the one-page matrix"). Compiled 2026-10-03 from the code, not from the
docs: every row cites where the behavior lives. It records **current behavior** — nothing here is a recommendation unless it says so.
The reason it exists: each posture below is locally sensible, but no single page stated which failure opens and which closes, so a
new gate had nothing to follow and a reviewer could not see the whole picture.

Vocabulary: **CLOSED** = the safe-for-money outcome (no new risk taken) when the input is missing/failed. **OPEN** = proceeds as if
the check passed. **DEFER** = does nothing this cycle and retries. "Entries only" = only orders that increase exposure are gated.

## 1. Scheduler path (`vinu-live/vinu_live/scheduler.py`, portfolio weights + live-decision EXECUTEs)

| Check / input | When it fails or is missing | Posture | Where |
|---|---|---|---|
| Portfolio weights fetch | raises, whole cycle aborts | CLOSED | `_fetch_portfolio` |
| Broker positions fetch (or non-list reply) | raises, whole cycle aborts ("we don't know what we hold") | CLOSED | `_fetch_positions` |
| Per-symbol price | symbol omitted, its instruction skipped, retried next cycle | CLOSED (that symbol) | `_fetch_prices`, `SignalTranslator._build_instruction` |
| Account equity | HTTP error, non-200 or `configured: false` all fall through to: positions value if > 0, else **`fallback_portfolio_value` (default $1,000,000)** with a warning | **OPEN, and risky: see A7** | `_fetch_portfolio_value` |
| Breaker: aggregate VaR | covariance is always `None` on this path, so the VaR check is skipped | OPEN (named gap) | `_check_breaker` -> `check_limits` |
| Breaker: daily loss / position count / cluster / leverage | evaluated over the **trade-plan book**, which this path does not write to (audit A6); daily loss is realized-only | partially blind | `breaker/engine.py` |
| Breaker HALT verdict | skips all planning that cycle, **including reducing orders** (audit A5) | CLOSED, traps exits | `cycle()` |
| Breaker HALT: failing to engage the cross-process kill switch | logged ERROR; other order paths are NOT halted | OPEN (loud) | `_engage_real_halt` |
| Maturity-scaled limits | fetch fails -> `None` -> default (unscaled) limits; recorded as `tier=unknown` | OPEN | `_maturity_scaled_limits` |
| Local `HALT` file | present -> blocks execution | CLOSED | `guards.halt_reason` |
| Remote kill-switch status | fetch fails -> proceeds | OPEN | `guards.halt_reason` |
| Spread gate | no quote / fetch error -> proceeds (market order); spread over ceiling -> slice skipped **for both sides** (audit A5) | OPEN on missing, CLOSED on breach | `guards.fetch_spread_bps` |
| Event blackout | calendar fetch error -> proceeds; event in window -> slice skipped **for both sides** (audit A5) | OPEN on missing, CLOSED on hit | `guards.event_blackout_reason` |
| Limit price for a passive order | price unknown -> falls back to a market order, never guesses a limit | OPEN (w.r.t. the passive preference) | `_execute_plan` |
| Opt-in entry guards (cooldown, stale data, turbulence) | any error -> instructions untouched; missing timestamp / <15 closes / cooldown read error -> that guard passes; entries only | OPEN, by design | `_apply_entry_guards` |
| Live-decision strategy config (for sizing) | fetch fails -> decision left unapplied, retried next cycle | DEFER | `_fetch_live_decision_weights` |
| Live-decision EXECUTE with no size | marked applied, no position, listed at `GET /live/decisions/needs-sizing` | CLOSED, now visible | same + `list_needs_sizing` |
| Stuck live-decision trigger | retried per candle, then expired + notified after `live_decision_max_trigger_attempts` (default 3) | CLOSED (no entry) | `poller._retry_or_expire_unresolved` |
| Position rules (stop / max hold) | no entry price, bad price, or a 0 setting disables that rule; never raises | OPEN (no exit from that rule) | `position_rules.evaluate_position_rules` |

## 2. Trade-plan orchestrator (`vinu-live/vinu_live/trade_plan/orchestrator.py`)

| Check | When it fails or is missing | Posture | Notes |
|---|---|---|---|
| Entry guards: halt, cooldown, turbulence, broker outage, signal conflict, stale signal, stale data, CVaR, event blackout, spread, borrow | missing/failed data -> entry proceeds; an explicit hit blocks the entry | OPEN on missing, CLOSED on hit | **entries only; exits are never gated** (`reduce_only`) |
| Plan with no `max_position_size_pct` | entry skipped | CLOSED | |
| Broker-side backstop stop | no expected_drawdown/cvar -> no bracket (plain order) | OPEN | |
| Fill confirmation unavailable | books the intended qty; reconciliation is the net | OPEN | `_confirm_fill` |
| Reconciliation drift | auto-corrects toward broker truth up to a 10x ratio; beyond that alerts and refuses | CLOSED past the ratio | `RECONCILE_MAX_RATIO` |
| OOD detector | ships `off` | n/a | `VINU_LIVE_OOD_DETECTOR` |

## 3. Order boundary (`vinu-agent/vinu_agent/broker/order_guard.py`) — every order from either path passes here

| Check | When it fails or is missing | Posture |
|---|---|---|
| Kill switch | blocks everything except `reduce_only` orders when halt policy is `entries_only` (so a scheduler sell, which is not marked `reduce_only`, is blocked here too) | CLOSED |
| Risk budget | fetch fails -> passes; reply `status: no_equity` -> blocks new/increasing orders only | OPEN on error, CLOSED on `no_equity` |
| Portfolio concentration / pairwise correlation | fetch fails -> passes; buys only | OPEN |

## 4. Research and approval

| Check | When it fails or is missing | Posture |
|---|---|---|
| Promotion bar (deflated Sharpe, holdout, stress, PBO) | a metric that was never computed is a rejection reason | CLOSED |
| `approve_trade_plan`: no calibration history and no ACTIVE strategy | rejected | CLOSED |
| `approve_trade_plan`: scored plan with no computed risk band | rejected `risk_not_computed` (new, audit B2) | CLOSED |
| `approve_trade_plan`: plan with no Trade Score at all | passes (legacy plans) | OPEN |
| Trade Score sub-scores with missing inputs | neutral or zero values (confluence/risk neutral, regime fit 0) | OPEN, mixed |
| Maturity / synthesis / evaluation-status / precondition fetches | advisory: prompt block or write is skipped, work continues | OPEN (stacking is v1 C6) |
| Forecast / refinement prompt extras (opt-in) | fetch failure -> section omitted | OPEN |

## What the matrix shows

1. **One pattern is consistent and deliberate:** *entries* fail open on missing data and block only on an explicit hit; *exits*
   are never gated. That holds on the orchestrator and at the order boundary. It does **not** hold on the scheduler path (audit A5).
2. **One row is a genuine outlier: the capital fallback (A7).** Everything else that fails to read an input about the account
   either aborts the cycle (portfolio, positions) or skips the symbol (price). Equity falls back to an invented $1M.
3. **Three rows are "OPEN but loud"** and fine as long as someone reads the logs: kill-switch engage failure, remote halt-status
   fetch failure, VaR skipped on missing covariance.
4. **Stacked fail-opens are invisible** in aggregate (v1 C6): several of the OPEN rows can all fire in one cycle and the result
   looks like "all clear". The pipeline edge recorder (plan Phase 3) is the intended answer.

## Rule for every new gate (review checklist)

State, in the gate's docstring: (1) what it does when its input is missing, **open or closed, and why**; (2) whether it applies to
entries only or also to exits (default: entries only); (3) what it logs; (4) one test for each side of the failure. Add a row here.
