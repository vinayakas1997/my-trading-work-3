# Decision — Row 6 Single-voice self-verdict (accepted risk 2026-09-07)

> `04:253-255` single voice vs bull/bear debate. Decided to keep single-voice with explicit mitigations, not build adversarial debate now.

## Decision

- Keep `StrategyResearchLoop` single-voice self-verdict `critic_feedback` `PASS/FAIL` using `pbo.py` + `walk_forward stability` + `completeness` fail-closed (`loop.py:352` trade count, `comparison.py` DSR). Cost-control rationale `04:253` outweighs debate overhead for current stage.

## Mitigations already in place (why accepted)

- `PaperRehearsalResult` (Row 1) bar-by-bar 7-day rehearsal before gate — catches rehearsal degradation even if verdict permissive.
- `HoldoutResult` trailing 20% never-seen slice + `WalkForwardResult` 3 windows + `StressTestResult` crisis windows — already provide ensemble OOS signals.
- `PBO` `probability_of_backtest_overfitting` across iterations — multiple-testing correction same family as DSR.
- `pypfopt` not needed here; FinRL 5-agent bake-off (adoptable Row 23) remains enhancement backlog for future spike.

## When to revisit

- If PASS rate >30% with holdout fail >20%, revisit bull/bear debate or risk_officer gate.

## Status

- Accepted risk in writing 2026-09-07, not a build.
