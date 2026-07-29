# Index — Suggestions Extracted From Reference-Repo Audits

Source of these files: a deep, file-and-line-level audit of `vinu_research`'s P1–P4
agentic loop (memory injection, self-awareness, hypothesis brain, meta-intelligence),
cross-checked against `01-later-stage-01/R-A..R-E` (confirmed genuinely applied in the
code, not just documented — verified by reading current `loop.py`/`service.py`/
`hypothesis_registry.py`), plus a targeted comparison against three reference repos:

- **Vibe-Trading** (`personal-important/other-reference-repos/Vibe-Trading/agent/src/`)
  — almost certainly the actual source your P1–P4 vocabulary was adapted from
  (`Hypothesis`, `run_cards`, `Goal`, `memory` — identical naming). Materially more
  mature implementation of the same ideas. **Primary source for these suggestions.**
- **fincept-terminal** (`ref-fincept-terminal/fincept-qt/scripts/agents/`) — a few
  genuinely useful patterns (BM25-ranked memory, persona specialization, subagent
  task decomposition), but its own docs admit it's ~80% built, not finished.
- **FinRobot** — checked and mostly ruled out. Its "CoT news routing" README claim
  doesn't correspond to any real prompt in the code, and its multi-agent layer has
  no critic/reviewer role — your existing risk-critic already beats it. Not cited
  further in these files.

**Relationship to existing docs:** `00-vision.md` already defines 7 cognitive layers
(L0–L7) and `03-reference-patterns.md` already has a priority matrix with sketch-level
code. These files go one level deeper — concrete file:line evidence from the actual
mature implementation, not a sketch — and add several ideas neither existing doc
covers (trace/audit log, context-budget management, persona guardrails, native
function-calling, confidence scoring, live-trading kill switch). Where a file extends
an existing roadmap item, it says so explicitly.

## What's Already Done (verified in code, not re-suggested here)

| Bug (from first audit) | Fix doc | Verified in code at |
|---|---|---|
| Hypothesis keyed by symbol only, collides across strategies | `01-later-stage-01/R-A` | `loop.py:213-229` (strategy_type normalize+match) |
| Rejected hypothesis silently resurrected to validated | `01-later-stage-01/R-A` | `hypothesis_registry.py:186-195` (rejected guard) |
| Current run appears in its own "past runs" memory context | `01-later-stage-01/R-B` | `service.py:96-108` (query moved before insert) |
| Pivot path skips `on_iteration` callback | `01-later-stage-01/R-C` | `loop.py:388-391` |
| `Evidence.run_id` always 0 | `01-later-stage-01/R-C` | `loop.py:145,189,466` + `service.py:128` |
| AST-verification failures pollute evidence trail | `01-later-stage-01/R-C` | `loop.py:463` |
| Stock characterization ignores computed volatility/ADX | `01-later-stage-01/R-D` | `loop.py:862-873` |
| Suggestion-effectiveness tracking never matches (embeds live numbers) | `01-later-stage-01/R-E` | `loop.py:352,958-969` |

## Codebase Discoveries That Change Feasibility (read before picking a file)

While grounding each suggestion in exact file:line locations, three things turned
up that materially change how much new work several of these actually are —
**each S-file's own "Implementation Hint" section has the full detail**, this is
just the cross-cutting summary:

1. **A disconnected "autopilot" subsystem already implements half of S-02 and
   S-07.** `tools.py` has `run_autopilot()`, `generate_backtest_config()`,
   `scaffold_signal_engine()`, `link_autopilot_backtest()` (CLI-only, via
   `cli.py`'s `autopilot` command) that already build a `Goal` from a
   `Hypothesis` and already call `HypothesisRegistry.link_backtest()`
   (`hypothesis_registry.py:163-175`, itself pre-existing and unused elsewhere).
   None of this is wired into `StrategyResearchLoop.run()` — the actual LLM
   research loop P1-P4 modified. See S-02 and S-07 for what this means for each.
2. **`Goal` (`models.py`) already exists and is already used** — just not for
   budgets, and not connected to the main loop. See S-07.
3. **Live trading already exists as a real component** (`vinu-components/
   vinu-live/vinu_live/`, separate from `vinu_research`), and its actual order-
   submission code (`scheduler.py`'s `_execute_plan`, POSTing to
   `/broker/order`) has no halt/guard check in front of it — confirmed by direct
   grep, zero matches for `halt`/`guard`/`circuit_breaker`. This reframes S-12
   from "build before you need it" to "check whether this gap already matters."

## Suggestion Files, Priority-Ordered

| # | File | Layer (00-vision.md) | Effort | Impact | Status |
|---|------|------|--------|--------|--------|
| 1 | [S-01-hypothesis-identity-still-fragile.md](S-01-hypothesis-identity-still-fragile.md) | L3+L7 | Low | 🔴 High | Residual gap in R-A |
| 2 | [S-02-evidence-artifact-linking.md](S-02-evidence-artifact-linking.md) | L1+L3 | Low | 🔴 High | New |
| 3 | [S-03-batched-evidence-writes-and-locking.md](S-03-batched-evidence-writes-and-locking.md) | L3 | Low | 🟠 Med-High | Residual gap (not in R-A..E) |
| 4 | [S-04-two-tier-memory-with-relevance-ranking.md](S-04-two-tier-memory-with-relevance-ranking.md) | L3 | Medium | 🔴 High | New |
| 5 | [S-05-trace-writer-audit-log.md](S-05-trace-writer-audit-log.md) | L1 | Medium | 🟠 Med-High | New |
| 6 | [S-06-context-budget-and-graceful-stop.md](S-06-context-budget-and-graceful-stop.md) | L5 | Medium | 🟠 Med-High | New |
| 7 | [S-07-goal-budget-and-compliance-object.md](S-07-goal-budget-and-compliance-object.md) | L7 | Medium | 🟠 Medium | Extends existing roadmap item |
| 8 | [S-08-decay-monitoring-state-machine.md](S-08-decay-monitoring-state-machine.md) | L4 | Medium | 🟠 Medium | Extends existing roadmap item |
| 9 | [S-09-persona-guardrails-per-llm-role.md](S-09-persona-guardrails-per-llm-role.md) | L1-L7 (cross-cutting) | Low | 🟡 Medium | New |
| 10 | [S-10-native-function-calling.md](S-10-native-function-calling.md) | L6 | High | 🟠 Med-High | New, alt. to existing L6 sketch |
| 11 | [S-11-confidence-scoring-on-judgment-calls.md](S-11-confidence-scoring-on-judgment-calls.md) | L5+L7 | Low | 🟡 Medium | New |
| 12 | [S-12-live-trading-kill-switch.md](S-12-live-trading-kill-switch.md) | (pre-live-trading) | Medium | 🔴 High (once live) | New, no current analog |
| 13 | [S-13-refresh-strategy-integration-gap.md](S-13-refresh-strategy-integration-gap.md) | L2-L5 (cross-cutting) | Low | 🟠 Medium | Residual gap |
| 14 | [S-14-zero-test-coverage.md](S-14-zero-test-coverage.md) | (all) | Medium | 🔴 High | Residual gap |

**Suggested next batch (highest ROI, lowest effort first):** S-01, S-03, S-13 (all
small, close remaining correctness/integration gaps) → S-02, S-04 (biggest capability
upgrade for the effort) → S-14 (protects everything above from regressing).
