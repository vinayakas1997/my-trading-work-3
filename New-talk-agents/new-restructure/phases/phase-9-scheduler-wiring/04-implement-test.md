---
name: phase-9-implement-test
status: all 4 dormant mechanisms now scheduled and wired -- Significance Triage delivery is live but has no real credentials filled in yet (user-supplied, not code)
purpose: record of what was actually touched, tested, and the real result. Not one of the original 9 planned phases (0-8) -- this is the follow-up work every one of those phases' own 04-implement-test.md independently flagged as the highest-leverage next step ("a real scheduler covering all of them"). No 01-plan.md/02-guard-rail.md/03-test.md preceded this -- there was no pre-existing plan to follow, so this file is the plan and the record together.
---

# Phase 9 -- Scheduler wiring, implementation record

Built 2026-08-11, in two passes within the same day. Four real, tested
mechanisms from Phases 0/4/6/7 were sitting inert -- correct code with no
live caller anywhere: `RunLogTrigger`/`ChangeGate` (`run_gate_cycle`,
Phase 0), `ShadowEvaluator.evaluate_all()` (Phase 4), `check_skill_edits()`
(Phase 6), and Significance Triage delivery (Phase 7).

**Pass 1** wired up the two that needed nothing invented
(`shadow-worker`, `skill-audit-worker`) and documented two apparent
blockers on the rest: no ticker watchlist, and no "Planner" team.

**Pass 2**, after rereading `mermaid-explanation.md` directly, corrected
that second blocker -- "Planner" was never meant to be its own team; it's
`idea_generator` (real, already built, inside `teams/research/`) plus a
missing deterministic triage layer in front of it, the same shape as
`thesis_intake_gate.py`. That triage layer is what Pass 2 actually built,
closing `RunLogTrigger`/`ChangeGate` end to end. Significance Triage
delivery remains the one genuinely unbuilt mechanism -- it needs an
admin/owner chat_id that doesn't exist anywhere in this codebase, a
product decision, not a wiring task.

## What got wired

### `ShadowEvaluator.evaluate_all()` -- vinu-live `shadow-worker`

Confirmed by reading `vinu_live/cli.py` directly: a single-cycle
`shadow-evaluate` command already existed and was already correct
(`run_shadow_evaluate_main`) -- the only missing piece was a *continuous*
loop, exactly the gap Phase 4/5's own records named. Added:

- `vinu_live/config.py`: `shadow_worker_interval_sec` (default 3600s,
  reusing the pre-Phase-5 `worker_interval_sec` default rather than
  inventing a new number -- shadow evaluation's paper-Sharpe signal moves
  over days, not minutes, so this doesn't need the 300s cadence
  trade-plan/feedback use).
- `vinu_live/cli.py`: `shadow_worker_main()`, identical
  `while True: cycle(); sleep()` shape to `trade_plan_worker_main`/
  `feedback_worker_main`; new `shadow-worker` subcommand.
- `vinu-live/entrypoint.sh`: `vinu-live shadow-worker &` added alongside
  the two existing background workers.

### `check_skill_edits()` -- vinu-agent `skill-audit-worker`

vinu-agent had no worker/background-process pattern at all before this --
its Dockerfile ran `vinu-agent serve` directly via `CMD`, no
`entrypoint.sh`. Added the pattern fresh, mirroring vinu-live's:

- `vinu_agent/config.py`: `skill_audit_worker_interval_sec` (default
  3600s, same reasoning as above).
- `vinu_agent/cli.py`: `skill_audit_worker_main()` + `skill-audit-worker`
  subcommand, wired into `main()`'s dispatch. `resolve_worker_interval()`
  is simpler than vinu-live's own (no `args=None` sys.argv-parsing
  fallback) because there's no dedicated `vinu-agent-skill-audit-worker`
  console script -- this is only ever reached through the subcommand, so
  `args` is always real.
- `vinu-agent/entrypoint.sh` (new file) + `Dockerfile` (`CMD` ->
  `ENTRYPOINT ["/app/entrypoint.sh"]`, matching vinu-live's Dockerfile
  shape) + `docker-compose.yml` (`agent-api`'s `command:` override
  removed -- with `ENTRYPOINT` in place it would only have been appended
  as unused trailing args).

## Pass 2 -- `RunLogTrigger`/`ChangeGate`, the real "Planner"

The user picked the watchlist source (`TickerSummaryStore.list_summaries()`)
after Pass 1. Investigating what else `run_gate_cycle`'s `on_yes` callback
needed turned up that Pass 1's "no Planner team exists" conclusion was
checking the wrong thing -- `Glob`-ing `TEAM.md` files found no team
*named* "Planner," but `mermaid-explanation.md`'s own Section 2 states
the Planner is explicitly "new triage stage + existing `idea_generator`"
-- `idea_generator` (real, tested, inside `teams/research/`) *is* half of
it. Only the triage half in front of it was missing.

