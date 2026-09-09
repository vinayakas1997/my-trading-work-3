# Plan - 20 Learning Over Time

Goal: Lesson worker + calibration wire first, memory starts day 1.

Files touched:
- `vinu-components/vinu-live/feedback_loop.py:86,121,135` close writes.
- `vinu-components/vinu-research/calibration.py:22`, `forecast_skill.py:77` accuracy.
- `vinu-components/vinu-agent/agent/scheduler_workers.py:37` angle trust 0.45.
- `vinu-components/vinu-research/scheduled/executor.py:118`, `config.py:162`, `cli.py:146,569` scans/decay.
- Lesson LESSON artifact + regime/weight fields + PRIDE star + notebook.

Steps:
1. Lesson worker 3600s + calibration wire de-prioritize low_trust.
2. Decay reconcile single policy + regime lessons + forgetting halve 90d + PRIDE.
3. Baseline PPO + debate on PASS only.
4. RD loop + full 5-agent later after 30 trades + GPU.

Knobs: LESSON_ENABLED, INTERVAL 3600, MIN_TRADES 30, REGIME, DECAY 90d, PRIDE, VECTOR false to 1000, BAKEOFF, DEBATE, RD false (see 10).
Acceptance: lesson after 30, low_trust de-prioritized, single decay, debate cites table.
