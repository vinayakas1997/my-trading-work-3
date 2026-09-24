# Test results

Worked examples showing the actual mechanics this folder exists for:
take one angle's real `compute()` output shape, build the exact prompt
that would be sent to the downstream local LLM (angle context section
copied verbatim from that angle's own research file, per the "passed to
the LLM" / "human only" split defined in `../README.md`), and show the
conclusion the model draws.

Each subfolder is one worked example:

| # | Example | What it demonstrates |
|---|---|---|
| 01 | `01-trend_lifecycle-1H-vs-1min` | The `no_peaks` status, taken at face value, reads as "no pattern exists." With the angle's own researched context (specifically F1: the missing `1min`/`5min` threshold entries, documented in `../27-trend_lifecycle-angle.md`), the same status is correctly read as "the detector is miscalibrated for this input," not as real evidence. Includes both the correct answer (with context) and the wrong-but-plausible answer (without it), for direct comparison. |

## Data note

The `compute()` JSON in these examples is **fabricated** for
demonstration -- it was not produced by a real run against real bars.
The angle context text (definition/assumptions/output fields/status
values) is copied verbatim from the already-researched, cited files in
the parent folder, so that part is real.