**How a scheduled (non-chat) trigger calls a real team**, resolved by
reading `submit_thesis_tool.py` directly: it constructs `TeamManager`
directly and calls `.run(task)` synchronously (`_run_team` method) --
bypassing the orchestrator's own open-ended tool-call decision entirely.
`TeamManager` needs a `full_registry: ToolRegistry`, normally built by
`SessionService._run_with_agent`'s call to `build_registry(...)` inside
an active chat turn. Confirmed by reading `tools/__init__.py` directly:
every `build_registry(...)` parameter that would require a live chat
session (`session_service`, `workflow_tracker`) is optional -- only
injected into tools that specifically declare the matching attribute --
so a synthetic `session_id` string and a standalone `build_registry(...)`
call, outside any real session, is enough. No new plumbing needed; this
is the exact mechanism that already exists.

**What got built:**
- `agent/planner_triage_hook.py` (new) -- `PlannerTriage`, the
  deterministic triage half of the Planner. `.check(ticker)`: K-cap check
  (reuses `thesis_intake_gate.py`'s own `CANDIDATE_PROPOSED_EVENT_TYPE`/
  `K_CAP_DEFAULT` -- confirmed generic, queries `TickerLedger` directly,
  not a Thesis-Intake-only store, exactly as that module's own comment
  already said it should be shared) -> non-terminal-artifact dedup via
  `list_artifacts_for_symbol` (CREATED/BENCHING/PEND/PENDBLOCK/ACTIVE/
  MONITORING) -> `HypothesisRegistry` consult for prior rejected reasoning
  -> deterministic recipe pick (`vinu_research.generator.list_recipes()`,
  rotated by how many non-terminal artifacts already exist for this
  ticker -- `Artifact` has no stored "recipe used" field, so this is a
  first-pass heuristic, explicitly flagged, not real angle-characteristic
  matching, which stays `idea_generator`'s own downstream LLM job per
  `mermaid-explanation.md`). `.on_propose(...)` writes the
  `candidate_proposed` TickerLedger event -- the watchlist-side writer
  Phase 6's own follow-up list said was missing.
- `agent/scheduler_workers.py` (new) -- `run_team_for_ticker(service,
  team_name, task, session_id=...)`: standalone `build_registry(...)` +
  `TeamManager(...).run(task)`, the pattern above.
  `make_summary_agent_fn(service)`: `RunLogTrigger.refresh_if_stale`'s
  `summary_agent_fn` -- calls the real `screener` team for the summary
  text, but computes `angles_with_data`/`angle_count` from a direct,
  deterministic `GetAllAnglesTool` call, never parsed out of the LLM's
  prose. `make_planner_on_yes(service, triage)`: `ChangeGate`'s `on_yes`
  -- runs `PlannerTriage.check`, and on a "propose" verdict hands off to
  the real `research` team with the chosen recipe and any prior-rejection
  reasoning embedded directly in the task text (deterministic input, LLM
  executes it -- same division of labor as every other hook in this
  build). `hypothesis_reader_for(service)` -- in-process
  `get_hypothesis_registry()` (`broker/research_link.py`, confirmed real
  and live), adapted to the same dict shape `submit_thesis_tool.py`'s
  HTTP-based reader already returns, so Planner triage and Thesis Intake
  read prior hypotheses identically regardless of transport.
- `vinu_agent/config.py`: `planner_worker_interval_sec` (1800s -- longer
  than the other two workers on purpose, since each cycle can fire real
  LLM team calls, not just deterministic checks; first-pass, unvalidated).
- `vinu_agent/cli.py`: `planner_worker_main()` -- per cycle, per ticker in
  the watchlist: `RunLogTrigger.refresh_if_stale` (failures logged and
  skipped, never abort the cycle), then `run_gate_cycle` (Phase 0,
  completely unmodified) with the new `on_yes`. `resolve_worker_interval`
  generalized to take a config field name (now shared by
  `skill-audit-worker` and `planner-worker`).
- `vinu-agent/entrypoint.sh`: `vinu-agent planner-worker &` added.

