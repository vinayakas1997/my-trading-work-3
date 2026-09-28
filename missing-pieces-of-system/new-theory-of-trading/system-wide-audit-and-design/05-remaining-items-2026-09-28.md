# Remaining items (2026-09-28) — explicitly left, not forgotten

Everything else this audit series flagged as a real gap was built and
tested this session (see `04-synthesis-built-vs-missing-2026-09-28.md`
for the full list, and `02-open-questions-strategy-and-simulation.md`
for each item's own dated UPDATE with citations and test counts). These
three are the ones deliberately left open, on record, by explicit
choice — not oversights.

## 1. Agent↔research contract-version stamp (the other half of item #17)

The research↔simulator hop already got a deterministic schema-version
stamp (`vinu_infra.contract_version.contract_version()`, echoed on every
`CustomSimulateResponse`, pinned in `vinu-research/tests/
test_simulator_contract.py`). The agent↔research hop
(`RunResearchRequest`/`SweepCandidateRequest`) is the identical pattern
— same shared helper, same "receiving service echoes its own version,
sender-side test pins it" shape. Small, mechanical, no new design
decision needed.

## 2. Indicator-duplication root cause (item #20.6)

Every individual instance of the duplicated-ADX/RSI/ATR pattern has now
been fixed or confirmed a deliberate non-fix (item #21 pattern #2,
closed 2026-09-28). What's still open is the *cause*, not a symptom:
there's no single documented, enforced "blessed" import path
(`get_indicator_module()`) for indicator math in this codebase, which is
the reason the same mistake happened independently four times. Fixing
this means making that path actually discoverable — documented in
`AGENTS.md`, possibly a lint/check — so a fifth instance doesn't happen
the same way later.

## 3. `trade_plan_tool.py` test coverage (the last file from item #11 finding #2)

1330 lines, ~24 methods spanning rendering, prospective fact-checking,
and journal scheduling. Every other zero-coverage file item #11 named
now has real tests; this one is genuinely its own session-sized piece of
work, not a same-pass mechanical add.

---

Pick any of these up later by referencing this file — each one is a
complete, scoped, buildable unit on its own.
