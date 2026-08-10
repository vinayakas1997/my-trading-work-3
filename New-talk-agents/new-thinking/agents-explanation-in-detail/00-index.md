---
name: agents-explanation-in-detail-index
status: proposed-not-built
purpose: index and quick-reference table for the 8 per-team detail files in this folder -- each team's full internal breakdown (sub-agents, scope, real/drafted prompts, mermaid flow, final-answer shape) lives in its own file; this file is the map.
---

# Agents, explained in detail — index

Each file in this folder covers one team completely: who's on it, what
it's responsible for (and explicitly not responsible for), every prompt
(verbatim where the team is real and built, carefully drafted where it's
proposed), a mermaid diagram of its internal flow, and exactly what its
final answer must contain. Higher-level reasoning about *why* this
roster looks the way it does — the reference-repo research, the shared
mechanisms, the open decisions — lives one level up in
[../think-1.md](../think-1.md); this folder is the concrete,
per-team-mechanical companion to that document, not a replacement for it.

## Quick reference

| # | File | Team | Specialists | Status | Trigger |
|---|------|------|:---:|--------|---------|
| 1 | [01-screener.md](01-screener.md) | `screener` | 1 | **built, tested against a real LLM** | `delegate_to_team`, in-conversation |
| 2 | [02-research.md](02-research.md) | `research` | 3 | **built** | `delegate_to_team`, in-conversation |
| 3 | [03-strategist.md](03-strategist.md) | `strategist` | 1 | proposed | `delegate_to_team`, in-conversation |
| 4 | [04-strategy-lab.md](04-strategy-lab.md) | `strategy_lab` | 5 | proposed | `delegate_to_team`, in-conversation |
| 5 | [05-risk-gatekeeper.md](05-risk-gatekeeper.md) | `risk_gatekeeper` | 1 | proposed, blocked on real position data | `delegate_to_team` or non-interactive, not decided |
| 6 | [06-capital-allocator.md](06-capital-allocator.md) | `capital_allocator` | 1 | proposed, **least fleshed out — allocation math undecided** | `delegate_to_team`, in-conversation |
| 7 | [07-trade-monitor.md](07-trade-monitor.md) | `trade_monitor` | 1 | proposed, blocked on real position data + shadow ledger | **external scheduler**, `TeamManager` direct, not `delegate_to_team` |
| 8 | [08-post-trade-review.md](08-post-trade-review.md) | `post_trade_review` | 1 | proposed, blocked on shadow ledger + point-in-time angle history | **real position-close event**, `TeamManager` direct, not `delegate_to_team` |

**14 specialist roles total** across the 8 teams (1+3+1+5+1+1+1+1).
`strategy_lab` alone accounts for 5 of them — it's the merge of what were
originally three separate team ideas (enhancer, risk debate, paper-trade
rehearsal), see its own file for why merging was the right call.

## The whole system in one diagram

```mermaid
flowchart TB
    RESEARCH["research (built)<br/>3 specialists"] -.->|"validated idea, optional"| STRATEGIST

    SCREENER["screener (built)<br/>1 specialist"] --> STRATEGIST["strategist<br/>1 specialist"]
    STRATEGIST --> LAB["strategy_lab<br/>5 specialists<br/>(enhancer, bull, bear,<br/>risk_officer, paper_trader)"]
    LAB -->|"reject -- rework"| STRATEGIST
    LAB --> GATE["risk_gatekeeper<br/>1 specialist"]
    GATE -->|"reject -- rework"| STRATEGIST
    GATE --> ALLOC["capital_allocator<br/>1 specialist<br/>(sees ALL approved candidates<br/>at once, not just this one)"]
    ALLOC --> EXEC[("Phase 6 execution<br/>-- broker, outside vinu-agent")]

    EXEC --> MONITOR["trade_monitor<br/>1 specialist<br/>-- external scheduler trigger"]
    MONITOR <-.->|"get_position_comparison"| SHADOW[("shadow_ledger<br/>-- deterministic, no LLM,<br/>runs continuously, not a team")]
    MONITOR -->|"position closes"| REVIEW["post_trade_review<br/>1 specialist<br/>-- position-close event trigger"]
    REVIEW <-.->|"get_shadow_ledger_history"| SHADOW
    REVIEW -->|"lessons"| MEM[("per-symbol memory ledger<br/>-- not a team"), style: shared]
    MEM -.->|"must consult before proposing"| STRATEGIST
```

## Two things every file in this folder assumes you already know

1. **Not a fixed DAG.** Every manager here can loop — delegate, read the
   result, decide what to do next, possibly delegate again — rather than
   walking a static graph with no judgment in the middle. `research` and
   `strategy_lab` actually use their loop; `screener`, `strategist`,
   `risk_gatekeeper`, `capital_allocator` are structurally simple enough
   that in practice they usually run once through, but the mechanism is
   the same `AgentLoop`-based manager either way, not a special
   "simple team" code path.
2. **Two teams (`trade_monitor`, `post_trade_review`) don't use
   `delegate_to_team` at all.** Nothing about "check on an open position"
   or "a position just closed" is triggered by someone chatting with the
   orchestrator, so these two are invoked by constructing `TeamManager`
   directly from outside vinu-agent (a scheduler, an event handler) — a
   pattern already proven for real, not theoretical. See either team's own
   file, §3, for the full reasoning.
