All three workstreams are done, and the vinu-research suite went from broken (207 passing, 7 modules couldn't import) to 349 passed, 0 failed on Windows.

What was fixed
Portability + test fixes

hypothesis_registry.py — removed the Unix-only fcntl lock rather than emulating it: the lock was taken on a private freshly-created temp file no other process could contend for, so it provided no protection; the real atomicity comes from os.replace, which is kept. This one import was cascading through tools → loop → service → server, blocking 7 test modules.
sqlite_backend.py — two real bugs the suite exposed: list_runs ordering now tie-breaks on id DESC (same-tick inserts returned oldest-first), and update_run guarantees updated_at advances even on coarse Windows clocks.
Angle integration (your foundation now feeds the research loop)

New angle_context.py — pure compactor that takes the raw /angle/{name}/{ticker} records (which include every historical run), selects the latest run by stored_at (run_ids are random uuids, so file order lies), filters by the research time format, strips NaN, and reduces to a small dict. Session structure falls back to any intraday format (labeled) so daily research still sees it.
tools.py — get_angle_rows + get_angle_context fetch trend_lifecycle, trend_session_structure, and news_price_causality concurrently.
loop.py — the story dict is enriched with story["angles"] before caching (no signature changes anywhere, so custom critics keep working). The rule-based critic now emits deterministic suggestions from it: high reversal risk → trailing-stop suggestion with the pattern library's exit threshold; Granger causality present → news filters may add edge (or the inverse warning); worst-drawdown session → session filter suggestion. Suggestions only — verdict logic untouched, so the loop's PASS/REFINE/STOP behavior is unchanged.
llm.py — the risk-critic prompt gets a "Deterministic Angle Analysis" section: trend stage/risk/signal, per-session stats (floor-qualifying only), news causality.
Tests + doc — 11 new tests (compactor latest-run/time-format/NaN behavior, intraday fallback, prompt rendering); new-direction doc section 3 rewritten from "NOT STARTED" to the audited reality, including the angle-trim decision and the remaining work list.

What I'd flag for next
The exploration surfaced one thing worth knowing: the LLM strategy generator (llm_generator.py) still builds its prompt from only the user idea + dates — angle context reaches the critic but not the generator. That's the natural next move, along with an end-to-end loop run against real angle data (needs the four services up), and eventually the Python-vs-YAML approved-strategy decision. All three are recorded in the doc so nothing gets lost.