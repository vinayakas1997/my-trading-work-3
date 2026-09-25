# System-wide audit and design — the whole pipeline, not just the 29th angle

**This folder exists so the big picture doesn't get mixed into
`../how-to-use-29th-angle/`, which is deliberately scoped to just Track 1
and Track 2.** Everything here spans multiple components across the full
6-layer pipeline (screener → data/analysis → hypothesis/validation →
strategy execution → portfolio risk → live execution), not just the 29th
angle's own mechanism.

## Files in this folder

- `00-overview.md` — this file.
- `01-full-system-layer-map.md` — the full 6-layer system sequence, with
  real citations for what each layer does, `vinu-reflection` as a
  cross-cutting feedback loop (not a sequential step), infrastructure vs.
  pipeline stages, a mermaid diagram, and the "three disconnected
  evidence streams" pattern finding.
- `02-open-questions-strategy-and-simulation.md` — the full audit series:
  26 items covering strategy-definition design questions, a real code
  audit of every layer in the pipeline (`vinu-screener`, `vinu-stock-price`/
  `vinu-news`, `vinu-tools`, `vinu-agent`, `vinu-research`,
  `vinu-simulator`, `vinu-strategy`, `vinu-portfolio`, `vinu-live`),
  cross-service seam issues, cross-cutting patterns found by comparing
  findings against each other, a cross-check against prior recorded
  expectations (the `maturity-agentic-system` and `high-expectations`
  folders), and a final honest assessment of where the whole system's
  components are and aren't actually connected. This is the largest file
  in this folder by far and the one most likely to keep growing.
- `03-strategy-definition-full-schema.md` — the complete strategy
  definition field list: must-condition/indicator "why," a link to
  `HypothesisRegistry`, explicit risk management, precondition/
  postcondition (mirroring Track 2's PRE/POST from the 29th-angle
  folder), a two-level failure definition, a performance-record
  reference, and origin/versioning.

## How this folder relates to `../how-to-use-29th-angle/`

That folder explains one specific mechanism (the 29th angle) in full.
This folder is everything that mechanism connects to, or should connect
to, or was found not to connect to — the rest of the pipeline, the
audits of each component, and the design questions that span more than
one component at once. Cross-references between the two folders use
relative paths (`../how-to-use-29th-angle/...` and vice versa).

## Status of everything in this folder

Nothing in this folder has been implemented. It is entirely design
records and audit findings, verified against real code at the time each
item was written (dates given per item), kept in full detail on purpose
per standing instruction — this is meant to be read and acted on in the
future, not summarized away.
