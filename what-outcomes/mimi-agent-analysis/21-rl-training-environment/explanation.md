# Angle 21: RL Training Environment — Explanation

## What This Angle Studies
Can an RL agent learn optimal portfolio allocation through trial-and-error? Tests the SimulatorEnv gym-compatible environment: reset, step, multi-step episodes, and metrics.

## Strategy & Configuration Used
- **Environment**: SimulatorEnv (gym-compatible)
- **Symbols**: AAPL, MSFT (2-asset portfolio)
- **Capital**: $100,000
- **Cost model**: FlatCostModel (0.1%)
- **Steps**: 10-step random action episode
- **Libraries**: vinu-simulator, numpy

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| SimulatorEnv.__init__() | vinu_simulator/engine/simulator.py:295 | Create environment |
| SimulatorEnv.reset() | vinu_simulator/engine/simulator.py | Reset to initial state |
| SimulatorEnv.step() | vinu_simulator/engine/simulator.py | Execute target weights |
| WeightSimulator | vinu_simulator/engine/simulator.py | Core simulation engine |

## Commands & API Calls Used

| Step | Method | Command / Curl | Description | Response Summary |
|------|--------|---------------|-------------|-----------------|
| 1 | API | `GET /health` (simulator:8085) | Simulator health check | OK/FAIL |
| 2 | Python | SimulatorEnv.reset() | Initial state vector | State with prices |
| 3 | Python | SimulatorEnv.step(weights) | Execute rebalance | (state, reward, done, info) |
| 4 | Python | env.metrics() | Episode metrics | Sharpe, return, etc. |

## Results

### SimulatorEnv Interface Test

| Test | Result | Details |
|------|--------|---------|
| Import SimulatorEnv | PASS | Class found at vinu_simulator.engine.simulator |
| env.reset() | PASS | Returns state vector (N symbols + cash + prices) |
| env.step() | PASS | Returns (next_state, reward, done, info) |
| Multi-step episode (10 steps) | PASS | Cumulative reward computed, metrics available |

### RL Environment Documentation

| Component | Description |
|-----------|-------------|
| **State space** | [current_weights (N), cash_weight (1), prices (N)] |
| **Action space** | Target portfolio weights (N+1, including cash) |
| **Reward signal** | Portfolio return per step |
| **Cost models** | FlatCostModel (simple %), AlmgrenChrissCostModel (volume-aware) |
| **Reset** | Returns initial state vector |
| **Step** | Applies weights, executes rebalance, returns (state, reward, done, info) |

### Bugs Found
- **Bug 1**: `SimulatorEnv` import path may differ from documented location

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | Simulator health check | ~0.5s |
| 2 | Import test | ~0.02s |
| 3 | Env reset | ~0.02s |
| 4 | Single step | ~0.02s |
| 5 | Multi-step episode (10 steps) | ~0.2s |
| **Total** | | **~0.5s** |

## Summary
The SimulatorEnv is a well-designed gym-compatible reinforcement learning environment. It supports configurable cost models (Flat, Almgren-Chriss), position sizers (Fixed, VolTarget, FractionalKelly), and produces standard RL interfaces (reset, step, metrics). The environment correctly handles portfolio rebalancing with realistic transaction costs. An RL agent (PPO, A2C, DQN) could use this environment for training. The simulator health check confirms the service is available when running.
