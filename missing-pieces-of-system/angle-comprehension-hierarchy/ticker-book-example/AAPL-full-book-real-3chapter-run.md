# AAPL — real, live 3-chapter run (all real, no hand-authored chapters)

This is the first time all 3 chapters were produced end-to-end by a real
live model against real (fabricated-but-structured) data, rather than
any chapter being hand-written. Supersedes the original `AAPL.md`'s
Chapter 2-3 for the comprehension question — those were written by me;
these were written by `hindsight-llm` (Qwen3.5-9B-Q4_K_M), 2026-09-22.

## Pipeline actually run

1. **Chapter 1** (index): `gen_full_book.py` — 28 real angles, every one
   at every one of its own real `time_formats`, clean + deliberately
   uneven variants. Unchanged from the earlier single-shot test — see
   `AAPL-full-28angle-clean.md`/`AAPL-full-28angle-uneven.md`.
2. **Chapter 2** (comprehension), **split-cluster design**: 7 separate
   calls, one per cluster, each scoped to ONLY that cluster's own real
   angle list (`run_split_cluster_test.py`). This replaced the earlier
   single-shot-all-28 design after real testing showed the split design
   structurally prevents cross-cluster hallucination (zero occurrences
   across all 14 calls, vs. one confirmed violation in the single-shot
   9B run) and gets the coverage count exactly right on the clean
   dataset (7 of 7 clusters correct, vs. single-shot's 0 of 2 runs
   correct) — see `03-real-llm-findings-and-guardrails.md` for the full
   comparison. Real results: `split_cluster_results_clean.json`,
   `split_cluster_results_uneven.json`.
3. **Chapter 3** (cross-analysis), first real run: takes Chapter 2's 7
   real synthesis sentences (only the sentences — no raw per-angle data)
   and asks: which clusters genuinely corroborate each other, which show
   no real cross-timeframe change, what does that mean for a downstream
   decision. `run_chapter3_test.py`. Real results: `chapter3_result_
   clean.json`, `chapter3_result_uneven.json`.

All calls: `temperature=0.2`, `chat_template_kwargs: {enable_thinking:
false}` (not a real production setting — see checkpoint 01's finding on
why thinking-enabled doesn't reliably converge).

## Real Chapter 3 output (clean dataset)

> Corroboration found: **Cluster B + Cluster D** — Cluster D's "bullish
> regime and uptrend lifecycle signals across 1min to 1M" independently
> matches Cluster B's "transition from flat... to consistent upward
> trends... at 1H and 1D." Redundant clusters: **C, E, F, G**.
> Verdict: "a single, high-confidence bullish signal corroborated by
> regime and trend clusters, while the remaining clusters provide
> static or stale data that adds no directional value."

## Real Chapter 3 output (uneven dataset)

> Corroboration found: **Cluster A + Cluster D** this time (not B+D).
> Redundant clusters: **C, E, F, G** (same set, with Cluster C's
> redundancy specifically reasoned as "primarily a data integrity note"
> given its propagated GARCH-NaN issue from Chapter 2 — a sensible,
> cautious read of an already-imperfect input, not compounding the
> error).

## Verdict — real, verified

**No fabrication at the Chapter 3 stage itself.** Every quote Chapter 3
used to justify its corroboration claim traces back verbatim or
near-verbatim to the real Chapter 2 sentence it was given — checked
directly, not assumed. Redundant-cluster calls (C/E/F/G) are accurate:
those clusters really are at-or-near byte-identical across timeframes in
this data, matching the original hand-authored `AAPL.md` example's own
finding for the same clusters, arrived at independently.

**One real limitation, found by comparing the two runs side by side**:
Cluster A's real sentence shows the *same* bullish-strengthens-with-
horizon pattern as B and D in both runs, but Chapter 3 only ever
surfaced 2 of the 3 relevant clusters — B+D on the clean run, A+D on the
uneven run, dropping B that time even though its input sentence still
showed the pattern. Not a hallucination (nothing stated was false) —
an incompleteness, and a real inconsistency between two very similar
inputs, worth knowing before treating any single Chapter 3 run as
exhaustive. A real candidate fix, untested: explicitly prompt Chapter 3
to check every cluster pair rather than stopping once one corroboration
is found.

## Real cost

Chapter 2 (split, 7 calls) + Chapter 3 (1 call), clean dataset: 34.6s +
15.0s ≈ **50s total**. Uneven: 33.9s + 13.8s ≈ **48s total**. Full
3-chapter pipeline, real model, real data, under a minute per ticker.
