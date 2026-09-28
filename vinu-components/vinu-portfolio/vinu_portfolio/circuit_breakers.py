from __future__ import annotations

import logging
import os
from typing import Any

import httpx

LOG = logging.getLogger(__name__)


def compute_drawdown_action(
    portfolio_value: float,
    *,
    peak_value: float | None,
    start_value: float | None,
    threshold: float,
    halve_threshold: float,
    flat_threshold: float,
    abs_loss_threshold: float,
) -> dict[str, Any]:
    """The pure threshold/action-ladder math `PortfolioDrawdownMonitor
    .update()` wraps -- item #14A factor #3 (system-wide-audit-and-
    design/02-open-questions-strategy-and-simulation.md): extracted so a
    backtest (`vinu-simulator`'s `DrawdownAwareSizer`) can reuse the exact
    same ok/halve/flat/halt logic without also reusing `update()`'s real
    HTTP halt call -- firing that inside a backtest replaying synthetic
    data would risk halting real live trading as a side effect, which is
    exactly why this wasn't already a drop-in.

    Takes and returns peak/start value explicitly (no `self`) so a caller
    owns its own state -- the live monitor keeps it on `self` across real
    time; a backtest sizer keeps it on its own instance across the
    replayed calendar. Same output shape `update()` already returns, plus
    `new_peak_value`/`new_start_value` for the caller to persist.
    """
    if start_value is None:
        start_value = portfolio_value
    if peak_value is None or portfolio_value > peak_value:
        peak_value = portfolio_value

    if peak_value == 0:
        return {
            "current_drawdown": 0.0, "abs_loss_from_start": 0.0,
            "threshold_breached": False, "abs_loss_breached": False,
            "action": "ok", "new_peak_value": peak_value, "new_start_value": start_value,
        }

    current_drawdown = (portfolio_value - peak_value) / peak_value
    drawdown_breached = current_drawdown <= threshold

    abs_loss = 0.0
    if start_value:
        abs_loss = (portfolio_value - start_value) / start_value
    abs_loss_breached = abs_loss_threshold < 0.0 and abs_loss <= abs_loss_threshold

    threshold_breached = drawdown_breached or abs_loss_breached

    if threshold_breached:
        action = "halt"
    elif current_drawdown <= flat_threshold:
        action = "flat"
    elif current_drawdown <= halve_threshold:
        action = "halve"
    else:
        action = "ok"

    return {
        "current_drawdown": round(current_drawdown, 4),
        "abs_loss_from_start": round(abs_loss, 4),
        "threshold_breached": threshold_breached,
        "abs_loss_breached": abs_loss_breached,
        "action": action,
        "new_peak_value": peak_value,
        "new_start_value": start_value,
    }


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
        unavailable_halt_threshold: int = 3,
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
        # item #23 finding #4 fix (system-wide-audit-and-design/
        # 02-open-questions-strategy-and-simulation.md): drawdown_scheduler.
        # run_once() used to catch any exception reaching agent-api,
        # return {"status": "unavailable"}, and just... move on -- no
        # retry/backoff, no escalation, nothing but an easily-missed log
        # line. If agent-api stays down, real drawdown protection goes
        # silently inert for as long as that lasts. Same "N consecutive
        # cycles" shape already used for LiveScheduler's own
        # RECON_DRIFT_ALERT_CYCLES (vinu-live/vinu_live/scheduler.py,
        # item #24 finding #3's fix) -- "we don't know the drawdown, so
        # trade as if it might already be breached" once unreachability
        # itself persists, not "we don't know, so assume it's fine."
        self._unavailable_halt_threshold = unavailable_halt_threshold
        self._consecutive_unavailable = 0

    def note_unavailable(self) -> dict[str, Any]:
        """Called by drawdown_scheduler.run_once() every cycle agent-api's
        /broker/account fetch itself raises -- NOT for "no_broker_account"/
        "no_equity_data", which are valid states, not failures. Escalates
        to a real halt once unreachability has persisted for
        `unavailable_halt_threshold` consecutive cycles, same real
        cross-process kill switch `_halt_trading` already uses -- an
        unmanaged, unmonitorable book is exactly the situation that halt
        exists for, not just a threshold breach."""
        self._consecutive_unavailable += 1
        escalated = self._consecutive_unavailable >= self._unavailable_halt_threshold
        if escalated:
            self._halt_trading(
                0.0,
                reason=(
                    f"agent-api unreachable for {self._consecutive_unavailable} "
                    f"consecutive drawdown-monitor cycles -- cannot verify "
                    f"drawdown is within limits, halting as a precaution"
                ),
            )
        return {
            "consecutive_unavailable": self._consecutive_unavailable,
            "escalated_halt": escalated,
            "action": "halt" if escalated else "unknown",
        }

    def update(self, portfolio_value: float) -> dict[str, Any]:
        """Process a new portfolio value and return status info.

        Returns a dict with:
          - current_drawdown: float
          - threshold_breached: bool
          - halted: bool (whether the kill switch was triggered)
        """
        # A real, successful update means agent-api is reachable again --
        # clear any unavailability streak so a single-cycle blip that
        # already recovered doesn't sit halfway toward escalating later.
        self._consecutive_unavailable = 0

        result = compute_drawdown_action(
            portfolio_value,
            peak_value=self._peak_value, start_value=self._start_value,
            threshold=self._threshold, halve_threshold=self._halve,
            flat_threshold=self._flat, abs_loss_threshold=self._abs_loss_threshold,
        )
        self._peak_value = result["new_peak_value"]
        self._start_value = result["new_start_value"]

        threshold_breached = result["threshold_breached"]
        abs_loss_breached = result["abs_loss_breached"]
        current_drawdown = result["current_drawdown"]
        abs_loss = result["abs_loss_from_start"]

        halted = False
        if threshold_breached:
            if abs_loss_breached and not (current_drawdown <= self._threshold):
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

        return {
            "current_drawdown": current_drawdown,
            "abs_loss_from_start": abs_loss,
            "threshold_breached": threshold_breached,
            "abs_loss_breached": abs_loss_breached,
            "halted": halted,
            "action": result["action"],
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
