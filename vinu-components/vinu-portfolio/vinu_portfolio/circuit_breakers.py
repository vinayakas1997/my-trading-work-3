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
        abs_loss_threshold: float | None = None,
    ) -> None:
        self._threshold = drawdown_threshold
        # DD de-risk (19 step2): halve at -10%, flat at -15%, halt at -20%.
        # Env only, defaults keep old halt behavior plus new actions.
        self._halve = -abs(float(halve_threshold)) if halve_threshold is not None else -abs(float(os.environ.get("VINU_PORTFOLIO_DD_HALVE", "-0.10")))
        self._flat = -abs(float(flat_threshold)) if flat_threshold is not None else -abs(float(os.environ.get("VINU_PORTFOLIO_DD_FLAT", "-0.15")))
        # Stage A (A16): a second, independent breaker -- absolute loss from
        # the session's STARTING equity, not from its running peak. Hummingbot's
        # kill switch works this way. The two catch different things:
        # drawdown-from-peak re-references to every new high (so it can trip
        # while you're still net up on the session, and conversely a slow
        # grind-down where the peak never pulled far ahead can stay under it
        # for a long time); loss-from-start never trips while you're net
        # profitable but does catch that steady bleed. 0.0 (default) disables
        # it -- drawdown-from-peak stays the only breaker unless an operator
        # opts in. Env: VINU_PORTFOLIO_ABS_LOSS_HALT (e.g. -0.15).
        self._abs_loss_threshold = (
            -abs(float(abs_loss_threshold)) if abs_loss_threshold is not None
            else -abs(float(os.environ.get("VINU_PORTFOLIO_ABS_LOSS_HALT", "0.0")))
        )
        self._peak_value: float | None = None
        self._start_value: float | None = None
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
        if self._start_value is None:
            self._start_value = portfolio_value
        if self._peak_value is None or portfolio_value > self._peak_value:
            self._peak_value = portfolio_value

        if self._peak_value is None or self._peak_value == 0:
            return {"current_drawdown": 0.0, "threshold_breached": False, "halted": False}

        current_drawdown = (portfolio_value - self._peak_value) / self._peak_value
        drawdown_breached = current_drawdown <= self._threshold

        # A16: absolute loss from the session's starting equity, checked
        # independently of the peak. Only armed when the operator set a
        # non-zero threshold.
        abs_loss = 0.0
        if self._start_value:
            abs_loss = (portfolio_value - self._start_value) / self._start_value
        abs_loss_breached = self._abs_loss_threshold < 0.0 and abs_loss <= self._abs_loss_threshold

        threshold_breached = drawdown_breached or abs_loss_breached

        halted = False
        if threshold_breached:
            if abs_loss_breached and not drawdown_breached:
                self._halt_trading(
                    abs_loss,
                    reason=(
                        f"session loss {abs_loss:.1%} from starting equity exceeds "
                        f"absolute-loss halt threshold {self._abs_loss_threshold:.1%}"
                    ),
                )
            else:
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
            "abs_loss_from_start": round(abs_loss, 4),
            "threshold_breached": threshold_breached,
            "abs_loss_breached": abs_loss_breached,
            "halted": halted,
            "action": action,
        }

    def _halt_trading(self, drawdown: float, reason: str | None = None) -> None:
        reason = reason or f"portfolio drawdown {drawdown:.1%} exceeds threshold {self._threshold:.1%}"
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
            LOG.warning("PORTFOLIO CIRCUIT BREAKER — %s — trading halted via %s",
                        reason, self._agent_api_url)
        except Exception as e:
            LOG.error(
                "PORTFOLIO CIRCUIT BREAKER — %s — FAILED to halt trading via %s: %s. "
                "Trading is NOT halted — manual intervention required.",
                reason, self._agent_api_url, e,
            )

    def reset(self) -> None:
        self._peak_value = None
        self._start_value = None
