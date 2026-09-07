# Other-Our-Repo Full Research Features — Index

> Folder: `other-our-repo-full-research-features/` inside `new-vision/`. Companion to `04-new-full-explanation.md` (vision), `pending-items-to-be-implemented.md` (16 gaps), and `05-other-repos-research.md` (18 repos ranked). Created 2026-09-07.

## What lives where

| File | Purpose | When to read |
|---|---|---|
| `01-pending-vs-outer-coverage.md` | 16 pending rows × 18 outer repos coverage matrix (covered / not covered / partial) | Before picking what to extract vs build custom |
| `02-adoptable-logic-catalog.md` | Beyond-16 adoptable features 17-26: source repo file → dest vinu file → effort → target pending row | Backlog for whole-app maturity after 16 are green |
| `03-per-repo-deep-dive/` | One file per high-value outer repo to actually extract (Qlib, Freqtrade, Nautilus, FinRL, VectorBT, PyPortfolioOpt) | When spiking that repo's logic — read only the one you need |
| `04-implementation-slices.md` | Slice plan A1-A6 (16) + Slice B (20/21/24 beyond-16): order, dependencies, acceptance, file:line | Implementation order — do not parallelize across dependency lines |
| `assets/` | `projects.yaml` snippet + star CSV snapshot Sep 2026 | Audit provenance of 05 ranking |

## Status vocabulary (used in all files)

- `pending` — not started
- `spiked` — logic examined in outer repo, not yet wired into vinu
- `wired` — code landed in vinu file, not yet tested end-to-end
- `green` — `04:` diagram stage passes with ledger evidence

## How to use this folder when implementing

1. Pick a row from `pending-items-to-be-implemented.md` (e.g. Row 5 sizing).
2. Check `01-pending-vs-outer-coverage.md` — is there outer coverage? If yes, open the repo's file in `03-per-repo-deep-dive/`.
3. Copy the `source → dest` mapping from `02-adoptable-logic-catalog.md` into your `Product Required / task.md` (Phase 0 style, not Phase 9).
4. Follow `04-implementation-slices.md` order — do not jump ahead (e.g. Row 2 replace needs Row 5 sizing first).

## Related docs

- `new-vision/04-new-full-explanation.md:1-421` — vision (7 stages + 2 entries + 4 cross-cutting)
- `new-vision/pending-items-to-be-implemented.md` — 16 shortcomings table
- `new-vision/05-other-repos-research.md` — 18 repos ranked by live stars
