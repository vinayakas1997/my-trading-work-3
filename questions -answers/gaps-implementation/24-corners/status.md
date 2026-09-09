# Status - 24-corners

Date: 2026-09-09
State: doing (Sec1+Sec2 done, Sec3-5 pending)
Owner: agent build
Doing: entrypoints + scripts verified. Next indicators + test map + cleanup.
Done:
- Sec1: entrypoints wired agent/live/portfolio/research, verified files.
- Sec2: run_pipeline.py --help works, setup-secrets.sh --check all present.
Bugs found while implementing: none, verify only.
Other files touched: none (verify only).
Next: Sec5 cleanup.
Done2:
- Sec3 indicators decided: 15 BUILTIN_RECIPES are the backtest-safe set, catalog angles 27/28 separate.
- Sec4 test map (knob->test): SWEEP_INTERVALS->test_config, USE_VECTORBT->test_sweep_grid, HYPEROPT->test_sweep_grid cap, DIVERSITY->comparison tests, TOP_N->writer check, PAPER_DAYS->test_shadow, DD_HALVE/FLAT->test_circuit, PROVIDER_ORDER->provider tests, SPREAD/QUEUE->cost tests, LESSON_MIN->feedback tests, MUTE->significance tests, DECAY_RATIO->scheduled tests, HALT/COOLDOWN->orchestrator tests, INTERVALS order->test_config.
Done3: map verified against test files present.
