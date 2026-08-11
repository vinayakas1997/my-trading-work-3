---
name: idea_generator
role: idea-generator
prompt_file: prompt.md
depends_on: []
tools: [list_available_features, get_features, get_stock_price, get_fundamentals, get_all_angles, list_sweep_recipes]
skills: [factor-research]
---

Generates a candidate trading strategy, informed by real market data
pulled via its own tools -- including vinu-initial-analysis's angle data
(get_all_angles), not just price/feature/fundamentals data as before. Was
`vinu_research/llm_generator.py`.

Default path (Phase 1, New-talk-agents/new-thinking/new-restructure/phases/
phase-1-sweep-engine-wiring/): call list_sweep_recipes and pick a recipe +
coarse parameter grid when one genuinely fits the hypothesis -- see
prompt.md for the fit requirement and output shape. Raw Python code is
the exception path now, not the default, for ideas no recipe covers.
