---
name: phase-8-test
status: proposed-not-built
purpose: concrete input/expected-output cases proving the consensus check and calibration wiring both preserve the existing grounding discipline instead of quietly working around it.
---

# Phase 8 -- Test plan

**`test_consensus_check_reports_insufficient_data_when_either_angle_empty`**
Input: two angles being compared, one with `row_count == 0`.
Expected: output is "insufficient data to compare" -- not `agree` or
`diverge`.

**`test_consensus_check_directional_agreement`**
Input: two directional angles (e.g. `arima`, `chronos`) both forecasting
the same sign.
Expected: reported as agreeing, citing both real forecast values.

**`test_consensus_check_directional_divergence`**
Input: same angle pair, opposite sign forecasts.
Expected: reported as diverging, citing both real forecast values.

**`test_consensus_check_magnitude_within_tolerance_agrees`**
Input: two numeric forecasts within the stated tolerance of each other.
Expected: reported as agreeing.

**`test_consensus_check_categorical_adjacency_from_config_file`**
Input: a regime label and a lifecycle stage compared via the adjacency
config file; the config is then edited to change that pair's adjacency
rule, and the same comparison run again.
Expected: the output changes to match the edited config without any
prompt change -- proves the adjacency table is externally configurable,
not hardcoded in prose.

**`test_calibration_downweight_distinct_wording_from_missing_data`**
Input: an angle with real data (`row_count > 0`) but a low historical
calibration score.
Expected: output explicitly states "has data, underperformed
historically" (or equivalent) -- wording distinct from how a
`row_count == 0` angle is reported, so a reader can tell the two cases
apart.

**`test_consensus_claims_cite_the_actual_compared_values`**
Input: any agree/diverge output.
Expected: the specific real values from both angles are present in the
output text -- not just the word "agree"/"diverge" with no numbers
backing it.

**`test_calibration_tracker_call_works_regardless_of_transport`**
Input: `CalibrationTracker` reachable via in-process import (migration
complete) in one test run, via HTTP to `research-api` (migration not yet
complete) in another.
Expected: both produce the same calibration result for identical input --
proves the Summary Agent's calibration wiring doesn't hardcode an
assumption about which transport is currently active.

## End-to-end

**`test_phase8_full_summary_with_consensus_and_calibration`**
Input: a real ticker with a realistic mix -- some angles with real data
that agree, some that diverge, one with `row_count == 0`, and calibration
scores spanning both high- and low-trust angles.
Expected: one coherent Summary Agent output where each condition is
represented distinctly and correctly -- agreeing angles cited together,
diverging angles flagged with both real values, the empty angle marked
insufficient-data (not silently dropped or treated as disagreement), and
low-calibration angles flagged as "has data, less trustworthy" rather
than omitted. This is the case that proves the two additions work
together without the grounding discipline breaking anywhere.
