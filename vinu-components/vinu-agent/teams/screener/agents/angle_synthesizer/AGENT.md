---
name: angle_synthesizer
role: angle-synthesizer
prompt_file: prompt.md
depends_on: []
tools: [get_all_angles]
skills: []
---

Given one ticker, fetches all 28 vinu-initial-analysis angles for it in
a single tool call and synthesizes an initial read across whichever
angles actually have data.