**Known limitation, not fixed this pass:** the `screener` team's own
result hook (`team.py`'s `_apply_team_result_hook`) already calls
`write_ticker_summaries` on every completed run, so a ticker's summary
row gets upserted twice per refresh -- once by that hook, once by
`RunLogTrigger.refresh_if_stale` itself. Deliberately left
un-deduplicated, same reasoning as Phase 5's `debrief.py`/
`feedback_loop.py` overlap: both writes target the same real row with the
same real data: last-write-wins is harmless, and coupling the hook to the
trigger isn't worth it for this.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-live/vinu_live/config.py` | modified | `shadow_worker_interval_sec` field + env loading |
| `vinu-components/vinu-live/vinu_live/cli.py` | modified | `shadow_worker_main()`, `shadow-worker` subcommand |
| `vinu-components/vinu-live/entrypoint.sh` | modified | `vinu-live shadow-worker &` |
| `vinu-components/vinu-live/tests/test_cli.py` | modified | +3 tests: subcommand parsing, real loop calls `evaluate_all()` and exits cleanly on interrupt, explicit `--interval` override |
| `vinu-components/vinu-agent/vinu_agent/config.py` | modified | `skill_audit_worker_interval_sec` + `planner_worker_interval_sec` fields + env loading |
| `vinu-components/vinu-agent/vinu_agent/cli.py` | modified | `resolve_worker_interval()` (generalized), `skill_audit_worker_main()`, `planner_worker_main()`, both subcommands |
| `vinu-components/vinu-agent/vinu_agent/agent/planner_triage_hook.py` | new | `PlannerTriage` -- the deterministic triage half of the Planner |
| `vinu-components/vinu-agent/vinu_agent/agent/scheduler_workers.py` | new | `run_team_for_ticker`, `make_summary_agent_fn`, `make_planner_on_yes`, `hypothesis_reader_for` |
| `vinu-components/vinu-agent/entrypoint.sh` | new | starts `skill-audit-worker` + `planner-worker` in background, `exec`s `serve` in foreground |
| `vinu-components/vinu-agent/Dockerfile` | modified | `CMD` -> `COPY entrypoint.sh` + `ENTRYPOINT` |
| `vinu-components/docker-compose.yml` | modified | `agent-api`'s `command:` override removed |
| `vinu-components/vinu-agent/tests/test_cli.py` | new | 8 tests: interval resolution, both subcommands' parsing, `skill-audit-worker`'s real loop, `planner-worker`'s wiring (watchlist -> RunLogTrigger -> run_gate_cycle, one ticker's refresh failure doesn't abort the cycle) |
| `vinu-components/vinu-agent/tests/test_planner_triage_hook.py` | new | 10 tests: K-cap (under/at/lookup-failure), artifact dedup + recipe rotation, no-recipes-available, HypothesisRegistry consult (surfaced/lookup-failure), `on_propose` writes the event / never raises |
| `vinu-components/vinu-agent/tests/test_scheduler_workers.py` | new | 6 tests Pass 2, +8 Pass 3: `run_team_for_ticker` constructs the right team + runs the task, `make_summary_agent_fn` returns deterministic meta + LLM text (and empty text on a non-completed run), `make_planner_on_yes` skips/hands-off correctly, `hypothesis_reader_for` converts dataclasses to the shared dict shape, `build_channel_targets` (none/Telegram-only/both/token-without-id), `run_significance_cycle` (raises+delivers, flag still recorded with zero targets, one ticker's detection failure doesn't stop the rest) |
| `vinu-components/vinu-agent/vinu_agent/agent/notify_channels.py` | new | `HttpTelegramChannel`/`HttpDiscordChannel` -- one-shot REST delivery, no persistent bot connection |
| `vinu-components/vinu-agent/tests/test_notify_channels.py` | new | 6 tests: correct endpoint/payload for each channel, no-op when unconfigured, long-message chunking (both platforms' real max lengths) |
| `vinu-components/vinu-agent/vinu_agent/config.py` | modified (Pass 3) | `telegram_token`/`telegram_admin_chat_id`/`discord_token`/`discord_admin_channel_id`/`significance_worker_interval_sec` fields + env loading |
| `vinu-components/vinu-agent/vinu_agent/cli.py` | modified (Pass 3) | `significance_worker_main()`, `significance-worker` subcommand |
| `vinu-components/vinu-agent/entrypoint.sh` | modified (Pass 3) | `vinu-agent significance-worker &` added |
| `vinu-components/.env-example` | modified (Pass 3) | documented (commented-out) `TELEGRAM_TOKEN`/`VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID`/`DISCORD_TOKEN`/`VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID` -- real values are the user's to fill in, never written here |
| `vinu-components/vinu-agent/tests/test_cli.py` | modified (Pass 3) | +2 tests: `significance-worker` subcommand parsing, wiring (watchlist -> `run_significance_cycle`, `SignificanceFlagStore.close()` called) |

## Pass 3 -- Significance Triage delivery: Telegram + Discord, independently gated

User chose Telegram + Discord (not WhatsApp -- discussed and deferred:
WhatsApp Business API needs a template-approval process and a 24-hour
free-form-message window, a materially heavier lift than a bot token,
not something to fold into this pass), explicitly kept as independently
extensible so a future channel is an append, not a redesign.

**Why not reuse `channels/discord.py`/`channels/telegram.py` directly**,
confirmed by reading both: `send_message()` on each silently no-ops
(`if not self._app: return` / `if not self._client or not
self._client.is_ready(): return`) unless `.start()` has already been
called -- and `.start()` opens a persistent bot connection
(`Application.builder()...build()` / a discord.py gateway client) meant
for the interactive receive-and-reply bot. A scheduler worker firing an
occasional unprompted flag has no reason to hold that connection open.
Built `agent/notify_channels.py` instead -- `HttpTelegramChannel`
(Telegram Bot API's plain `sendMessage` endpoint) and `HttpDiscordChannel`
(Discord's REST `POST /channels/{id}/messages`, bot-token authenticated)
-- both one-shot HTTP calls, no gateway/polling connection, both
implementing the exact same `Channel` protocol
(`significance_triage.py`'s own `async def send_message(chat_id, text)`)
so `deliver_flag()` (Phase 7, unmodified) doesn't know or care which
transport it's using.

**What got built:**
- `agent/notify_channels.py` (new) -- the two channel classes above,
  including each platform's real message-length chunking (Telegram 4000,
  Discord 2000 -- same limits `channels/telegram.py`/`discord.py` already
  used, reused not reinvented).
- `agent/scheduler_workers.py`: `build_channel_targets(config)` --
  Telegram and Discord are each independently gated on their own
  token+id both being set; an unconfigured channel is silently omitted
  (logged at info level), not an error. `run_significance_cycle(tickers,
  ticker_ledger_store, flag_store, targets)` -- one pass: detect via
  `detect_repeated_rejection_pattern` (Phase 7, unmodified), create the
  flag, deliver to whichever targets exist. A flag is still recorded even
  with zero targets configured -- detection and delivery stay separate
  concerns, so nothing is silently lost while credentials aren't set up
  yet.
- `vinu_agent/cli.py`: `significance_worker_main()` -- same watchlist
  source as `planner-worker` (`TickerSummaryStore.list_summaries()`),
  `asyncio.run(run_significance_cycle(...))` per cycle (the rest of
  `cli.py`'s workers are sync loops; only this one needs an event loop,
  scoped to just the cycle call, not a full async rewrite of the file).
- `.env-example`: the four new variables, documented with exactly how to
  obtain each real value, left commented out -- real credentials are the
  user's to add to their own `.env` (gitignored), never typed into this
  conversation or written by me.

**Still true, unchanged:** no real credentials exist yet. The worker is
live and will run its full cycle (detect + record) the moment it's
deployed; delivery activates the moment `.env` has real values in it, no
further code change needed either way.

## Test results

```
vinu-live:  144 -> 147 passed (full suite; 3 new tests, Pass 1)
vinu-agent: 602 -> 626 passed (Pass 1+2) -> 642 passed (full suite; 16 new tests, Pass 3)
```

No regressions in either package's full suite, any pass.

## Known follow-ups (not blocking, not silently dropped)

- **Real Telegram/Discord credentials still need to be added to `.env`**
  -- the one remaining step to make Significance Triage delivery actually
  deliver anything; purely a user action at this point, no more code.
- **`shadow_worker_interval_sec`/`skill_audit_worker_interval_sec`/
  `planner_worker_interval_sec`/`significance_worker_interval_sec`
  (3600s/3600s/1800s/900s) are first-pass, unvalidated defaults**, same
  category as every other untuned threshold across this build.
- **WhatsApp was discussed and deliberately deferred** -- heavier lift
  (Business API template approval, 24-hour session window) than a bot
  token; `build_channel_targets`'s per-channel gating means adding it
  later is an append, not a redesign, whenever it's actually wanted.
- **The Planner triage's recipe-rotation heuristic is a real, first-pass
  placeholder**, not the "tied explicitly to the angle characteristics
  that motivated it" matching `mermaid-explanation.md` describes --
  `Artifact` has no field to build that on top of yet (no stored
  "recipe used" or "angle characteristics" reference). Real
  angle-aware recipe selection is a genuinely separate piece of work,
  likely inside `idea_generator`'s own prompt rather than the
  deterministic hook.
- **No real live-LLM run has validated `planner-worker`'s hand-off
  prompt** (the task text `make_planner_on_yes` sends to the `research`
  team) -- same category of deferred validation as Phase 1's and Phase
  8's prompt-behavior tests, same reasoning (cost/rate-limit risk on the
  free-tier model).
- The `screener`-team double-write noted above (Pass 2 section) --
  revisit only if it produces a real, observed confusion in practice,
  same threshold Phase 5 already set for its own analogous overlap.
