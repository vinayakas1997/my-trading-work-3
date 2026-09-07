# Full Pattern — Scope (7 stages + 2 entries + 9 edges, Gate)

> Same 7 stages + 2 entry points as ATS but with **full window `2022-01-01`** so `deflated_sharpe 0.95`, `holdout 20%`, `walk_forward 3`, `PBO`, `stress 2020/2022`, `composition_view`, `cycle_shock_batch`, `freeze` drift, throttle, observed halt/Triage are trustworthy for go-live per `04-v2` + `pending Status`.

## What Full checks beyond ATS

- Golden path one ticker no failures → `PEND→ACTIVE` → `Live+Shadow` → `Monitor hold`
- 9 edges ×2 tickers: sweep `FAIL`→re-propose with prior_rejections, `REJECTED`→`SIG`+`P`, Kill `PEND→PENDBLOCK`, Triage near-duplicate cheap discard before LLM, K-cap shared, rebalance `REQUEST` vs Monitor race, decay→`HR`→next `P` reads it, batch NEW-vs-NEW corr (`other-our-repo-full-research-features/04-implementation-slices.md`).
- Cross-cut `TickerLedger` retention `90d/1M` `decisions/10`, `skill-edit audit log` ticker-agnostic, `Calibration Tracker` spiked, `env_file` accepted risk, tick wallet still spiked.
