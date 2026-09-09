from __future__ import annotations

import logging
import os
from typing import Any

import httpx

LOG = logging.getLogger(__name__)


class PortfolioDrawdownMonitor:
    """Monitors portfolio-level drawdown and triggers the kill switch when
    the drawdown exceeds a configurable threshold.

    Halts trading via agent-api's `/broker/halt` endpoint rather than
    touching a local kill-switch file: each vinu-* service runs in its own
    container with a private tmpfs /tmp, so a file touched here would never
    be visible to OrderGuard, which checks the kill switch inside the
    agent-api container. See vinu_agent/vinu_agent/server/routes_broker.py.
    """

    def __init__(
        self,
        drawdown_threshold: float = -0.20,
        agent_api_url: str | None = None,
        halve_threshold: float | None = None,
        flat_threshold: float | None = None,
    ) -> None:
        self._threshold = drawdown_threshold
        # DD de-risk (19 step2): halve at -10%, flat at -15%, halt at -20%.
        # Env only, defaults keep old halt behavior plus new actions.
        self._halve = -abs(float(halve_threshold)) if halve_threshold is not None else -abs(float(os.environ.get("VINU_PORTFOLIO_DD_HALVE", "-0.10")))
        self._flat = -abs(float(flat_threshold)) if flat_threshold is not None else -abs(float(os.environ.get("VINU_PORTFOLIO_DD_FLAT", "-0.15")))
        self._peak_value: float | None = None
        self._agent_api_url = agent_api_url or os.environ.get(
            "VINU_AGENT_API_URL", "http://localhost:8086"
        )

    def update(self, portfolio_value: float) -> dict[str, Any]:
        """Process a new portfolio value and return status info.

        Returns a dict with:
          - current_drawdown: float
          - threshold_breached: bool
          - halted: bool (whether the kill switch was triggered)
        """
        if self._peak_value is None or portfolio_value > self._peak_value:
            self._peak_value = portfolio_value

        if self._peak_value is None or self._peak_value == 0:
            return {"current_drawdown": 0.0, "threshold_breached": False, "halted": False}

        current_drawdown = (portfolio_value - self._peak_value) / self._peak_value
        threshold_breached = current_drawdown <= self._threshold

        halted = False
        if threshold_breached:
            self._halt_trading(current_drawdown)
            halted = True

        # Action ladder: ok -> halve -> flat -> halt. Orchestrator halves size
        # at halve, exits to flat at flat, HALT entries-only at halt.
        if threshold_breached:
            action = "halt"
        elif current_drawdown <= self._flat:
            action = "flat"
        elif current_drawdown <= self._halve:
            action = "halve"
        else:
            action = "ok"

        return {
            "current_drawdown": round(current_drawdown, 4),
            "threshold_breached": threshold_breached,
            "halted": halted,
            "action": action,
        }

    def _halt_trading(self, drawdown: float) -> None:
        reason = f"portfolio drawdown {drawdown:.1%} exceeds threshold {self._threshold:.1%}"
        try:
            try:
                from vinu_infra.auth import internal_auth_headers
                _headers = internal_auth_headers() or None
            except Exception:
                _headers = None
            resp = httpx.post(
                f"{self._agent_api_url}/agent/broker/halt",
                json={"reason": reason},
                headers=_headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            LOG.warning("PORTFOLIO DRAWDOWN %.1f%% exceeds threshold %.1f%% — trading halted via %s",
                        drawdown * 100, self._threshold * 100, self._agent_api_url)
        except Exception as e:
            LOG.error(
                "PORTFOLIO DRAWDOWN %.1f%% exceeds threshold %.1f%% — FAILED to halt "
                "trading via %s: %s. Trading is NOT halted — manual intervention required.",
                drawdown * 100, self._threshold * 100, self._agent_api_url, e,
            )

    def reset(self) -> None:
        self._peak_value = None
