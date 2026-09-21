# Time-format richness — what exists, what can be done, and what it's actually worth

Two separate questions, kept separate on purpose: (1) what's now possible
since `GetAllAnglesTool`/`AngleStorage`/the read route all support real
per-granularity fetches (fixed in this session, see git history for
`angles_tool.py`/`routes_read.py`), and (2) whether looking across more
than one timeframe is actually worth the extra cost — measured, not
assumed.

## 1. Where things stand today

Every real angle declares its own real `time_formats` list in
`angles.yaml` (e.g. `arima`: 1min through 1D; `backtesting_44_metrics`:
1min through 6M) — genuine, existing granularity coverage on the
storage side. Until this session, none of it ever reached an LLM: the
whole chain (`GetAllAnglesTool` → Summary Agent → `forecast_skill`) was
hardcoded to `1D` at two separate points (`angles_tool.py`'s v1 fetch
URL, and `routes_read.py`'s fallback read route). Both are now fixed —
`GetAllAnglesTool` takes a real `time_format` parameter, defaulting to
`1D` so nothing existing changed behavior.

**But nothing calls it with anything else yet.** `angle_synthesizer`
(the only real caller) still only ever asks for `1D`. The capability is
real; the usage is zero. Building more on top of an unused capability
without first deciding whether it's worth using would be exactly the
kind of speculative feature this project's own discipline avoids.

## 2. What can be done with it (a menu, not a commitment)

1. **A confirmation check** — `angle_synthesizer` optionally calls
   `get_all_angles` a second time with `time_format="1H"` for the
   forecast-model cluster (Cluster B) or the regime/trend cluster
   (Cluster D), and reports whether the shorter read confirms or
   diverges from the daily one. Cheapest option: one extra call, a
   binary agree/diverge signal.
2. **Label which timeframe each reading came from.** A real prerequisite
   for #1 (and everything below) — `summarize_angle`/`build_angle_digest`
   currently produce `{angle_name: {field: value}}` with no timeframe
   marker at all, which is fine with exactly one timeframe and ambiguous
   the moment there are two.
3. **Decide whether it ever reaches `forecast_skill`'s own prompt**, or
   stays confined to the Summary Agent's narrative. Not free either way:
   reaching `forecast_skill` needs the same timeframe-labeling discipline
   in `_build_forecast_prompt`'s `Angle Digest` section.
4. **Cross-timeframe confluence scoring** (the richer version, section 3
   below) — not a binary agree/diverge, but an actual measured signal of
   how much a second (or third) timeframe changes the picture.

## 3. Cross-timeframe richness — is it actually worth it, and how would we know

The real question behind "worth" here isn't philosophical — this project
already has the right infrastructure to answer it empirically, the same
way it already answers "is this angle worth trusting" instead of
guessing. Two real, existing precedents to build on, not invent from
scratch:

**a. `Calibration Tracker` / `AngleCalibrationEntry`
(`vinu-research/vinu_research/models.py:507+`)** — already tracks, per
angle, a real closed-trade outcome (`forecast_direction`,
`actual_return_pct`, `brier_score`, `directional_correct`,
`magnitude_error`) every time a position closes and that angle was one
of the artifact's `origin_angles`. Its own docstring is explicit that
this is *"an observability signal, not a gate, until real usage says
otherwise"* — exactly the posture cross-timeframe richness should start
from too: measure first, gate later, never invent a threshold ahead of
real data.

**The concrete gap**: `AngleCalibrationEntry` has no `time_format` field
at all — it can already tell you "is `regime_analysis` a trustworthy
angle," but has no way to tell you "is `regime_analysis` *at 1H* worth
checking in addition to 1D." That's the real, specific extension needed:
add `time_format` to `AngleCalibrationEntry`, and to whatever produces
it (`record_realized_outcome` in `trade_plan_authoring.py`, which
currently fans a closed trade's outcome out to one entry per
`origin_angle` with no timeframe attached).

**b. What that unlocks — a real confluence/richness score, not a
guess.** Once outcomes are keyed by `(angle, time_format)`, two genuinely
measurable questions become answerable instead of assumed:
- **Redundancy check**: for a given angle, how often does its `1H`
  reading actually differ from its `1D` reading on the same cycle? If
  they agree almost always, checking `1H` adds no real information —
  pure added cost (a second API call, more tokens in the digest) for
  zero marginal signal.
- **Value check**: on the cycles where `1H` and `1D` *did* disagree,
  did the eventual outcome track the shorter or the longer timeframe
  more often? This is the actual "how much is it worth" answer — not a
  fixed weight decided today, but a real, updatable number derived from
  what has actually happened, the same posture `low_trust < 0.45`
  already uses for whole angles in `calibration.py`.

**Recommendation**: don't build a bespoke "richness score" system.
Extend the calibration infrastructure that already exists (`origin_angles`
→ `AngleCalibrationEntry`) to also carry `time_format`, let it accumulate
real entries once section 2's confirmation check is live, and only then
decide whether cross-timeframe checking is worth keeping, worth
expanding, or worth dropping for a given angle — a real answer instead of
an assumption, on the same timeline the rest of this project's
calibration already operates on (it needs real closed trades to
accumulate before it means anything, same as every other calibration
signal here).

## Status

Written up, not built. Real next step if this direction is confirmed:
section 2, point 2 (timeframe-labeled digest shape) — it's the shared
prerequisite for both the simple confirmation check and the richer
calibration-based richness score, so it's worth doing once, correctly,
rather than twice.
