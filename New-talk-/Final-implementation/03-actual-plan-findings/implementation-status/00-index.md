---
name: implementation-status-index
status: all-phases-done
purpose: live tracker for actual code changes made to vinu-components against the plan (02-api-design.md, 03-storage-design.md, 05-angle-reconciliation.md). One file per component. Updated as work lands, not written up front.
---

# Implementation Status — Index

This folder tracks what's actually been changed in the real
`vinu-components/` codebase, component by component, as the plan gets
built out. `04-build-status.md` and `05-angle-reconciliation.md` (one
level up) are the starting snapshot — this folder is the delta from that
snapshot forward.

**All 6 phases are complete and independently verified** (every
background agent's report was re-checked with a separate full test-suite
run before being trusted — see each component file's "Tested" sections).

## Components

| Component | Status | Summary |
|---|---|---|
| [vinu-infra](01-vinu-infra.md) | Done | Added `require_data_root()` — the shared no-fallback root resolver every component now uses. |
| [vinu-news](02-vinu-news.md) | Done | Required data root, renamed DB, fixed a dual-db-path bug. All 9 Section-1 methods built (`analysis/methods/`). New `/v1/stage1/vinu-news/{fetch,trigger}/.../{method}` API. Tested: 122/122. |
| [vinu-stock-price](03-vinu-stock-price.md) | Done | Required data root, renamed DB. Daily-shard storage already existed (audit correction). New `/v1/stage1/vinu-stock-price/{fetch,trigger}/...` API. Tested: 40/40. |
| [vinu-initial-analysis](04-vinu-initial-analysis.md) | Done | Full storage-path redesign (`{granularity}`/`{tier}`/`_multi`), tier-aware pruning, `garch` extracted, `ml_model_pipeline`/`news_first_analysis` deprecated, all 22 remaining price-dependent methods built (35 angles total), registry consolidated, new `/v1/stage1/vinu-initial-analysis/{fetch,trigger}/.../{method}[/{run-id}]` API with real tier2/tier3 separation. Tested: 194/205 (11 pre-existing unrelated failures). |
| [vinu-tools](05-vinu-tools.md) | Untouched, as planned | Reuse-only — `garch`'s angle calls straight into its existing `garch_volatility` function; no changes needed. |

## Phase map — all done

1. **Foundation** — required env-var data roots, consistent DB naming,
   `vinu_infra.sqlite.SQLiteBackend` reuse everywhere, fixed the mtime
   "latest run" bug.
2. **vinu-stock-price storage conformance** — turned out to already
   exist (audit correction); `ParquetStore` adoption deliberately
   skipped as unnecessary churn on working code.
3. **vinu-initial-analysis storage path shape** — `{granularity}`/`{tier}`
   segments, `_multi/` branch, tier-aware pruning that actually enforces
   immutability in code.
4. **Angle reconciliation execution** — `garch` extracted as a
   standalone angle; `ml_model_pipeline`/`news_first_analysis` marked
   deprecated in place (not deleted — a deliberate, documented choice,
   see `04-vinu-initial-analysis.md`).
5. **The 32 planned methods** — all built: 9 news-only methods in
   vinu-news, 23 price-dependent methods in vinu-initial-analysis (3
   classical stats, 7 trained-from-scratch neural, 12 foundation
   models/fusion architectures — 2 genuinely pretrained via HuggingFace,
   the rest honestly labeled `fallback_proxy` with documented reasons,
   never faked).
6. **API redesign** — the `/v1/stage1/{component}/{action}/...` pattern
   live across all 3 components, additive alongside each component's
   existing routes. Two real bugs (tier propagation, tier-scoped
   polling) caught and fixed via independent verification before being
   trusted.

## Related files

- `../04-build-status.md` — the pre-change audit this tracker is measured against
- `../05-angle-reconciliation.md` — keep/remove/upgrade decisions for the 12 original angles
- `../02-api-design.md` / `../03-storage-design.md` — the target shape every phase converged on
