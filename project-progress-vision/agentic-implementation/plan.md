# Merged Build Order — Strategy-Validation Pipeline & Unified Storage

This plan merges [01-vision-plan](../01-vision-plan/) and [02-storage-memory](../02-storage-memory/) into a single execution sequence. The key insight: 01-vision-plan's Phase 3 (structured iteration storage) and the storage half of its Phase 1 (Monte Carlo persistence) are replaced by 02-storage-memory's Phase 2 (research/simulator catalog). Building them first and migrating later is pure waste.

Also, 02-storage-memory Phase 1 is split into two parts: hardening `vinu-lib`'s primitives (Step 1 — fast, low-risk, everything else depends on it) vs. migrating stock-price/news onto them (Step 5 — valuable cleanup, nothing blocked on it).

---

## Build Sequence

| Step | Phase | What It Delivers | Depends On |
|------|-------|------------------|------------|
| 1 | Harden vinu-lib's SQLiteBackend/ParquetStore | Review-and-fill-gaps: composite-key dedup, upsert helpers, sharded/consolidatable parquet writes. Isolated to `vinu-lib` + its own tests. | — |
| 2 | Build research/simulator catalog + iteration-checkpoint tables | Catalog table (`research_catalog`), checkpoint table (`research_jobs`/`iteration_checkpoints`) on top of Step 1's hardened primitives. Delivers what 01-vision-plan Phase 1's storage and Phase 3 were separately trying to build. | Step 1 |
| 3 | Monte Carlo validation algorithms | Pure math: `block_bootstrap_permutation`, `price_path_resample`, `compute_validation_verdict`. No storage dependency — can be built in parallel with Steps 1–2. | — |
| 4 | Wire Monte Carlo gate into research loop | `StrategyResearchLoop` enforces validation verdict. Uses Step 2's checkpoint table for resumability. | Step 2, Step 3 |
| 5 | Migrate stock-price & news onto vinu-lib | Both packages adopt `SQLiteBackend`/`ParquetStore` without behavioral change. Can happen in parallel with Steps 3–4. | Step 1 |
| 6 | Comparative critique agent (Stage 2) | Cross-run reasoning over Step 2's iteration history catalog. First use of lifetime data across runs. | Step 2, Step 3 |
| 7 | Unified agent-memory layer | Cross-package memory catalog aggregating price/news/research summaries. Cleanest if Step 5 has landed, but reads through existing API either way. | Step 5 (preferred), Step 2 |
| 8 | Trading playbook synthesis (Stage 3) | Entry/exit checklists, drawdown-by-regime, long/short split, news-sensitivity handling, time-of-day guidance. Extends `TradePlanTool`. | Step 3, Step 6 |
| 9 | Context-efficient retrieval + overfitting/robustness | Two parallel tracks: retrieval patterns for agent memory (needs Step 7) + overfitting correction using `lifetime_trial_count` (needs Step 2). | Step 7, Step 2 |
| 10 | Portfolio correlation gate | Cross-strategy correlation check before promotion. Reads from catalog. | Step 2 |
| 11 | Integration testing | End-to-end pipeline tests. All prior phases must ship first. | Steps 1–10 |
| 12 | Shadow/live validation "Stage 4" | Continuous re-validation using `last_validated_ts` watermark for decay detection. | Step 2 |
| 13 | Judgment quality & cost realism | LLM judgment calibration, cost tracking, token efficiency. | All prior |

---

## Superseded / Dropped Phases

The following phases from the original vision documents are **replaced** by steps above — do not implement:

| Original Phase | Replaced By | Reason |
|----------------|-------------|--------|
| 01-vision-plan Phase 3 (structured iteration storage) | Step 2 (catalog + checkpoint tables) | Step 2's design is stronger — resumable checkpoints, lifetime trial counts, watermark — and is built on hardened `vinu-lib` primitives from the start |
| 01-vision-plan Phase 1 storage half (validation/symbols columns in `simulation_runs`) | Step 2 (catalog) | Same reasoning: build on the proven catalog+watermark pattern once, not as a bespoke table that gets migrated later |

---

## Parallelization Opportunities

- **Steps 1 + 3** can run in parallel (storage infra vs. pure math — no shared dependency)
- **Steps 3 + 5** can run in parallel (Monte Carlo algorithms vs. stock-price/news migration — independent)
- **Step 9** can split into two parallel sub-tracks after Step 7 and Step 2 are done

---

## Files Touched, by Service (Cumulative)

| Service | Phases |
|---------|--------|
| `vinu-lib/` | 1, 5 |
| `vinu-simulator/` | 2, 3, 4 |
| `vinu-research/` | 2, 4, 6 |
| `vinu-stock-price/` | 5 |
| `vinu-news/` | 5 |
| `vinu-agent/` | 8 |
| New cross-package memory module | 7 |
