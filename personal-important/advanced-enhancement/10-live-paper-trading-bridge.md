# Enhancement 10: Live Paper Trading Bridge

## Current State Score: 2/10

The system is currently **backtest-only**. After a strategy is approved and saved as `*_approved.py`, there's no mechanism to:
- Deploy it to paper trading
- Monitor its live performance
- Compare live vs backtest results
- Alert when live performance deviates from backtest expectations

## Target State: 10/10

A complete paper trading bridge that:
1. Automatically deploys approved strategies to a paper trading environment
2. Runs the strategy daily, generating weights for the current session
3. Executes trades via Alpaca or another paper trading API
4. Records all paper trades for analysis
5. Continuously monitors live vs backtest performance
6. Alerts when performance diverges significantly (possible regime change or strategy decay)
7. Provides a web dashboard showing live P&L, positions, and performance vs backtest

## Why This Matters (The Problem)

- **Backtest-to-live gap**: The biggest risk in quant trading is that live performance doesn't match backtest results. Without paper trading, there's no way to detect this before going live with real money.
- **Strategy decay**: Strategies decay over time as market regimes shift. Without live monitoring, you don't know when a strategy has stopped working.
- **No feedback loop**: The research system can't learn from live trading results. Approved strategies are a one-way output — there's no mechanism to feed live results back into the research loop.
- **Paper trading is the industry standard**: No reputable fund deploys a strategy without at least 3-6 months of paper trading.

## What to Build

### 1. Paper Trading Service — New Component `vinu-trader`

Create a new microservice that manages live strategy execution:

```
vinu-trader/
├── vinu_trader/
│   ├── __init__.py
│   ├── cli.py              # CLI: deploy, status, pause, resume
│   ├── service.py           # PaperTraderService facade
│   ├── config.py            # Config with broker API keys
│   ├── engine/
│   │   ├── executor.py      # Daily strategy execution loop
│   │   ├── broker.py        # Broker interface (Alpaca, paper)
│   │   ├── scheduler.py     # Daily scheduling (cron-like)
│   │   └── order_manager.py # Order lifecycle management
│   ├── monitoring/
│   │   ├── tracker.py       # Live vs backtest comparison
│   │   ├── alerting.py      # Performance deviation alerts
│   │   └── dashboard.py     # Web dashboard generation
│   ├── storage/
│   │   ├── trades.py        # Live trade recording
│   │   └── pnl.py           # P&L tracking
│   └── server/
│       ├── api.py           # FastAPI endpoints
│       └── routes.py        # Status, P&L, positions
├── tests/
├── pyproject.toml
└── Dockerfile
```

### 2. Strategy Deployment Pipeline — Modify `vinu-research/cli.py`

```python
@click.group()
def cli():
    pass

@cli.command()
@click.option("--strategy", required=True, help="Path to approved strategy file")
@click.option("--paper", is_flag=True, help="Deploy to paper trading")
@click.option("--dry-run", is_flag=True, help="Preview deployment without executing")
def deploy(strategy, paper, dry_run):
    """
    Deploy an approved strategy to paper trading.

    Steps:
    1. Validate strategy file (import check + syntax)
    2. Register with vinu-trader service
    3. Set initial capital and config
    4. Start daily execution loop
    """
    ...

@cli.command()
@click.option("--strategy-id", required=True)
def status(strategy_id):
    """Show live status of a deployed strategy"""
    ...

@cli.command()
@click.option("--strategy-id", required=True)
def pause(strategy_id):
    """Pause strategy execution (close positions, stop trading)"""
    ...
```

### 3. Execution Engine — `vinu_trader/engine/executor.py`

```python
class StrategyExecutor:
    """
    Daily execution cycle:
    1. Fetch latest data from vinu-stock-price
    2. Compute required features from vinu-features
    3. Run strategy.generate_weights(data)
    4. Get current positions from broker
    5. Compute target positions from weights
    6. Generate orders (market/limit, size)
    7. Submit orders to broker
    8. Record executed trades
    9. Update P&L
    """

    def __init__(self, config: TraderConfig):
        self.config = config
        self.broker = BrokerInterface(config)
        self.scheduler = DailyScheduler()

    async def run_once(self, strategy_id: str):
        """Single execution cycle (called by scheduler at market close)"""

        # 1. Get strategy
        strategy = await self._load_strategy(strategy_id)

        # 2. Get latest data
        data = await self._fetch_data(strategy.symbols)

        # 3. Compute weights
        weights = strategy.generate_weights(data)

        # 4. Get current positions
        positions = await self.broker.get_positions()

        # 5. Compute target positions
        target = self._compute_target(weights, positions, data)

        # 6. Generate and submit orders
        orders = self._generate_orders(
            current=positions,
            target=target,
            prices=data.close.iloc[-1],
        )
        results = await self.broker.submit_orders(orders)

        # 7. Record
        await self._record_trades(strategy_id, results)
        await self._update_pnl(strategy_id)
```

### 4. Live vs Backtest Monitor — `vinu_trader/monitoring/tracker.py`

