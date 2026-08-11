---
name: thesis-intake-strategy-definitions
description: What shapes of strategy exist to test a human-submitted theory against -- read by the thesis_intake team's theory_reviewer to decide whether a raw idea maps to something checkable.
category: strategy
---

## Strategy shapes a human theory can map onto

A human's raw theory ("AAPL tends to keep drifting after an earnings
surprise") is not itself a strategy -- this document is the bridge
between a plain-language idea and the concrete shapes
`vinu-research`'s recipe engine already knows how to test (see
`vinu-research/vinu_research/generator.py`'s `BUILTIN_RECIPES`, the same
recipes Phase 1's `idea_generator` already prefers over hand-written
code).

When reviewing a theory, ask which of these it actually describes:

- **Trend/momentum continuation** -- "X keeps moving in the direction it
  was already moving." Maps to the `momentum`/`crossover` recipe family.
  A theory about drift, breakouts holding, or "don't fight the trend"
  belongs here.
- **Mean reversion** -- "X overshoots and comes back." Maps to the
  `rsi`/`bollinger`/`zscore` recipe family. A theory about overreaction,
  exhaustion, or "it always snaps back" belongs here.
- **Event-driven persistence** -- "a specific event (earnings, news, a
  guidance change) changes X's behavior for a while afterward." This is
  the closest match for the worked example above. Does not map cleanly
  onto a single existing recipe on its own -- note this explicitly in the
  verdict rather than forcing a recipe that only partially fits (same
  "recipe fit must be justified against real data, not picked to dodge
  the alternative" discipline `idea_generator`'s own prompt already
  requires in Phase 1).
- **Cross-sectional / relative** -- "X vs. its peers/sector," not X in
  isolation. Not directly recipe-shaped; needs the peer-relative-strength
  angle's data (`vinu-initial-analysis`) as supporting evidence, not a
  strategy recipe by itself.
- **Regime-conditional** -- "X behaves differently depending on the
  broader market regime." Check `regime_analysis`/`trend_lifecycle` angle
  data for the ticker before concluding this fits; a theory phrased this
  way but with no real regime data behind it for this specific symbol is
  not yet "worth checking," it's a hypothesis about a hypothesis.

**A theory that doesn't cleanly match any of these is not automatically
rejected** -- say so plainly in the verdict, and note that it would need
raw-code strategy generation (Phase 1's exception path) rather than a
recipe, same as any other idea a recipe doesn't fit.
