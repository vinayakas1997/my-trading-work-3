# Research Loop

## What This Angle Studies
Automated strategy research: template selection, auto-iteration, risk critic (19 dimensions), AST verification, weight holding check, auto-filters, hypothesis registry.

## Results
Research loop module (vinu_research.runner) not importable - import path differs. Code exists at vinu-research/ but runner module name/structure not as expected. 15 strategy templates, 19 risk critic dimensions, and walk-forward/holdout validation documented in codebase.

## Execution Time
~0.1s

### Bugs Found
- **Bug 1**: vinu_research.runner module not found — No module named vinu_research.runner. Research loop entry point may have a different module name or is not exported. Status: Open