Along the way, found and documented a real vocabulary mismatch between tags.yaml's regime labels and regime_analysis's actual labels — resolved with an explicit, documented mapping rather than a silent guess.

Deliberately not done: substep 5 (wiring to anything that moves real capital) — the new logic is on-demand only (GET /portfolio/daily-allocation + CLI), not started from entrypoint.sh, per the same "consequential actions stay manual" precedent already established elsewhere in this codebase.

Full suite: 1415 passed, 3 skipped, 0 failed across all 10 services (1382 baseline + 33 new). Both AGENTS.md and the Step 10 plan file are updated. Only substep 5 remains before Step 10 — and the entire 10-step plan — closes out.