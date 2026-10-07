# How the settings should look for the real 24-hour system

Written 2026-10-07 from the code, the project template `.env-example`, and what I saw in the running containers earlier in this session. The real `.env` was not read (access was refused), so "now" below is the template plus the deployed profile I saw, and **each "now" must be confirmed against `.env`** before changing anything.

Rule for every row: **Change?** is `no` (keep, and here is why), `yes` (change, and here is why), or `decide` (needs a measurement or the owner's choice first). Nothing marked `yes` has been changed yet.

Real system means: Alpaca **paper** account, equities only, around the clock, unattended, the models container dormant.

## A. Settings that must not change (the safety floor)
| Setting | Target | Why |
|---|---|---|
| `ALPACA_PAPER` | `true` | Owner rule: paper only until the paper run has been judged. |
| `VINU_MODELS_ENABLED` | `false` | Models container stays dormant; model angles are skipped instead of failing every cycle. |
| `VINU_API_KEY` (secret) | set, non-empty | Empty means every internal route is open with no check. Confirm it is set in every container. |
| Mandate `require_active_artifact` | `true` | Only an ACTIVE strategy may order. Now fails closed if the strategy store cannot be read. |
| Mandate `allow_margin` | `false` | No borrowed money on a paper test. |
| Mandate `allowed_sessions` | all four (premarket, regular, afterhours, overnight) | The system trades 24 hours; each strategy is still limited to its own approved sessions by the order guard. |
| `VINU_LIVE_HALT_POLICY` | `entries_only` | A halt stops new entries but never traps an exit. |
| `VINU_LIVE_SCHEDULER_EXITS_EXEMPT_FROM_HALTS` | `true` | Same reason; risk-reducing orders must pass a halt. |
| `VINU_LIVE_OOD_DETECTOR` | `alert` | First rung only (log). `halt` and `flatten` are earned by watching `alert` in paper. |
| Research promotion flags (`VINU_RESEARCH_PROMOTION_PBO/HOLDOUT/STRESS_TEST/CORRELATION_REQUIRED`) | all `true` (code default is true; unset in deployment) | The bar is never lowered to produce a pass. |
| `VINU_RESEARCH_MIN_TRADES_FOR_PASS` | `30` | Fewer trades cannot support the statistics. |
| `VINU_RESEARCH_PROMOTION_DSR_THRESHOLD` | `0.95` | Deflated Sharpe required for promotion. |
| `VINU_LLM_GATEWAY_SLOTS` | `1` | The local model serves one request at a time. |
| `VINU_LLM_ENABLE_THINKING` | `false` | Hidden thinking used about 70 percent of the tokens and long prompts timed out. |

## B. Settings that must change for 24-hour operation
| Setting | Now (template / deployed) | Target | Change? | Why |
|---|---|---|---|---|
| `VINU_STAGE1_START_DATE` | `2026-06-17` (temporary test override, seen in agent-api and initial-analysis-api) | `2022-01-01` after checking history exists from then | **yes** | The template itself says to revert before real use. A start date this close to now gives analysis windows of a few months only. |
| `VINU_LIVE_ORDER_ROUTING_MODE` | code default `market` | session-aware: market or limit in regular hours, limit outside | **decide** | The order guard refuses market orders outside regular hours. There is a dynamic per-order routing in the orchestrator; confirm it never sends a market order outside regular before trusting it overnight. |
| `VINU_SIM_SPREAD_BPS` | `0` | measured per session (small regular, larger overnight) | **yes** | A backtest with zero spread overstates extended-hours profit, and the per-session approval rests on those backtests. Needs the spread measured from quotes first. |
| `VINU_SIMULATOR_SLIPPAGE_PCT` | `0.0005` for all sessions | higher outside regular | **decide** | Same reason; measure first. |
| `VINU_LIVE_MAX_SPREAD_BPS` | `25`, one number | per session | **decide** | Overnight spreads are wider; one limit either blocks all overnight entries or lets regular ones through too wide. |
| `VINU_LIVE_PRICE_MAX_AGE_HOURS` | `96` | tied to the strategy's bar size (a few bars for intraday, 96 for daily) | **yes (code)** | 96 hours suits daily bars across a long weekend and is far too loose for a 15-minute strategy overnight. The code takes one number in hours only. |
| `VINU_CORRELATION_MARKET_HOURS_ONLY` | `true` | review; likely `false` for the sessions traded | **decide** | A regular-hours assumption inside analysis. I have not read what it filters; check before changing. |
| `VINU_CORRELATION_SESSION_BREAK_ON_CLOSE` | `true` | review with the line above | **decide** | Breaks the series at the close, hiding overnight moves. |
| `VINU_STOCK_DEFAULT_SESSION` | unset (regular) | keep unset | no | Callers ask for a session explicitly; the default keeps old callers unchanged. |
| `VINU_VALIDATION_SESSIONS` | `regular,all` (code default) | keep | no | Each bar size tested under regular and under 24 hours. |
| `VINU_STOCK_OVERNIGHT_FEED` | `boats` (code default) | keep | no | Only source of overnight bars. 15-minute delay and from 2024-09-16 only. |
| `VINU_STOCK_POLL_INTERVAL_SEC` | `60` | keep, but confirm the poller is not gated to market hours | **decide** | Live bars must keep arriving through the night. |
| `VINU_LIVE_INTERVAL` (scheduler cycle) | `3600` | per strategy bar size | **decide** | An hourly cycle is too slow for 15-minute strategies; the decision poller (60 s) is separate. |
| `VINU_SIMULATOR_INITIAL_CAPITAL` | `1000000.0` | the paper account's real equity | **decide** | Backtest and live sizing should use the same starting size. Check the account equity first. |

## C. Settings needed so an unattended system can be trusted
| Setting | Now | Target | Change? | Why |
|---|---|---|---|---|
| `VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID`, `VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID` (+ their tokens in secrets) | not set in the template and not seen in the containers | at least one delivery channel | **yes** | With none set, flags and alerts (halt, drift, stuck trigger) are recorded but delivered nowhere. A system running through the night needs a way to reach a person. |
| `VINU_AGENT_NOTIFY_QUIET_START_HOUR` / `_END_HOUR` / `_MIN_SEVERITY` | not set | quiet hours, urgent alerts still pass | **decide** | At night only urgent alerts should wake someone. |
| `VINU_LLM_FALLBACKS` | not set | decide whether a second model exists | **decide** | With none, a model outage stops research and live decisions until it returns (orders are never placed on an AI failure). |
| `VINU_AGENT_PLANNER_INTERVAL` | `1800` | keep; measure real run time | **decide** | One research run on one local model takes long; confirm cycles do not pile up. |
| `VINU_SWEEP_INTERVALS` | code default `1d,4h,1h,15m` | must equal the bar sizes the validator tests | **decide** | Two lists of bar sizes that must agree (change-impact list in `02`). |

## D. Guards: deployed on, and the target
Deployed profile (seen earlier): entry guards, precondition enforcing, daily allocation, breaker uses broker account, abort on equity-read failure, runtime correlation trim, CVaR gate, volatility targeting, execution idempotency, maturity gating, symbol lockout after 3 losses are all **on**. Target: keep them all on. The connection manifest still labels several as "default off"; that is the code default, and the manifest note should be updated to say "on in the deployed profile".

Open guard gap: the live scheduler does not record its own orders in the book that the breaker checks (`book.writes->live.scheduler`, gap). Target: wired, then verified on a real paper order.

## E. Mandate limits to confirm against the account
`max_position_pct 0.25`, `max_order_value 50000`, `max_daily_orders 10`, `max_daily_trade_volume 200000` (code defaults; the seeded values in `entrypoint.sh` should be checked). Target: set from the paper account's actual equity, then written here with the numbers. Not yet checked.

## F. What to do next with this file
1. Confirm every "now" value against `.env` (blocked in this session; see the note to the owner).
2. Resolve each `decide` by measuring (spreads per session, what the correlation switches filter, account equity).
3. Apply each `yes`, with a test that fails if the value comes back wrong, and a line in the problem log.
4. Move each applied row into `current-settings.md`.
