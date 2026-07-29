Focus 1 — Monte Carlo Strategy Optimization
What exists today: vinu-simulator runs backtests with fixed configs. vinu-strategy evaluates strategies. vinu-initial-analysis computes 11 angles. vinu-research does LLM-guided strategy iteration. But nothing ties them together into a parameter sweep.
What it should do: For a strategy with N tunable parameters (e.g., two indicators with precision ranges), systematically test permutations via the simulator, evaluate each result across the 11 analysis angles (your "gatekeepers"), and converge on the optimal parameter set.
Architecture thought: The vinu-simulator already has the engine — it just needs a batch/permutation mode. The vinu-initial-analysis already has the 11 angles — they just need to be queried per permutation. The vinu-agent should orchestrate the loop: define the parameter space → submit batches → read angle results → decide next iteration or converge.
This doesn't need a new service. It needs:
- A permutation runner mode in vinu-simulator
- The agent to gain a new "optimizer" skill/tool
- The analysis angles to be called systematically (right now they're standalone)
Focus 2 — Agent Role & News Angle Utilization
Today the agent syncs everything into memory but doesn't use the analysis angles actively. The 11 angles (news_price_causality, trend_lifecycle, drawdown_deep_dive, shock_personality, regime_analysis, etc.) are computed and stored but not queried back to drive decisions.
The agent should:
- Query specific angles on-demand when making strategy decisions
- Feed angle results into optimization decisions
- Use regime analysis to decide which market environment we're in
- Use news_price_causality and shock detection to avoid certain plays
Focus 3 — Progressive Daily Portfolio
This is the core value and the most ambitious.
Current vinu-portfolio is stateless — computes risk-parity in memory and returns it. No tracking, no learning, no market regime awareness, no probability-based allocation.
What I think this should be:
- A stateful service that tracks portfolio state daily in SQLite
- Reads current market regime from the 11 analysis angles
- Takes active strategies from research + yesterday's performance
- Produces a daily allocation: which tickers + cash ratio with highest probability
- The probability model improves over time as outcomes accumulate
This effectively replaces vinu-portfolio with a much smarter version.


The Core Problem
Right now the platform has all the pieces but they don't feed back into each other in a learning loop:
vinu-strategy ──► vinu-simulator ──► vinu-research ──► vinu-portfolio ──► vinu-live
                                                                                │
                          (feedback missing) ◄──────────────────────────────────┘
The 11 analysis angles exist but nobody calls them to influence decisions. The agent syncs data but doesn't orchestrate. The portfolio is stateless.
What a Mature System Would Look Like
         ┌─── Monte Carlo optimization loop ──────────────────────┐
         │                                                        │
         │  Agent decides parameter space                         │
         │      │                                                 │
         │      ▼                                                 │
         │  vinu-simulator runs N permutations                    │
         │      │                                                 │
         │      ▼                                                 │
         │  vinu-initial-analysis evaluates each via 11 angles    │
         │      │                                                 │
         │      ▼                                                 │
         │  Agent converges on optimal params                     │
         │      │                                                 │
         └──────┴─────────────────────────────────────────────────┘
                        │
                        ▼
         Optimized strategy registered in vinu-strategy
                        │
                        ▼
         ┌─── Daily portfolio loop ───────────────────────────────┐
         │                                                        │
         │  Morning:                                              │
         │    • Query vinu-initial-analysis → current regime      │
         │    • Read yesterday's performance                     │
         │    • Query active strategies from research            │
         │    • Compute: which tickers + cash ratio = highest P?  │
         │      │                                                 │
         │      ▼                                                 │
         │  Output: daily allocation plan                         │
         │      │                                                 │
         │      ▼                                                 │
         │  vinu-live executes                                     │
         │      │                                                 │
         │  Evening:                                              │
         │    • Record actual outcomes                            │
         │    • Feed back into probability model                  │
         │    • Update agent memory                               │
