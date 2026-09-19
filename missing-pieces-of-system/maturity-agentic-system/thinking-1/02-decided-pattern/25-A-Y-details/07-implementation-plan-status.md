# Implementation plan & status — single reference

## What this file is

`00-index.md` through `06-external-signal-cross-check.md` are the
**design spec** for all 25 analyses (A–Y). This file is the
**implementation status** — what's actually built, what's tested, what
isn't built and the real, verified reason why, and exactly where to
continue. Read this file first if you're picking this work up cold;
it's the map, the other files are the territory.

Named `07-` (not `06-`) because `06-external-signal-cross-check.md`
already owns that number — reading order in this folder is
`00` → `06` (the spec), then this file.

Status as of **2026-09-20** (update: also fixed all 21 pre-existing
Windows-only test failures across `vinu-infra`/`vinu-agent` for real,
root-caused rather than left as known-bad -- see the test-count table's
footnote history below; then, on explicit user sign-off, built K's new
writer (`injected_context_log.py`) and the analyst itself, plus U's, Y's,
O's, and R's new writers (`rebalance_request_history`, `events_archive`,
`GuardResult.blocked_artifact_ids`, the live Planner-triage freshness
hook). U/Y/O/R's analysts were initially left unbuilt on the reasoning
that all four data sources start empty and need real production time to
accumulate anything worth analyzing -- then built anyway once asked
"can't we just build it so it's ready when it starts working," since
that reasoning only argued against *findings appearing soon*, never
against writing and testing the analyzer code itself (every analyst here
started at zero real evidence once; each one's own `MIN_EVIDENCE_COUNT`
gate is exactly the mechanism that makes writing it early safe).

Then J, same day, once its original framing was checked and found to be
a genuine dead end (`regime_tag` never transitions -- see this file's
own earlier note) but a *different* real signal was found sitting
unused: `market_regime_analogue.get_market_regime_stats_for_today()`
already computes a real system-wide market-regime read once per day,
just with no durable home. Added `MarketRegimeHistoryStore`
(vinu-research) to give it one, and `regime_drift.py` to trend it the
same PSI way R trends triage staleness.

Then F, same day, on the user's "think what can be done and complete the
next ones" -- re-investigated all 5 remaining items rather than assuming
last pass's verdicts still held. F's "not attempted" note turned out to
be exactly that: `significance_flags` already had `ticker`/`created_at`/
`resolved`, the same weak-join shape U's `rebalance_bypass.py` already
uses against `trade_audit_log.jsonl` -- the only real gap was
`SignificanceFlagStore` having no way to read every flag. Added
`all_flags()` and `significance_response_outcome.py`. **21 of 25
analyses now have real code for every implementable one.**

Q and N were also re-investigated this pass and found to be *more*
blocked than their 2026-09-19 notes assumed, not less -- see "How each
remaining group actually gets closed" below for what was actually
checked. S and T were re-confirmed as still needing what their existing
notes already said (a real design spec for S, `MaturityAssessor` itself
for T) -- not rebuilt this pass, no new information changed either
verdict.

Then Q and N too, on the user's explicit "think where it missed so that
we implement it and fix it" -- re-investigated one level deeper than the
prior pass and found the real, underlying problem behind each
"dependency-cost" label: Q's whole premise (a live model checkpoint's
real trade outcomes) has no real referent anywhere in production; N's
data is reachable without the heavy import, but only via live HTTP,
which traced further into a genuine coarse-cadence limit once read the
honest (offline, torch-free) way instead. Both reframed and built --
`dl_angle_backtest_health.py` (Q) and `shock_reading_before_halt.py`
(N), plus a new shared reader (`_initial_analysis_parquet.py`) neither
installs `vinu_initial_analysis` nor needs a live service. **23 of 25
analyses now have real code for every implementable one.** Only S
(needs a spec) and T (blocked on `MaturityAssessor`) remain.

Same day, on explicit user sign-off, closed two of the three items this
file's own ranked list left below S/T: **V's per-`strategy_family`
breakdown** (`paper_live_correlation.py` now emits one additional
`scope_type=strategy_family` Finding per family with enough promoted
artifacts, alongside its original `scope_type=system` row -- a real
belief-collision risk against B's own `scope_key=family` rows under the
same `analyst_name` was found and fixed the same way Q's was, see
`02-regime-risk-coverage.md`) and **`regime_analogue_enabled` flipped on**
(`VINU_RESEARCH_REGIME_ANALOGUE_ENABLED=true` added to both `agent-api`
and `research-api` in `docker-compose.yml`, covering both the real
in-process and HTTP-fallback trade-plan-authoring paths -- see
`06-external-signal-cross-check.md`). S and T were left open, as decided.

Then, on the user's explicit "the brain... we have to do that" -- checked
the docs carefully first and found **two separate components both loosely
called "the brain"**, not one: `MaturityAssessor`
(`00-maturity-agentic-system-explanation.md` -- small, fully specified,
deterministic, no LLM, unblocks T directly) and the step-8 "brain" itself
(`00-decided-pattern.md` -- a much bigger LLM synthesis agent reading
`reflection_beliefs` *and* Hindsight, which doesn't exist either, plus an
undesigned "6-axis maturity profile" and a self-trust-tracking loop).
Building the second exactly as specced would mean inventing a design on
the fly, which this file's own discipline throughout has avoided --
`MaturityAssessor` was built instead, since it's the one with no open
design questions and a real, immediate consumer (T). **T built the same
day**, once `MaturityAssessor` gave it something real to compare against
-- see `06-external-signal-cross-check.md` for both. **24 of 25 analyses
now have real code for every implementable one.** Only S (needs a spec)
remains; the step-8 LLM synthesis agent, Hindsight integration, and
self-trust-tracking are explicitly out of scope for this pass, same as
they were left out of the original 25-analysis build.

