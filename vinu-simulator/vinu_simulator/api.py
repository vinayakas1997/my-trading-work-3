from __future__ import annotations

from typing import Any

from vinu_simulator.config import load_config
from vinu_simulator.server.schemas import SimulateRequest
from vinu_simulator.service import SimulatorService


class SimulatorAPI:
    def __init__(self) -> None:
        self._config = load_config()
        self._service: SimulatorService | None = None

    def _get_service(self) -> SimulatorService:
        if self._service is None:
            self._service = SimulatorService(self._config)
        return self._service

    def simulate(
        self,
        strategy_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        initial_capital: float | None = None,
        transaction_cost_pct: float | None = None,
        slippage_pct: float | None = None,
    ) -> dict[str, Any]:
        req = SimulateRequest(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            transaction_cost_pct=transaction_cost_pct,
            slippage_pct=slippage_pct,
        )
        result = self._get_service().simulate(req)
        return {
            "run_id": result.run_id,
            "strategy_name": result.strategy_name,
            "timestamp": result.timestamp.isoformat(),
            "metrics": result.metrics,
            "benchmark_metrics": result.benchmark_metrics,
            "trade_count": len(result.trades),
            "equity_points": len(result.portfolio_values),
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self._service is not None:
            self._service.close()
            self._service = None

    def list_runs(self, strategy_name: str | None = None) -> list[dict[str, Any]]:
        return [r.model_dump() for r in self._get_service().list_runs(strategy_name)]

    def get_result(self, run_id: str) -> dict[str, Any] | None:
        return self._get_service().get_result(run_id)

    def delete_run(self, run_id: str) -> bool:
        return self._get_service().delete_run(run_id)

    def delete_runs(self, strategy_name: str | None = None) -> int:
        return self._get_service().delete_runs(strategy_name)
