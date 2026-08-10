---
name: idea_generator
role: idea-generator
prompt_file: prompt.md
depends_on: []
tools: [get_features, get_stock_price, get_fundamentals]
skills: [factor-research]
---

Generates a candidate trading strategy as Python code, informed by real
market data pulled via its own tools. Was `vinu_research/llm_generator.py`.