Prior update, 2026-09-19: W, H-consistency, P+G, V, and B built — P/G's
earlier "blocked" verdict was a documentation error, corrected the same
day; V's two blockers both turned out to be non-issues once chased
down; B's taxonomy design resolved by adding a new
`Artifact.strategy_family` field.

---

## The plan, in one paragraph

`00-decided-pattern.md` (parent folder) lays out 9 steps: 55 existing
data points → 25 cross-package joins (A–Y, this folder) → grouped into 6
analysts (Forecast Intelligence, Regime & Risk Coverage, Execution &
Money-Flow, Decision-Process/Cognition, Governance & Freshness,
External-Signal Cross-Check) → each analyst writes `Finding`s through one
shared severity/trend pipeline (Layer 0/1) → into two tables
(`reflection_findings_history`, `reflection_beliefs`) → optionally into
Hindsight memory banks → synthesized by "the brain" (a 7th, not-yet-built
component) into one maturity narrative. `05-to-do.md` (parent folder)
originally scoped what had to be designed before any of this could be
coded; that's now fully closed. This file picks up from there — the
actual build.

## Where the code actually lives

- **Layer 0/1 (shared, cross-analyst)**: `vinu-infra/reflection.py` —
  `ReflectionStore` (3 tables), `Finding` dataclass, `classify_severity()`
  /`compute_trend()` (PSI-based), `write_finding()`/`write_findings()`.
  25 tests, `vinu-infra/tests/test_reflection.py`.