```python
class LiveBacktestComparator:
    """
    Continuously compare live trading results with backtest expectations.

    Metrics tracked:
    - Live Sharpe / Backtest Sharpe
    - Live MaxDD / Backtest MaxDD
    - Live WinRate / Backtest WinRate
    - Live CAGR / Backtest CAGR
    - Slippage gap (live slippage vs backtest assumption)

    Alerts triggered when:
    - Sharpe drops below 50% of backtest Sharpe
    - MaxDD exceeds 150% of backtest MaxDD
    - Win rate drops below 60% of backtest
    """

    def compare(self, strategy_id: str) -> ComparisonReport:
        ...

    def alert_if_necessary(self, report: ComparisonReport) -> list[str]:
        alerts = []
        if report.live.sharpe < report.backtest.sharpe * 0.5:
            alerts.append(
                f"CRITICAL: Live Sharpe {report.live.sharpe:.2f} is "
                f"{report.live.sharpe / report.backtest.sharpe:.0%} of backtest"
            )
        if report.live.max_dd > report.backtest.max_dd * 1.5:
            alerts.append(
                f"WARNING: Live MaxDD {report.live.max_dd:.1%} exceeds "
                f"{report.backtest.max_dd:.1%} backtest by {report.live.max_dd / report.backtest.max_dd:.0%}"
            )
        return alerts
```

### 5. Dashboard — FastAPI Web UI

```python
# Simple endpoints for a React dashboard (or lightweight plotly dash)

@router.get("/strategies")
async def list_strategies():
    """List all deployed strategies and their status"""

@router.get("/strategies/{id}/performance")
async def strategy_performance(id: str):
    """Returns live performance metrics + backtest comparison"""

@router.get("/strategies/{id}/positions")
async def current_positions(id: str):
    """Current open positions"""

@router.get("/strategies/{id}/trades")
async def trade_history(id: str):
    """All executed trades"""

@router.post("/strategies/{id}/pause")
async def pause_strategy(id: str):
    """Emergency stop"""

@router.post("/strategies/{id}/resume")
async def resume_strategy(id: str):
    """Resume paused strategy"""
```

### 6. Integration with Research Loop

```python
# In cli.py after successful research:
if approve_strategy:
    paper_config = {
        "strategy_code": result.best_strategy_code,
        "symbols": [symbol],
        "initial_capital": config.initial_capital,
        "backtest_sharpe": result.best_result.metrics.sharpe_ratio,
        "backtest_max_dd": result.best_result.metrics.max_drawdown,
    }
    if ctx.params.get("auto_deploy"):
        # Deploy to paper trading
        response = await http_client.post(
            "http://vinu-trader:8087/strategies",
            json=paper_config,
        )
        LOG.info("Strategy deployed to paper trading, id=%s", response["strategy_id"])
```

## Code Changes Summary

| Component | Change Type | Description |
|-----------|-------------|-------------|
| `vinu-trader/` | **NEW** | Complete paper trading service |
| `vinu_trader/engine/executor.py` | **NEW** | Daily execution loop |
| `vinu_trader/engine/broker.py` | **NEW** | Alpaca paper trading API client |
| `vinu_trader/monitoring/tracker.py` | **NEW** | Live vs backtest comparator |
| `vinu_trader/monitoring/alerting.py` | **NEW** | Deviation alerts |
| `vinu_trader/server/api.py` | **NEW** | FastAPI service |
| `vinu_research/cli.py` | MODIFY | Add `deploy` command |
| `vinu_research/loop.py` | MODIFY | Optional auto-deploy after approval |
| `docker-compose.yml` | MODIFY | Add vinu-trader service |

## Complexity & Verdict

- **Difficulty**: High (requires broker API integration, real-time trade monitoring)
- **Lines of code**: ~1000-1500 total
- **Priority**: **MEDIUM** — essential for real trading, but backtest-first development is fine
- **Dependencies**: Alpaca Trade API (or another broker), vinu-stock-price, vinu-features
- **Risk**: Medium — paper trading with actual broker API introduces operational complexity
- **Time estimate**: 10-15 days

## Implementation Order

### Phase 1 — Foundation (5 days)
1. Build BrokerInterface with Alpaca paper trading API
2. Build StrategyExecutor for daily execution
3. Build trade recording and P&L tracking

### Phase 2 — Deployment (3 days)
4. Build CLI deploy/status/pause commands
5. Integrate with vinu-research (auto-deploy on approve)
6. Add to docker-compose

### Phase 3 — Monitoring (4 days)
7. Build LiveBacktestComparator
8. Build deviation alerting
9. Build web dashboard (or integrate with existing React apps)

### Phase 4 — Safety (2 days)
10. Add manual kill switch (pause all, close all positions)
11. Add max daily loss limit
12. Add position size override

## Risk Management in Paper Trading

The paper trader must include these safeguards:

```python
class RiskLimits:
    max_daily_loss_pct: float = 0.05       # Stop trading if > 5% loss in a day
    max_position_pct: float = 0.25         # Max 25% in any single position
    max_leverage: float = 1.0              # No leverage in paper trading
    min_cash_pct: float = 0.10             # Keep 10% cash at minimum
    max_daily_trades: int = 20             # Prevent overtrading
    max_trade_value_pct: float = 0.10      # Max 10% portfolio value per trade
```
