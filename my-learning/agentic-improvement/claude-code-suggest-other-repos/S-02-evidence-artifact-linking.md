# S-02: Link Evidence to Real Run Artifacts, Not Just a Number

## What It Is

R-C fixed `Evidence.run_id` being hardcoded to `0` — it's now threaded through
from `service.py:128` (`run_id=record.id`) into `loop.py`'s `Evidence(...)`
construction (`loop.py:466`). That closes the traceability gap, but the evidence
record is still just `(run_id, iteration, metric, value, conclusion, reasoning)` —
a number and a sentence. If you want to know *why* a given iteration "contradicts"
the hypothesis, you have to go find run `run_id`, find the right iteration, and
hope the strategy code and backtest artifacts are still around.

Vibe-Trading's equivalent, `link_backtest()`
(`Vibe-Trading/agent/src/hypotheses/registry.py:269-307`), appends a dict carrying
`run_card_path`, `backtest_run_dir`, `metrics`, `notes`, `linked_at` — evidence
points at an actual artifact on disk, not just a derived sharpe float.

## Why It's Required

`vinu_research` already produces a `report_md` and full `BacktestResult` per
iteration (see `service.py`'s `ResearchRunRecord` and whatever run-card/report
artifact your backtest engine writes). Right now none of that is linked from the
`Evidence` record — the hypothesis registry's "why" is a one-line `critique.reasoning`
string, disconnected from the actual metrics/trades/equity curve that produced it.
When a hypothesis reaches `validated` or `rejected`, you should be able to click
through from "why" to the actual evidence, not just trust the label.

## Impact

- **If unfixed:** the hypothesis registry stays a *summary* of what happened, never
  a *pointer* to what happened — every non-trivial "why was this rejected" question
  requires manually correlating `run_id` + `iteration` against the SQLite run store.
- **If fixed:** `reject_with_reason()` and hypothesis inspection tooling (CLI, UI,
  or future LLM tool-use per S-10) can surface the actual backtest artifact behind
  each evidence entry — directly useful for debugging the exact contamination bugs
  described in S-01, and for any future human review of why a strategy was
  auto-rejected before it's fully trusted.

## How to Use Effectively

1. Extend `Evidence` (`models.py`) with two optional fields:
   `report_path: str | None = None` and `metrics_snapshot: dict[str, float] | None = None`.
   Keep them optional so existing evidence records (already on disk in
   `hypotheses.json`) still deserialize via `_from_dict()`'s `.get(..., None)` pattern.
2. In `loop.py`'s evidence-building loop (`loop.py:449-467`), populate
   `metrics_snapshot` from `rec.result.metrics` (a handful of fields: sharpe,
   max_dd, trade_count, win_rate — not the full metrics object, to keep the JSON
   file from bloating further, see S-03).
3. If a `report_md`/run-card path is available on `BacktestResult` or the calling
   `ResearchRunRecord`, populate `report_path` too — that's the direct analog of
   Vibe-Trading's `run_card_path`.
4. Don't try to link the *strategy code* itself into the evidence record — that's
   already retrievable via `run_id` → `ResearchStorage` → `IterationRecord.strategy_code`.
   Evidence should point, not duplicate.

## Implementation Hint — Where This Fits Today

**Important discovery: the artifact-linking machinery this suggestion asks for
already exists — it's just not called from the main research loop.**

- `HypothesisRegistry.link_backtest(hypothesis_id, run_card_path)`
  (`hypothesis_registry.py:163-175`) already does exactly what Vibe-Trading's
  `link_backtest()` does — appends a run-card path to the hypothesis and
  timestamps it.
- `tools.py:447-483`'s `link_autopilot_backtest()` already calls it: reads a
  `run_card.json` from a run directory, pulls `metrics` out of it, and calls
  `reg.link_backtest(...)`. It even auto-transitions the hypothesis to `testing`
  status on a successful link (`tools.py:476-479`).
- **The catch:** this is part of a separate, disconnected "autopilot" pathway
  (`tools.py`'s `run_autopilot()` / `generate_backtest_config()` /
  `scaffold_signal_engine()` / `link_autopilot_backtest()`, wired only to a CLI
  command at `cli.py:365-390`). It operates on hand-scaffolded template strategy
  code and a JSON `run_card.json` file it writes itself — it is **not** connected
  to `StrategyResearchLoop.run()`, the actual LLM-driven loop that P1-P4 modified.
  The main loop's evidence block (`loop.py:449-467`, the one R-C fixed) never
  calls `link_backtest()` at all.

**Two ways to close this, in increasing order of effort:**
1. **Cheapest:** don't chase the file-based `run_card.json` pattern at all — it
   only exists because the autopilot pathway writes one. For the main loop, just
   add `metrics_snapshot: dict[str,float] | None` directly to `Evidence`
   (as originally described above) and populate it inline from
   `rec.result.metrics` in `loop.py:449-467`. No file I/O, no new format.
2. **More thorough, reuses existing code:** have `loop.py`'s evidence block write
   a minimal `run_card.json`-shaped dict (doesn't need to hit disk — you can adapt
   `link_backtest()`'s signature to accept an in-memory dict instead of a path) and
   call the *already-written* `link_backtest()` — reusing the auto-transition-to-
   `testing` behavior `link_autopilot_backtest()` already has, instead of
   reimplementing it.

Either way, note `ResearchRunRecord.report_md` (`storage/models.py:26`) and
`ResearchResult.report_md` (`models.py:359`) are **inline markdown text stored in
SQLite**, not a filesystem path — so "artifact" here means a metrics dict, not a
file reference, unless you deliberately choose to start writing run-card files
from the main loop (option 2 above).

## Potential Bugs to Watch For While Testing

- **Old `hypotheses.json` records predate this field.** Every hypothesis written
  before this change has `Evidence` entries with no `metrics_snapshot`/
  `report_path`. `_from_dict()` must default missing fields (same `.get(key,
  default)` pattern R-A/R-C already used for `strategy_type`/`invalidation_reason`)
  — test loading a hypotheses.json fixture captured *before* this change and
  confirm it doesn't raise on missing keys.
- **If reusing `link_backtest()` (option 2), don't break the existing autopilot
  path.** `link_backtest(hypothesis_id, run_card_path)` currently expects a real
  string path (`tools.py:474` passes `str(run_card_path)`, and
  `link_autopilot_backtest()` checks `run_card_path.exists()` before calling it).
  If you widen the signature to also accept an in-memory dict, test that the
  *existing* CLI `autopilot` command still works unchanged — this is shared code,
  not a fresh function.
- **Don't double-write the same information two ways.** If both the new
  `Evidence.metrics_snapshot` field *and* a `link_backtest()` call get added, test
  that they're not writing overlapping/redundant data for the same iteration —
  pick one path per iteration's evidence, not both.
- **This adds write volume to an already-unlocked file (see S-03).** Each new
  field populated is more data serialized on every `add_evidence()` call — if
  S-03 hasn't landed yet, test this under two concurrent runs specifically (not
  just serially), since more writes per run means a wider window for the
  known race condition to actually manifest in a test run, not just in theory.
