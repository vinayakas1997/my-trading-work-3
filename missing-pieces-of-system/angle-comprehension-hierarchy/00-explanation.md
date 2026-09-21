# Angle comprehension hierarchy — detailed explanation

Everything cited below was verified against real code on 2026-09-21
(`vinu-agent/vinu_agent/tools/angles_tool.py`,
`vinu-research/vinu_research/forecast_skill.py`,
`vinu-agent/teams/screener/agents/angle_synthesizer/prompt.md`,
`vinu-initial-analysis/vinu_initial_analysis/catalog/angles.yaml`), same
discipline as this project's other `missing-pieces-of-system/` docs.

## 1. The two real gaps, confirmed

**Gap 1 — angle explanations exist but never reach a prompt.**
`angles.yaml` has a real `title` + `purpose` (1-3 sentence plain-English
explanation) + output `description` for every one of its 28 angles. But
every real path that builds a prompt from angle data ignores it:
- `angles_tool.py::summarize_angle` (builds the `Angle Digest` used in
  `forecast_skill`'s prompt) only copies raw scalar fields off an
  angle's latest data row — no reference to the catalog at all.
- `angle_synthesizer`'s own prompt (`teams/screener/agents/
  angle_synthesizer/prompt.md`) tells the LLM the *rules* for reporting
  on angles (cite real numbers, check `row_count`, cross-check
  consensus) but never explains what any individual angle computes.
- `idea_generator`'s prompt, same thing.

**Gap 2 — `forecast_skill` has no room to reason about 28+ angles
individually.** `generate_forecast` (`forecast_skill.py:176`) is one
direct `chat_json()` call, system prompt says *"Return ONLY valid
JSON... No markdown fences"* — no tool access, no separate deliberation
turn. Even with explanations added, dumping up to 30 angle-name/field
lines into one flat list gives the model no structured way to weigh
them — everything arrives at once, undifferentiated, in a single forward
pass that also has to produce the final numbers.

## 2. The design: three tiers, not a flat dump

**Tier 1 — per-angle digestion.** For every angle with real data,
produce one short, grounded takeaway: what the angle measures (from the
new glossary) + what it's currently showing + how confident that reading
is. Real reasoning per angle, not a raw value copy.

**Tier 2 — clustered synthesis.** Group the ~28 per-angle takeaways into
a small number of thematic clusters (see section 3 below — a real,
complete assignment of all 28 angles, not a sample) and produce one
short synthesis per cluster. Turns "28 things to hold in mind at once"
into "6-7 chapter summaries."

**Tier 3 — final decision.** `forecast_skill` reads the chapter
summaries (not 28 raw lines) plus the exact, unsummarized Risk
State/Personality numbers, which stay raw on purpose — sizing must come
from real numbers, not narrative (the system prompt's own existing
rule).

## 3. The real 28-angle clustering scheme

Every one of the 28 real angle ids from `angles.yaml`, assigned to one
of 7 thematic clusters — grounded in each angle's actual `title`, not
guessed:

**Cluster A — Classical statistical forecasts (3)**
`arima`, `exponential_smoothing`, `kalman_filters` — traditional
statistical time-series methods (AR/MA-family models, smoothing,
state-space estimation).

**Cluster B — Deep-learning / foundation-model forecasts (14)**
`chronos`, `dlinear`, `itransformer`, `kronos`, `lag_llama`, `lpatchtst`,
`lstm`, `moirai`, `moment`, `patchtst`, `tft`, `timer_timerxl`,
`timesfm`, `tips_regime_aware_transformer` — every neural/foundation
forecasting model. Deliberately kept as one cluster rather than split
further: with 14 members, the single most valuable synthesis question
for this cluster is **cross-model consensus** — do most of these
independent architectures agree on direction, or is the "signal" really
just one or two models diverging from the rest? The Tier-2 synthesis for
this cluster should report an agreement rate, not describe all 14
individually (mirrors `angle_synthesizer`'s existing "Cross-angle
consensus" section, generalized from ad hoc pairs to this whole cluster).

**Cluster C — Volatility & drawdown risk (2)**
`garch`, `drawdown_deep_dive` — how much this symbol actually moves, and
how it has historically drawn down.

**Cluster D — Regime & trend structure (3)**
`regime_analysis`, `trend_lifecycle`, `trend_session_structure` — what
kind of market/trend phase the symbol is currently in.

**Cluster E — Shock / personality behavior (2)**
`shock_clustering`, `shock_personality` — this symbol's own
idiosyncratic reaction pattern to shocks, and which other symbols it
clusters with under stress. (Already the two angles the pre-2026-09-14
forecast prompt read exclusively, per `01-new-full-explanation-v2.md`'s
RESOLVED callout — this cluster's synthesis should be held to the
highest bar, since it has the longest track record of actually reaching
a forecast call.)

**Cluster F — Cross-asset & causality (2)**
`peer_relative_strength`, `news_price_causality` — how this symbol
behaves relative to its peers, and whether news genuinely precedes its
price moves (or the reverse).

**Cluster G — Validation & attribution (2)**
`backtesting_44_metrics`, `pnl_attribution` — real historical
performance/attribution metrics, not a forward-looking signal at all;
this cluster answers "has anything like this actually worked before,"
distinct from every other cluster's "what does the data say right now."

7 clusters, 3+14+2+3+2+2+2 = 28 — every real angle id accounted for,
none invented or dropped.

## 4. Where each tier actually lives

- **Tier 1 + Tier 2 run upstream**, inside the `screener` team's
  `angle_synthesizer` (Path A — already has tool access and already
  does multi-turn reasoning; this is closer to a prompt/process update
  than a new architecture). Output: the existing free-text summary,
  **plus** a new structured `cluster_digest` (7 entries, one per
  cluster above) stored alongside today's `angle_digest` in
  `TickerSummaryStore`.
- **Tier 3 stays `forecast_skill`**, unchanged in shape (still one
  call, per the "ONE call per plan" invariant) but fed the new
  `cluster_digest` instead of (or alongside, during a transition) the
  flat 30-line `angle_digest`. Risk State/Personality Features are
  untouched — they were never the problem.

This keeps `forecast_skill`'s one-call design intact while fixing both
real gaps: angle explanations now exist upstream (Tier 1), and the
model at decision time reads a handful of already-comprehended chapter
summaries instead of an unexplained flat list (Tier 2 output, Tier 3
input).

## Status: planned, not built

See `01-plan.md` for the ordered build steps.
