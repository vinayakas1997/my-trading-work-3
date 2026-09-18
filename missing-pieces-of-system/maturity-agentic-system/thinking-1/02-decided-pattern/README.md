# 02-decided-pattern — reading guide

This folder is the **settled design** for the maturity-agentic system
(55 raw stores → 25 analyses → 6 analysts → shared schema → one brain).
Everything here is design/specification — **nothing in this folder has
been implemented.** The earlier, exploratory conversation that led to
these conclusions now lives at
`personal-important/01-discussions-to-reach-conclusion/` (moved out of
this folder deliberately — it's the reasoning trail, not the settled
result; this folder cites it where a decision's full justification
lives there instead of being repeated here).

See also `project-understanding/deeper-why-this-concepts/concept-1.md`
for the plain-language "why 55 → 25 → 6" explanation, and
`../maturity-agentic-system-explanation.md` for the original
`MaturityAssessor` design this whole thing grew out of.

## Read in this order

1. **`00-decided-pattern.md`** — start here. The full 9-step narrative,
   end to end, in plain language: raw stores → joins → analysts → the
   gate → SQLite → Hindsight (all three bank types) → Graphiti
   (reserved, not built) → the brain → consumers. Includes a mermaid
   diagram and one fully worked 5-ticker example tracing a per-ticker
   finding, a pair finding, and a system-scoped finding through the
   whole pipeline. Read this before anything else in the folder.

2. **`01-table-schemas.md`** — the 3 real tables (`reflection_findings_history`,
   `reflection_beliefs`, `reflection_synthesis_outcomes`), all 24
   columns, what each one means. What decided-pattern.md's step 5 and
   step 9 actually get written to disk as.

3. **`02-analyst-interface.md`** — the code shape: the `Finding` dataclass,
   the `run(data_root_paths, service_clients) -> list[Finding]`
   signature every analyst implements, the worker loop, and which
   clusters need real `service_clients` (HTTP) vs. which are colocated
   — checked directly against the real `docker-compose.yml` mounts, not
   assumed.

4. **`03-severity-and-trend.md`** — how the two schema fields nothing else
   explains (`severity`, `trend`) actually get computed: reuses the
   Population Stability Index (PSI), a real external convention, not an
   invented scale. Read this if you're wondering "who decides if a
   finding is routine/notable/significant."

5. **`04-reference-baseline-config.md`** — the missing inputs PSI needs to
   actually run: what counts as the "expected" baseline distribution per
   metric, how many bins, and — the one most worth knowing —
   `metric_polarity`, since PSI alone can tell you *how much* something
   moved but never *which direction* is good or bad.

6. **`25-A-Y-details/`** — the full per-analysis specification, one file
   per analyst cluster (`00-index.md` first, then `01`–`06`). Every one
   of the 25 analyses (A–Y, including H) scoped down to real column
   names, the actual join, the significance condition, and the storage
   shape. `data-driven-analysis-opportunities.md` (same subfolder) is
   the original master list these 25 were first proposed in — read it
   only if you want the original "what it buys" reasoning behind a
   specific letter; the cluster files are the authoritative, current
   spec.

7. **`05-to-do.md`** — read last. The 8 concrete gaps still standing
   between this design and buildable code, with a clear "what actually
   unblocks building today" closing section. **All 8 items are now
   closed** — the only remaining next step is implementation, starting
   with #1 (Layer 0 schema) and analysis D alone.

## What's already provably correct, not just asserted

Every file above has been cross-checked at least once against real
code — `llm_calls.py`'s actual columns, the real `docker-compose.yml`
mounts, the real 55-store catalog
(`project-understanding/05-full-recorded-information/README.md`) — and
against each other, for internal consistency (matching `scope_type`
enums, matching ownership tables, no dangling references to relocated
files). Two real content gaps were found and fixed this way: analysis
**H** had fallen out of every cluster assignment (now in Governance &
Freshness), and `00-decided-pattern.md`'s step 6 was missing the
system-process Hindsight bank type entirely (now fixed, with a diagram
and worked-example update to match).
