# Decision — Row 8 Calibration Tracker (spiked, not yet wired 2026-09-07)

> `04:77-79` built/unused. `vinu-research/calibration.py` + `AngleCalibrationEntry` exists, Summary Agent `screener` team not yet consulting it.

## Status

- Spike: `calibration.py` `get_angle_calibration` + `AngleCalibrationResult` is observability signal, no pass/fail gate (deliberate per `models.py:383`).
- Next: wire `screener` `make_summary_agent_fn` `scheduler_workers.py:72` to fetch `angle_calibration` before `get_all_angles` and filter/prioritize angles with `accuracy <0.45` as low-trust. Keep as backlog after A1-A2 green, not blocker for first cycle.

## Dated

- 2026-09-07 — acknowledged, backlog.
