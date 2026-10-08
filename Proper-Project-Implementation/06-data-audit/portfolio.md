# Data audit: vinu-portfolio

Checked 2026-10-08 on the running stack (`portfolio-api`, port 8090; `/data`: `allocation_history.db`, `drawdown_status.db`).

## What triggers it
- **Daily allocation** (`GET /portfolio/daily-allocation`, called by the live scheduler each cycle): reads the active strategies from research, each one's equity returns from the simulator, builds weights (and, with `VINU_REAL_CAPITAL` set, dollars from the capital allocator), applies the drawdown and maturity ladders, writes one history row per day.
- **Drawdown scheduler:** reads the account equity from agent-api on a timer and keeps the current drawdown action.

## Data items

### P1 Allocation history  `allocation_history.db: allocation_history` (2 rows: 2026-10-06, 2026-10-07)
- **Format:** per day: `weights` JSON, `sleeves`, `interval_sleeves`, `account_equity`, `reserve_fraction`, `reserve_amount`, `deployable_equity`, `created_at`, and (schema v3, added by the capital allocator work) `account_mode`, `capital_base`, `committed`. Example: 2026-10-07, 12 weights, account equity 96,613.44, deployable 8,695.21.
- **Access:** `GET /portfolio/allocation-history`, `/not-funded`. **Consumers:** none found outside the portfolio service.
- **Properties:** the two rows were written before the real-money base existed (account base 96,613, YAML strategies funded); the live file still has the old columns until the next allocation writes (it is migrated on the first write; guarded by tests). **Verdict:** `no reader`, and the history mixes two different bases (DA-P1).

### P2 Drawdown status  `drawdown_status.db: drawdown_status` (1 row, `id = 1`)
- **Format:** `action (ok|...), current_drawdown, threshold_breached, updated_at`. Now: ok, 0.0.
- **Access:** `GET /portfolio/risk/status`. **Consumers:** agent (3 files), infra edge contracts; the daily allocation reads the action to scale held money. **Verdict:** `used well`, but it is a single current value with no history, and the drawdown is measured from equity the portfolio fetches on demand: no equity series is stored anywhere (DA-P4).

### P3 Computed on demand (nothing stored)
- `/portfolio/state`, `/weights`, `/strategies`, `/daily-allocation`, `/daily-game-plan`, `/capital-plan`, `/evaluate-batch`. All answer `empty` right now because no strategy is ACTIVE; `/capital-plan` still shows the ledger (committed 0, free cash 12 of the 20-dollar base, paper mode).
- **Consumers:** live scheduler (`/daily-allocation`, `/state`: 8 files), agent (`/state` 5 files, `/risk/status`, `/capital-plan` via `get_capital_summary`, `/strategies`, `/evaluate-batch`). `/weights`, `/daily-game-plan`, `/allocation-history` and `/not-funded` have no caller. **Verdict:** `used well` where called.

## Where portfolio reaches a decision
research ACTIVE strategies + simulator returns -> weights/dollars -> live scheduler orders. With no ACTIVE strategy the answer is `empty` and live trades nothing, as designed.
