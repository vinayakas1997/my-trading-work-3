# Rl Training Environment

## What This Angle Studies
Gym-compatible SimulatorEnv for RL: state space (weights+cash+prices), action space (target weights), reward (portfolio return), Almgren-Chriss cost model.

## Results
Simulator service health check passes (HTTP 200). SimulatorEnv class documented at vinu-simulator/engine/simulator.py:295-457. Direct import failed (import path issue). Environment exposes reset(seed), step(weights) with realistic costs.

## Execution Time
~0.1s

### Bugs Found
- **Bug 1**: SimulatorEnv import path not found — Import from vinu_simulator.engine.simulator fails. Module may be installed with different package structure. Status: Open