- **The worker + every analyst module**: its own service,
  `vinu-reflection/` — **not** inside vinu-agent. That was the original
  plan (`05-to-do.md` #5's first decision), reversed 2026-09-19 once
  explicitly asked for a cleaner separation; kept cheap to reverse again
  since every analyst only ever imports another service's storage
  classes in-process (mount-and-import), never vinu-agent-internal
  orchestration code — moving `vinu_reflection/reflection/` back into
  `vinu_agent/reflection/` later would be a folder move, not a rewrite.
  - `vinu_reflection/cli.py` — `ANALYSTS` registry, `run_cycle()`
    (per-analyst try/except isolation), `reflection_worker_main()` (the
    real `while True: cycle(); sleep()` loop `02-analyst-interface.md`
    only had as pseudocode before).
  - `vinu_reflection/reflection/*.py` — one module per built analysis
    (see table below).
  - `vinu_reflection/config.py` — env-resolved paths to every mounted
    service's data root.
  - Wired into `docker-compose.yml` as `reflection-worker`: no HTTP
    port, read-only mounts of vinu-agent/vinu-live/vinu-research/
    vinu-screener/vinu-portfolio/vinu-stock-price's data roots, all six
    added as real Python dependencies (mount-and-import, same posture
    `vinu-agent/broker/research_link.py` already established for
    vinu-research; vinu-stock-price was already installed transitively
    via vinu-agent's own chain, added explicitly to `pyproject.toml` for
    P/G's `ingest_health.py`). A 7th read-only mount
    (`./data/initial-analysis:/initial-analysis-data`, 2026-09-20, Q/N)
    is different in kind from the other six: a *data* mount only,
    `vinu_initial_analysis` is never added as a Python dependency at
    all -- see `vinu_reflection/reflection/_initial_analysis_parquet.py`.

## Status at a glance

**24 of 25 analyses implemented and tested. 1 not built** (S), with a
real, checked reason (not "not gotten to yet") — see the table.

| Package | Tests | Status |
|---|---|---|
| `vinu-infra` | 254 (248 + 6 new `TestPearsonCorrelation`) | green |
| `vinu-reflection` | 165 (144 (see prior entries) + 21 new: `test_maturity_assessor.py` (13) + `test_lesson_maturity_baseline_check.py` (8)) | green |
| `vinu-agent` | 1212 (1208 passed + 4 skipped; 1205 + 4 skipped + 3 new `SignificanceFlagStore.all_flags()` tests) | green (unchanged this pass — Q/N touched only vinu-reflection + docker-compose.yml) |
| `vinu-live` | 442 (436 + 6 new `TestRebalanceRequestHistory`) | green |
| `vinu-screener` | 436 | green |
| `vinu-portfolio` | 209 | green |
| `vinu-research` | 913 (912 passed + 1 skipped; 889 + 16 `test_strategy_family.py`/`TestStrategyFamilyField` + 9 new: `test_market_regime_history.py` (6) + 2 new `TestGetMarketRegimeStatsForToday` persistence tests) | green (one `TestThreadSafety::test_concurrent_writes` flake seen once under full-suite CPU contention, unrelated to this change — reruns 23/23 in isolation) |
| `vinu-stock-price` | 111 (104 + 3 new `TestIngestLog` + 4 new `TestEventsArchive`) | green |

All of the above ran for real, in-session, in a from-scratch Python 3.12
venv built specifically to verify this pass (this repo's own committed
`.venv`s were each built on a different machine/OS and don't run here).
Earlier drafts of this file claimed a local Application Control policy
permanently blocked pandas-dependent tests in this environment
(`test_ingest_health.py`, `test_paper_live_correlation.py`, and several
pre-existing files) and reported those two as verified only via a
standalone stub harness instead — that block turned out to be transient
(most likely a one-time AV/allow-list scan on first execution of a freshly
pip-installed binary), not a permanent constraint: a second, independent
venv ran the real suites for every package, including both files,
cleanly.

`vinu-infra`'s 19 Windows-only failures (`test_secrets.py`,
`test_ticker_profile.py`, `test_llm_client.py`,
`test_llm_client_async.py`, `test_logging.py`) and `vinu-agent`'s 2
(`TestOrderThrottle`) were first reported (2026-09-18) as pre-existing
and unrelated to this pass, since neither package was touched by it.
On the user's follow-up ("check the errors and fix them instead of
pointing them out"), all 21 were root-caused and fixed for real rather
than left as known-bad:
- 18 of the 19 `vinu-infra` failures (`test_llm_client.py`,
  `test_llm_client_async.py`) shared one root cause: `LlmClient.close()`
  / `AsyncLlmClient.close()` closed the HTTP session and cache but never
  called `TelemetryStore.close()` -- a method that already existed
  specifically to release `telemetry.db`'s sqlite connection before
  `TemporaryDirectory` cleanup, just never wired up at the one call site
  that mattered. Fixed in `llm/client.py` and `llm/client_async.py`.
- 1 (`test_logging.py`) was the same class of bug for a log
  `FileHandler`: the test's own cleanup fixture closed root-logger
  handlers, but only in fixture teardown, which runs *after* the
  `TemporaryDirectory` block already tried (and failed) to delete the
  dir. Fixed by closing the handler inside the test, before the `with`
  block exits.
- 2 (`test_secrets.py`) compared `secrets_dir()` against a hardcoded
  POSIX string (`"/tmp/custom-secrets"`) instead of a `Path`; `Path`
  normalizes separators per-platform so the string comparison only ever
  held on POSIX. Fixed by comparing `Path` objects (`secrets_dir() ==
  Path(...)`), which is correct on every platform since both sides
  normalize the same way -- no change to `secrets_loader.py` itself,
  since its POSIX-style default is correct (it always runs inside Linux
  containers in production).
- 1 (`test_ticker_profile.py::test_lock_file_created_alongside`) was a
  real cross-platform inconsistency in `ticker_profile.py`: the
  `filelock` library's default Windows backend deletes the `.lock`
  pathname on release (POSIX's native-lock backend doesn't need to).
  Fixed by passing `preserve_lock_file=True` to both `FileLock(...)`
  calls, so the lock file's on-disk presence is now deterministic on
  every platform instead of silently differing by OS.
- Both `vinu-agent` `TestOrderThrottle` failures were a test-isolation
  gap, not a throttle-logic bug: `OrderGuard.check()` always calls
  `_check_risk_budget()`, which does a real GET to
  `localhost:8090/portfolio/risk/status`; with no portfolio service
  listening, that fails via a real connection-refused round trip on
  every call, measurably slower on Windows than on Linux (dual-stack
  loopback fallback / firewall inspection) -- slow enough that the
  throttle's 1-second real-clock window's oldest entries aged out before
  the 4th call, so the throttle itself never got a chance to trip. Fixed
  by mocking `requests.get` in both tests (following the same pattern
  already used elsewhere in `test_order_guard.py`), so they test the
  throttle in isolation instead of racing an unrelated network call.

Result: all 21 are now green. Full from-scratch venv re-verification
(2026-09-18) after the fixes: `vinu-infra` 254/254, `vinu-agent`
1171/1171 passed + 4 skipped (`test_order_guard.py` alone: 83/83, was
2 failed/81 passed), `vinu-research` 905/905 passed + 1 skipped,
`vinu-reflection` 76/76, `vinu-stock-price` 107/107, `vinu-live`
436/436, `vinu-screener` 436/436, `vinu-portfolio` 209/209 -- the whole
repo's test suite is green with zero known-bad tests.

Real infra bugs found and fixed along the way (both worth knowing about
regardless of this reflection work):
- `trade_audit_log.jsonl` had no `VINU_TRADE_AUDIT_LOG` set anywhere in
  `docker-compose.yml` for `live-api` — it was writing into the
  container's ephemeral `$HOME`, not its mounted `/data` volume, so the
  whole log was silently lost on every restart. Fixed.
- `reflection-worker` itself had no `VINU_RESEARCH_DATA_ROOT` set — the
  first 3 analysts built (A, plus the Decision-Process ones that read
  vinu-research) would have silently read/written nothing in a real
  deployment. Fixed.
- Same bug, third instance: `live-api` had no `VINU_CALIBRATION_LOG` set
  either — `calibration_log.jsonl` (needed for W) was also writing into
  the container's ephemeral `$HOME`, not `/data`. Fixed.
- `vinu_infra/freeze.py` (needed for H's consistency piece) turned out to
  be entirely unreachable as `vinu_infra.freeze` — it lived in an orphaned
  `vinu-infra/vinu_infra/` subdirectory never covered by the package's own
  flat `package-dir` mapping, so nothing anywhere could actually import
  it despite the module itself being real and correct. Moved to
  `vinu-infra/freeze.py` (the same flat layout every other vinu-infra
  module already uses) — fixed, not just worked around.
- P/G's own "blocked" verdict (`01-forecast-intelligence.md`) turned out
  to be a documentation error, not a real gap: `calibration.py`'s
  `add_entry()` has set a real `CalibrationEntry.timestamp` since
  2026-07-27, two months before that verdict claimed otherwise, and it's
  wired to a real writer (vinu-live's `feedback_loop.py`). Worth noting
  as a caution about this file's own reliability — a "checked the real
  code" claim can still be wrong; re-verify before trusting a blocker
  claim at face value, this file's own included.
- `vinu_stock.storage.backend.MetaBackend` (the normal way to open
  vinu-stock-price's `symbol_catalog`/`ingest_log`/`provider_fallback_log`
  tables) turned out to require `VINU_STOCK_DATA_ROOT` to be set even
  when a caller passes its own explicit db path — `SettingsStore`'s
  schema init calls `vinu_stock.config.load_config()` for env-default
  seeding, entirely decoupled from the path actually given to
  `MetaBackend()`. `ingest_health.py` opens `CatalogStore` directly
  instead (same construction vinu-stock-price's own tests already use)
  to avoid that unrelated coupling — found while writing this pass's own
  tests, not by inspection alone.
- V's own "needs investigation" note (`02-regime-risk-coverage.md`)
  assumed `paper_performance` needed a `promoted_at` marker to split
  paper-period from live-period returns. Grepping `PaperPerformanceStore`'s
  one real writer (`ShadowEvaluator.record_daily_paper_returns()`,
  gated on `status=BENCHING`) showed the split already exists by
  construction — nothing ever appends to it once an artifact leaves
  BENCHING. No schema change needed at all, just the investigation this
  file's own ranked list called for.
- B's own "needs a new categorical scheme" note assumed `signal_definition`
  might be a usable (if messy) source once parsed. Checked directly: it's
  not messy, it's empty — no real writer anywhere ever sets
  `Artifact.signal_definition` on a real artifact
  (`service.py::_create_artifact_from_run` never touches it). The
  taxonomy ended up keyed off `ResearchRunRecord.user_idea` instead, a
  field the design doc's own grep for "`strategy_family`/`family`" never
  had reason to look at.

---

## Per-analysis status (all 25)

| # | Cluster | Analyst module | Status | File / reason |
|---|---|---|---|---|
| D | Decision-Process | `decision_process` | ✅ Built | `decision_process.py` |
| L | Decision-Process | `decision_process` | ✅ Built | `process_mining.py` |
| M | Decision-Process | `decision_process` | ✅ Built | `debate_value.py` |
| K | Decision-Process | `decision_process` | ✅ Built | `memory_effectiveness.py` (new `InjectedContextLogStore` writer in vinu-agent, 2026-09-20) |
| A | Forecast Intelligence | `forecast_intelligence` | ✅ Built | `angle_trust.py` |
| Q | Forecast Intelligence | `forecast_intelligence` | ✅ Built | `dl_angle_backtest_health.py` (reframed off the DL angles' own real backtest-accuracy history — no live checkpoint concept exists in production; new `_initial_analysis_parquet.py` torch-free reader, 2026-09-20) |
| P | Forecast Intelligence | `forecast_intelligence` | ✅ Built | `ingest_health.py` (2026-09-19 "blocked" verdict was a documentation error, corrected) |
| G | Forecast Intelligence | `forecast_intelligence` | ✅ Built | `ingest_health.py` (same module as P) |
| S | Forecast Intelligence | `forecast_intelligence` | 📋 Needs a spec | numeric-claim text extraction — no existing parser to build against |
| C | Execution & Money-Flow | `execution_money_flow` | ✅ Built | `loss_attribution.py` |
| U | Execution & Money-Flow | `execution_money_flow` | ✅ Built | `rebalance_bypass.py` (new `rebalance_request_history` writer, 2026-09-20; writes no findings until real evidence accumulates past `MIN_EVIDENCE_PER_GROUP`) |
| Y | Execution & Money-Flow | `execution_money_flow` | ✅ Built | `event_holding_loss.py` (new `events_archive` writer, 2026-09-20; same evidence-floor gating) |
| E (pair) | Regime & Risk Coverage | `regime_risk_coverage` | ✅ Built | `correlation_coverage.py` |
| E (concentration) | Regime & Risk Coverage | `regime_risk_coverage` | ✅ Built | `concentration_coverage.py` |
| B | Regime & Risk Coverage | `regime_risk_coverage` | ✅ Built | `regime_strategy_coverage.py` (new `Artifact.strategy_family` field, classified from `user_idea`) |
| N | Regime & Risk Coverage | `regime_risk_coverage` | ✅ Built | `shock_reading_before_halt.py` (reframed to the nearest quarterly shock snapshot before a real halt — the official cadence is quarterly, not live; same new torch-free reader, 2026-09-20) |
| V | Regime & Risk Coverage | `regime_risk_coverage` | ✅ Built | `paper_live_correlation.py` (both blockers were non-issues once chased down; per-`strategy_family` breakdown added 2026-09-20 — see below) |
| H (governance) | Governance & Freshness | `governance_freshness` | ✅ Built | `skill_edit_governance.py` |
| H (consistency) | Governance & Freshness | `governance_freshness` | ✅ Built | `consistency_freeze.py` |
| O | Governance & Freshness | `governance_freshness` | ✅ Built | `mandate_limit_friction.py` (new `GuardResult.blocked_artifact_ids` writer, 2026-09-20; same evidence-floor gating) |
| R | Governance & Freshness | `governance_freshness` | ✅ Built | `triage_freshness.py` (new live Planner-triage freshness hook, 2026-09-20; same evidence-floor gating) |
| F | Governance & Freshness | `governance_freshness` | ✅ Built | `significance_response_outcome.py` (`significance_flags` already had `ticker`/`created_at`/`resolved` — same weak join as U; new `SignificanceFlagStore.all_flags()` read method, 2026-09-20) |
| W | Governance & Freshness | `governance_freshness` | ✅ Built | `threshold_calibration.py` (2 of the design doc's 3 named checkpoints — the third has no real writer) |
| I | External-Signal Cross-Check | `external_signal_cross_check` | ✅ Built | `screener_agreement.py` |
| X | External-Signal Cross-Check | `external_signal_cross_check` | ✅ Built | `screener_agreement.py` (same module as I) |
| J | External-Signal Cross-Check | `external_signal_cross_check` | ✅ Built | `regime_drift.py` (reframed off the real `market_regime_analogue.get_market_regime_stats_for_today()` signal; new `MarketRegimeHistoryStore` writer, 2026-09-20; same evidence-floor gating as U/Y/O/R) |
| T | External-Signal Cross-Check | `external_signal_cross_check` | ✅ Built | `lesson_maturity_baseline_check.py` (unblocked 2026-09-20 once `_maturity_assessor.py` (new, `MaturityAssessor`) existed to compare against) |

Note: `MaturityAssessor` itself
(`vinu_reflection/reflection/_maturity_assessor.py`) is not a row in this
table — it's a shared, non-Finding-writing module T imports, not one of
the 25 analyses.

**Legend**: ✅ built & tested · ❌ blocked (real data doesn't support the
design as written — needs a new writer or a rescoped design) · ⏸
deferred (real tradeoff, not a gap — a decision to make, not data to
find) · 🚧 structurally blocked on another not-yet-built component · 📋
needs a written spec for something with no precedent in this codebase.
(🔍 "needs real investigation" and 🆕 "needs a new scheme invented" no
longer appear in the table — V and B, the rows that used them, were both
investigated/designed and built 2026-09-19.)

## The 6 analysts — completion by cluster

The "6 analysts" are groupings of the 25 analyses, not separate
components to build — each analyst is just `ANALYSTS` list entries
(functions) sharing a `cluster` label on their `Finding`s. There is no
per-analyst code to write beyond its member analyses' `run()` functions.

| Analyst | Analyses | Built | Blocked/deferred | Needs work |
|---|---|---|---|---|
| Decision-Process / Cognition | D, L, K, M | 4 (D, L, K, M) | 0 | 0 |
| Forecast Intelligence | A, Q, P, G, S | 4 (A, P, G, Q) | 0 | 1 (S) |
| Execution & Money-Flow | C, U, Y | 3 (C, U, Y) | 0 | 0 |
| Regime & Risk Coverage | B, E, N, V | 5 (B, E — both pieces, V, N) | 0 | 0 |
| Governance & Freshness | O, R, F, W, H | 5 (H — both pieces, W, O, R, F) | 0 | 0 |
| External-Signal Cross-Check | I, J, T, X | 4 (I, J, T, X) | 0 | 0 |

**Every one of the 6 analysts now has every implementable analysis
actually done — nothing left in "Blocked/deferred" or "Needs work"
anywhere except S (a real spec gap)** (Decision-Process: 4 of 4 — K's missing writer
(`injected_context_log.py`) built 2026-09-20 once the user decided it
was worth adding; Execution & Money-Flow: 3 of 3 — C plus U/Y, both
built 2026-09-20 (new writer, then the analyst itself, once asked to
build ahead of real data rather than wait); Governance & Freshness: 5 of
5 — H both pieces plus W, O, R, and F (F re-investigated and built
2026-09-20 once U's own weak-join precedent existed to reach for — see
below); Forecast Intelligence: 4 of 5 — A, P/G merged, and Q (reframed
and built 2026-09-20 once its live-checkpoint premise was found to have
no real referent in production — see below) — with only S left, needing
a spec; Regime & Risk Coverage: 5 of 5 — B, E both pieces, V, and N
(reframed and built the same pass as Q, once its data turned out
reachable torch-free but only at quarterly cadence — see below);
External-Signal Cross-Check: 4 of 4 — I/X plus J (reframed and built
2026-09-20) plus T (built the same day `MaturityAssessor` was, once it
had a real tier to compare LESSON snapshots against — see below). U, Y,
O, and R's new writers
(`rebalance_request_history`, `events_archive`,
`GuardResult.blocked_artifact_ids`, the live Planner-triage freshness
hook) were built 2026-09-20 on explicit user sign-off; their analyst
modules (`rebalance_bypass.py`, `event_holding_loss.py`,
`mandate_limit_friction.py`, `triage_freshness.py`) were then built the
same day too, once asked "can't we just build it so it's ready when it
starts working" -- each one's own `MIN_EVIDENCE_COUNT` floor (same
mechanism every other analyst here already uses) means it writes nothing
until real production data actually clears that floor, but the code is
real, tested, and registered now rather than needing a second build pass
later. J followed right after: its original framing was a real dead end
(`regime_tag` never transitions), but investigating it surfaced a
different, already-real market-regime signal
(`market_regime_analogue.get_market_regime_stats_for_today()`) with no
durable home — `MarketRegimeHistoryStore` (vinu-research, new) gives it
one, and `regime_drift.py` trends it the same PSI way R trends triage
staleness. F came next, on the user's explicit ask to re-investigate
every remaining item rather than assume last pass's verdicts still
held: `significance_flags` already had `ticker`/`created_at`/`resolved`
all along, the exact weak-join shape U established — the 2026-09-19
"genuinely blocked" verdict just predated that precedent. Q and N were
re-investigated the same pass and found to be *more* blocked than
believed at first, not less — then, on the user's explicit follow-up
("think where it missed so that we implement it and fix it"), traced one
level deeper still and found the real reframe for both: Q's live-
checkpoint premise has no referent in production at all (rebuilt around
the angles' own real backtest history instead); N's data is torch-free
readable but only at quarterly cadence (rebuilt around the nearest
quarterly snapshot instead of "immediately before"). Both built
2026-09-20 via a new shared reader (`_initial_analysis_parquet.py`) that
reads vinu-initial-analysis's Parquet files directly without installing
the package. **23 of 25 analyses now have real code for every
implementable one.** What's left (S, T) is entirely a real spec gap and
a structural blocker on a separate, larger component — not
uninvestigated gaps, and not unbuilt code waiting on data that was
already safe to build against.

---

## How each remaining group actually gets closed

**K, U, Y, O, R all resolved and fully built 2026-09-20** — the user was
asked directly which of the five new-writer decisions were worth making
(said yes to all five: K first, then U/Y, then O/R once investigated and
found to be a different shape), then asked again whether the analysts
themselves should be built ahead of real data rather than left waiting
("can't we just build it so it's ready when it starts working") — yes
to that too, for all four still pending at that point (U/Y/O/R; K's
analyst was already built the same pass as its writer, since chat turns
are frequent enough that it didn't need to wait). Every analyst here
already starts at zero real evidence and gates on its own
`MIN_EVIDENCE_COUNT` floor before writing anything — that's the
mechanism that makes building U/Y/O/R's analyzers now, before real data
exists, exactly as safe as building any other analyst ever was.
- **K**: writer (`injected_context_log.py`) + analyst
  (`memory_effectiveness.py`). See `04-decision-process-cognition.md`.
- **U**: writer (`rebalance_request_history` table, appended to from
  `RebalanceRequestQueue.consume()`) + analyst (`rebalance_bypass.py`,
  `MIN_EVIDENCE_PER_GROUP=5` given critical bypasses are "rare events by
  design"). See `03-execution-money-flow.md`.
- **Y**: writer (`events_archive` table, appended to from
  `EventsStore.replace_kind()` before its existing delete) + analyst
  (`event_holding_loss.py`, `MIN_EVIDENCE_COUNT=20`). See
  `03-execution-money-flow.md`.
- **O**: writer (`GuardResult.blocked_artifact_ids`, populated at
  `order_guard.py`'s four operator-limit rejection sites) + analyst
  (`mandate_limit_friction.py`, `MIN_EVIDENCE_COUNT=10`, reads
  `decay_snapshots` via `get_strategy_store()` same as B/V — **not**
  `data_root_paths["vinu_research"]`, a key that doesn't exist in the
  real wiring and was a real bug caught in testing). See
  `05-governance-freshness.md`.
- **R**: writer (a live freshness check at the real "Planner triage
  event" call site, `ChangeGate`'s `run_gate_cycle` → `_on_yes` in
  `scheduler_workers.py`, logging one of three exact event_types via the
  already-existing `TickerLedgerStore` — no new table needed) + analyst
  (`triage_freshness.py`, adjacent-window PSI same as `angle_trust.py`).
  Two new pure-read methods on `TickerLedgerStore`
  (`list_events_by_type`/`list_events_by_types`), ordered by SQLite
  `rowid` rather than `timestamp` — a real ordering bug (same-second
  writes losing their true relative order) found and fixed while testing
  this analyst. See `05-governance-freshness.md`.

All four new analysts (`rebalance_bypass.py`, `event_holding_loss.py`,
`mandate_limit_friction.py`, `triage_freshness.py`) are registered in
`cli.py`'s `ANALYSTS`/`_SEED_FNS` and were smoke-tested running a full
cycle against completely empty mounted data roots — zero crashes, zero
findings written (correct: no evidence yet), confirming they're
genuinely ready to start producing real findings the moment production
data clears each one's evidence floor, with no second build pass needed.

**J, reframed and built 2026-09-20**: its original framing really was a
dead end -- `Artifact.regime_tag` is a static, set-once-at-creation
field, never a time series, so "regime relabeling events" don't exist
and never will without inventing a wholly new concept. But that's not
the only real regime signal in this codebase: `market_regime_analogue.
get_market_regime_stats_for_today()` (vinu-research) already computes a
genuine, system-wide, once-per-day market-regime read (a KNN match of
today's market pattern against historical regime windows), feeding
`TradeScore.regime_fit_score` — it just lived only in an in-memory,
process-lifetime day-cache with nowhere durable to land (confirmed
`TradeScoreResult` is never persisted to `SqliteStrategyStore`). Closed
by adding `MarketRegimeHistoryStore` (vinu-research, new: one row per
calendar date), wired from `get_market_regime_stats_for_today()`'s one
real call site (`trade_plan_authoring.py`'s Phase 4 branch) via a new
`get_market_regime_history_store()` helper in
`vinu-agent/broker/research_link.py` (same env-var-direct pattern
B/V/O already use). `regime_drift.py` (new analyst) reads that history
and PSI-trends `positive_ratio` the same adjacent-window way
`triage_freshness.py` trends stale fraction. Two real caveats carried
forward, not fixed: `regime_analogue_enabled` is off by default, and
persistence only happens on days `author_trade_plan()` actually runs
that branch — sparser than a guaranteed daily heartbeat, so evidence
accumulates more slowly here than for the other 19 built analyses. See
`06-external-signal-cross-check.md` for the full reasoning.

**Q and N, re-investigated 2026-09-20 — found to be worse than the
2026-09-19 "dependency-cost" framing, not better**: the original notes
treated this as "the data exists, importing the owning package is just
expensive" — the same shape J and F turned out to have (a real signal
sitting behind an avoidable cost). Checked whether that was actually
true for Q/N specifically, the way it was checked for J/F, rather than
assuming the earlier framing still held.
- **Q**: traced `weights_ref` (the specific DL-model checkpoint a
  forecast should be attributed to) all the way through the real
  attribution pipeline and found it never crosses into any data vinu-
  research/vinu-agent stores. `angle_calibration_entries`
  (`vinu-research/vinu_research/storage/strategy_store.py`) — the table
  Q's own Fetch assumes carries `weights_ref` — has no such column, and
  no `symbol` column either; `Artifact.origin_angles` (the only real
  angle-attribution field that exists) is populated from `angles_used`,
  a plain list of angle-name strings an LLM research-manager
  self-reports (`research_artifact_writer.py:100`), with no connection
  to which checkpoint file that angle actually used. So the dependency
  cost was never the real blocker: even a free, torch-free reader for
  vinu-initial-analysis's `.pt` files would have nothing to join them
  to. Buildable only after new plumbing threads `weights_ref` from
  wherever a DL angle's inference actually resolves a checkpoint
  (inside vinu-initial-analysis, not explored this pass) through to
  `AngleCalibrationEntry` — a real, if mechanically similar to K/U/Y/O/R,
  new-writer project, but a materially bigger one since it starts inside
  an unfamiliar, heavy ML service rather than a small addition to an
  already-mounted store.
- **N**: checked whether `shock_clustering`/`shock_personality` angle
  results are reachable without the assumed heavy import, since
  `fetch_personality_features` (`trade_plan_authoring.py`) already reads
  them via `ResearchTools.get_angle_rows()`. They are — but only over a
  live HTTP call to vinu-initial-analysis's own running server
  (`tools.py`'s `_correlation_client`), not a file read. Every other
  analyst in this worker is a pure, offline read of a mounted, committed
  file — none of them require any origin service to actually be running.
  Building N this way would introduce a first-of-its-kind live-service
  dependency into the reflection worker, a real architecture change, not
  an implementation detail — worth a deliberate decision on its own,
  separate from Q's plumbing gap even though both were filed under the
  same "dependency-cost" label originally.

**Q and N, taken one level deeper and built 2026-09-20** (same day, on
the user's explicit "think where it missed so that we implement it and
fix it"): the "real options" this file previously left undecided turned
out to have a cleaner answer than any of the three once actually
checked, rather than requiring a pick between them.
- **Q's reframe**: chased `weights_ref` all the way to its one real
  write site (`walk_forward.py`'s `weights_sink` call, invoked only from
  each DL angle's offline `backtest.py`) and confirmed the LIVE forecast
  path (`compute.py`, what `AngleRunner` actually runs on schedule) never
  saves or references a checkpoint at all — read directly, not assumed.
  There is no live-checkpoint concept to plumb `weights_ref` *to* even if
  the attribution pipeline were extended, so option (b) above was a dead
  end too. What IS real: `orchestration_registry.py` runs every DL
  angle's `backtest.py` on a genuine (if quarterly) schedule, writing an
  immutable `tier2` Parquet record with real `bar_ts`/`hit`/`weights_ref`
  per walk-forward step. `dl_angle_backtest_health.py` reads that
  directly — an adjacent-window PSI trend on `hit` (same shape as A), plus
  a flat staleness check on the record's own age.
- **N's reframe**: confirmed `AngleStorage` (the class vinu-initial-
  analysis itself uses to read/write these files) only ever imports
  `pandas`/`pyarrow` — the heavy deps belong to the angle-computation
  modules, never the storage layer. So a torch-free reader wasn't a
  hypothetical option (a); it's exactly what `AngleStorage` already
  proves works, given its own small implementation. That closed the
  dependency question, but reading the real schedule
  (`quarters.py`/`AngleRunner.run()`'s `tier="tier2"` default) found
  shock readings only ever refresh quarterly in the official record —
  even the "continuous" hourly-polling mode dedupes against the same
  quarterly window. `shock_reading_before_halt.py` reads the same way,
  reframed to "the nearest quarterly snapshot before a real halt."
- **Shared infrastructure**: `_initial_analysis_parquet.py` (new,
  vinu-reflection) is the one small reader both use —
  `list_analyzed_symbols()`/`read_latest_run()`/`read_all_runs()`,
  `pandas`/`pyarrow` only (both already transitively installed via
  vinu-research/vinu-stock-price — no new dependency needed).
  `docker-compose.yml`'s `reflection-worker` gets a 7th mount
  (`./data/initial-analysis:/initial-analysis-data:ro`) that's different
  in kind from the other six: a data mount only, `vinu_initial_analysis`
  is never installed as a package.

This is what option (a) (extend the ticker-profile mechanism) would have
had to reimplement anyway to actually work — reading the real storage
layer directly turned out simpler than adding a new producer-side
projection step, once the storage layer was actually checked instead of
assumed heavy.

**T (structurally blocked)**: nothing to do until `MaturityAssessor`
itself is built — that's a separate, larger piece of work (the "brain,"
step 8 of `00-decided-pattern.md`), not part of the 25-analysis build at
all. Revisit T once that exists.

**S (needs a spec)**: needs someone to actually design the numeric-claim
extraction approach (likely: regex/number-parsing over the deterministic
fact sheet's known fields, cross-checked against the same numbers
appearing in the LLM summary's prose) before it's buildable. Nothing
else in this codebase does this kind of text-vs-structured-data
comparison to model it on.

**H-consistency and W, investigated and built 2026-09-19**: both turned
out cleaner than the design doc assumed. `freeze.py` needed no refactor
at all (it was just never wired into the installed package — fixed by
moving it into vinu-infra's own flat layout); W lost its counterfactual
ambition (no sweep helper exists anywhere) but kept a real, honestly
narrower drift-detection question, built for its 2 real checkpoints.

**O, investigated 2026-09-19 — real blocker found, not built (later
built 2026-09-20, see above)**: the "eventual performance of a blocked
artifact" half is real and computable (`decay_snapshots` is populated by
the offline promotion pipeline, independent of whether live order
submission was ever blocked). The real blocker is narrower than the
design doc implied: `order_rejected` audit entries carry no `artifact_id`
at all — identifying *which* artifact a rejection blocked needs a
symbol+time-window match, not a stored key. A real decision (accept the
weak match, or add `artifact_id` to `order_rejected` logging first), not
a missing investigation — same shape as the K/U/Y new-writer decisions
above.

**F, investigated 2026-09-19 — marked genuinely blocked, reversed
2026-09-20**: the 2026-09-19 note said no real or weak join existed —
`significance_flags` "has no `artifact_id`/order/trade id at all, only
`ticker`". True as far as it went, but incomplete: `ticker` *plus*
`created_at` (also on the table all along) is exactly the same
symbol+time weak-join shape O's own note above already reasons about —
it just wasn't recognized as a viable join at the time, because the
concrete precedent for actually doing that join (U's `rebalance_bypass.py`
matching a request's symbol+timestamp against `trade_audit_log.jsonl`'s
exit rows) hadn't been built yet on 2026-09-19. Re-investigated
2026-09-20 with that precedent in hand and built — see the F entry above
and `05-governance-freshness.md` for the full reasoning. Worth
remembering: "genuinely blocked" from an earlier pass is only as good as
the precedents that existed when it was written, not a permanent verdict.

**V, chased down and built 2026-09-19**: both blockers this file's own
ranked list flagged turned out to be non-issues. `paper_performance` was
assumed to need a `promoted_at` marker to split paper-period from
live-period returns; its one real writer (`ShadowEvaluator.
record_daily_paper_returns()`) only ever runs against `status=BENCHING`
artifacts, so the split already exists by construction — no schema
change needed. The missing Pearson-correlation helper was a real, small
gap — added to `vinu_infra/reflection.py`. Scoped down to
`scope_type=system` (B's `strategy_family` taxonomy didn't exist yet at
the time) and substituted a paper-vs-live distribution PSI for the
significance gate, since the design doc's single recomputed-each-cycle
correlation scalar has no natural two-window PSI comparison the way
every other analyst's Condition does. See `paper_live_correlation.py`'s
own docstring for the full reasoning.

**V's per-`strategy_family` breakdown added 2026-09-20**, once B's
taxonomy (below) existed to revisit the scope-down with. Adds one
`scope_type=strategy_family` Finding per family clearing
`MIN_SAMPLE_ARTIFACTS`, alongside the original `scope_type=system` row —
additive, not a replacement. Caught and fixed a real belief-collision
risk before shipping: B already writes `scope_type=strategy_family`/
`scope_key=<family>` under the same `analyst_name`
(`regime_risk_coverage`), and `reflection_beliefs`' real primary key
(`analyst_name, scope_type, scope_key`) has no `metric_name` column, so a
plain family-name `scope_key` here would have silently overwritten B's
belief row for that family. Fixed with a distinct `scope_key`
(`f"{family}:paper_live_correlation"`) — same bug class Q hit and fixed
the same day.

**B, designed and built 2026-09-19**: the taxonomy design task this
file's ranked list called for. Confirmed `signal_definition` has no real
writer anywhere (empty on every real artifact, not just messy free text)
before ruling it out, then found `ResearchRunRecord.user_idea` as the
real, always-populated, short/descriptive field to classify instead.
Added `Artifact.strategy_family`, classified once at creation via the
new `vinu_research/strategy_family.py` (a small, fixed, keyword-based
taxonomy grounded in common systematic-trading style categories --
momentum, mean-reversion, breakout, volatility, stat-arb, event-driven,
plus an honest `unclassified` bucket), same "research external
convention, pick something grounded, document the reasoning" resolution
`03-severity-and-trend.md`/`04-reference-baseline-config.md` used for the
PSI-threshold questions. Built against `trade_audit_log.jsonl`'s real
exit rows (not `bench_history`, a per-artifact backtest series that
can't answer a per-real-trade cross-tab) joined to `Artifact.
strategy_family`/`regime_tag` via `artifact_id`. See
`regime_strategy_coverage.py`'s own docstring for the full reasoning,
including the real scope-downs (`ic` dropped, raw reward-to-variability
ratio instead of an annualized Sharpe).

---

## Where to continue, ranked

1. **S's spec** — needs a design pass with no existing precedent to
   build from. The only remaining item in the 25-analysis build itself.
2. **The step-8 "brain"** (`00-decided-pattern.md`) — a much bigger,
   separate component than `MaturityAssessor` (built 2026-09-20, see
   below): an LLM synthesis agent reading `reflection_beliefs` *and*
   Hindsight (which doesn't exist either), producing an undesigned
   "6-axis maturity profile," plus a self-trust-tracking loop over its
   own past suggestions. Deliberately not started without its own design
   pass first — building it as specced right now would mean inventing
   that design on the fly.

Q and N were fully resolved and built 2026-09-20 (see "How each
remaining group actually gets closed" above) — both turned out to have
a real answer once traced one level deeper than the "dependency-cost"/
"architecture-decision" framing this list previously carried them
under, rather than needing the open decision that framing implied.

The two items previously ranked #3/#4 here are also closed, same day:
**V's per-`strategy_family` breakdown** (built, once B gave
`strategy_family` a real taxonomy — see `02-regime-risk-coverage.md`)
and **`regime_analogue_enabled` turned on** (`docker-compose.yml`, both
`agent-api` and `research-api` — see `06-external-signal-cross-check.md`).
Neither was urgent, both were closed on explicit user sign-off rather
than left for later.

**T is also closed, same day**, once `MaturityAssessor`
(`00-maturity-agentic-system-explanation.md`'s small, fully-specified,
deterministic module — not the bigger step-8 "brain" above, a real
distinction this file initially missed) was built to unblock it. See
`06-external-signal-cross-check.md` for both.

The gap `02-analyst-interface.md` still flags as open — every analyst
writes, nothing yet reads `reflection_beliefs` on its own initiative the
way the step-8 brain eventually will — remains open. That's still
arguably a higher lever than S's spec, but it's the same big, separate
piece of work as item 2 above, not a quick win.
