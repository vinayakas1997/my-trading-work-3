# Phase 2: Walk-Forward Validation and Overfitting Guardrails

## The Problem
The agentic loop generates multiple candidates (up to 15) and iterates until it finds one that achieves a "PASS" verdict. Because this evaluation happens on the *in-sample* data, the system is actively optimizing for noise. 
While `walk_forward.py` exists, the audit shows it is not actively gating the decisions in `loop.py`. The reported metrics are heavily inflated due to the Multiple Comparison Problem.

## How to Fix It

### 1. Enforce Out-of-Sample (OOS) Gating
**Target Files:** `vinu-research/vinu_research/loop.py`

**Implementation Steps:**
- **Split the Data:** Before the first LLM iteration begins, strictly divide the provided date range into `in-sample` (e.g., first 70%) and `holdout` (last 30%).
- **In-Sample Tuning:** Allow the LLM to iterate and generate filters on the `in-sample` data.
- **OOS Gate:** When the Risk Critic issues a `PASS` verdict based on the `in-sample` results, the system MUST run one final, frozen backtest on the `holdout` data.
- If the OOS performance degrades significantly (e.g., Sharpe drops by > 40%), the `PASS` is revoked, the strategy is marked as overfit, and the system either stops or starts over.

### 2. Multiple Comparison Deflation (Deflated Sharpe)
**Target Files:** `vinu-simulator/vinu_simulator/metrics/comparison.py`

**Implementation Steps:**
- Keep track of the total number of strategies evaluated ($N$) across all LLM iterations and candidates.
- Implement Bailey and López de Prado’s **Deflated Sharpe Ratio (DSR)**. As $N$ increases, the threshold for a "statistically significant" Sharpe ratio increases.
- Modify the Risk Critic's prompt and logic to require a higher Sharpe ratio if the system has generated many candidates.

## Definition of Done
- Run a backtest using pure random-walk (noise) price data. The system must reliably fail to produce a `PASS` verdict.
- The final Research Report unconditionally prints two distinct metric blocks: `In-Sample` and `Out-of-Sample`.
