# 03 — Optimization & Efficiency Test Plan

> **Status**: ⏳ Placeholder — will be detailed after Phases 1 and 2 are stable.

## Objective

After the core logic is verified and working, optimize for token efficiency, response speed, prompt quality, and resource usage.

---

## Planned Tests (To Be Detailed)

### 1. Context Window Optimization
- How quickly does the 128k context fill up?
- At what iteration count does compaction trigger?
- How effective is `_auto_compact()` (LLM summarization)?
- How effective is `_microcompact()` (tool result clearing)?

### 2. Prompt Engineering
- Does the system prompt produce correct tool selection?
- Are skill descriptions helpful or just noise?
- Does the "workflow rules" section improve behavior?
- Can we reduce system prompt size without quality loss?

### 3. Tool Selection Patterns
- Which tools are over-used / under-used?
- Are read-only tools being parallelized effectively?
- Are write tools blocking too long?
- Can we merge related tools?

### 4. LLM Parameter Tuning
- Effect of temperature on strategy generation quality
- Effect of context compaction thresholds
- Optimal `max_iterations` value
- Tool timeout tuning

### 5. Service Performance
- Response time of each microservice under load
- Caching opportunities (news LLM analysis, price data)
- Bottleneck identification (LLM speed? Data query? Backtest?)

---

## Metrics (To Be Tracked in Phase 1, Analyzed in Phase 3)

| Metric | Tracked? | Analysis |
|--------|----------|----------|
| LLM calls per request | ✅ Phase 1 | Baseline for optimization |
| Latency per LLM call | ✅ Phase 1 | Where to improve? |
| Prompt size growth | ✅ Phase 1 | Context management tuning |
| Tool execution times | ✅ Phase 1 | Bottleneck identification |
| Iterations per request | ✅ Phase 1 | Optimal max_iterations |
