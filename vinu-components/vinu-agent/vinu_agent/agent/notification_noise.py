"""Cross-channel notification noise control + delivery audit (Stage A,
A33/A35 — pattern from daily_stock_analysis's ``notification_noise.py``).

Vina already had per-feature mute logic (``SignificanceFlag.muted_until``)
and a "don't re-summarise if refreshed recently" check in one worker, but
no shared layer sitting in front of *every* outbound notification. Without
one, a flapping condition — a drawdown oscillating around its threshold,
an OOD alert re-firing each cycle, a repeatedly-rejected trade plan —
spams every configured channel on every tick.

This module is that layer. It is deliberately:

- **In-memory.** Every outbound notifier runs inside the one AgentService
  process; suppression state is inherently ephemeral, and the worst case
  of losing it on restart is a single duplicate alert. If a cross-process
  need appears later, swap the backing dict for a SQLite store the same
  way ``broker/daily_limits.py`` evolved — the interface here doesn't
  change.
- **Permissive by default.** Every window is 0 / disabled unless an
  operator sets the matching ``VINU_AGENT_NOTIFY_*`` env var, so wiring
  this in front of an existing notifier changes nothing until it's
  configured.
- **Fail-open.** Any internal error in ``evaluate`` returns "send" — a
  bug in noise control must never be the reason a real alert is dropped.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path

LOG = logging.getLogger(__name__)


class Severity(IntEnum):
    INFO = 10
    WARNING = 20
    CRITICAL = 30

    @classmethod
    def parse(cls, value: "Severity | str | int | None", default: "Severity") -> "Severity":
        if isinstance(value, Severity):
            return value
        if isinstance(value, int):
            return cls(value) if value in (10, 20, 30) else default
        if isinstance(value, str):
            try:
                return cls[value.strip().upper()]
            except KeyError:
                return default
        return default


@dataclass(frozen=True)
class NoiseConfig:
    # Same key seen again within this many seconds -> suppressed as a duplicate.
    dedup_window_sec: float = 0.0
    # Minimum seconds between two *sent* notifications for the same key.
    cooldown_sec: float = 0.0
    # Local-time [start, end) hour window in which anything below
    # quiet_hours_min_severity is held. end <= start wraps past midnight.
    quiet_start_hour: int | None = None
    quiet_end_hour: int | None = None
    quiet_hours_min_severity: Severity = Severity.CRITICAL
    # How long an in-flight reservation is held before it's considered stale
    # (the sender crashed mid-send) and a retry may proceed.
    reservation_ttl_sec: float = 30.0

    @classmethod
    def from_env(cls) -> "NoiseConfig":
        def _f(name: str, default: float) -> float:
            try:
                return float(os.environ.get(name, default))
            except (TypeError, ValueError):
                return default

        def _h(name: str) -> int | None:
            raw = os.environ.get(name, "").strip()
            if not raw:
                return None
            try:
                h = int(raw)
                return h if 0 <= h <= 23 else None
            except ValueError:
                return None

        return cls(
            dedup_window_sec=_f("VINU_AGENT_NOTIFY_DEDUP_WINDOW_SEC", 0.0),
            cooldown_sec=_f("VINU_AGENT_NOTIFY_COOLDOWN_SEC", 0.0),
            quiet_start_hour=_h("VINU_AGENT_NOTIFY_QUIET_START_HOUR"),
            quiet_end_hour=_h("VINU_AGENT_NOTIFY_QUIET_END_HOUR"),
            quiet_hours_min_severity=Severity.parse(
                os.environ.get("VINU_AGENT_NOTIFY_QUIET_MIN_SEVERITY"), Severity.CRITICAL
            ),
            reservation_ttl_sec=_f("VINU_AGENT_NOTIFY_RESERVATION_TTL_SEC", 30.0),
        )


@dataclass(frozen=True)
class GateDecision:
    send: bool
    reason: str


class NotificationNoiseGate:
    def __init__(self, config: NoiseConfig | None = None, *, clock=time.time) -> None:
        self._config = config or NoiseConfig()
        self._clock = clock
        self._lock = threading.Lock()
        self._last_seen: dict[str, float] = {}   # any evaluate() call
        self._last_sent: dict[str, float] = {}   # confirmed sends only
        self._reserved_until: dict[str, float] = {}

    # -- quiet hours -------------------------------------------------------
    def _in_quiet_hours(self, now: float) -> bool:
        s, e = self._config.quiet_start_hour, self._config.quiet_end_hour
        if s is None or e is None or s == e:
            return False
        hour = datetime.fromtimestamp(now).hour
        if s < e:
            return s <= hour < e
        return hour >= s or hour < e  # wraps midnight

    # -- main decision ---------------------------------------------------
    def evaluate(self, key: str, severity: Severity = Severity.INFO) -> GateDecision:
        """Should this notification go out? Records the sighting either way
        (so dedup counts suppressed attempts too). Fail-open on any error."""
        try:
            cfg = self._config
            with self._lock:
                now = self._clock()
                last_seen = self._last_seen.get(key)
                last_sent = self._last_sent.get(key)
                self._last_seen[key] = now

                if (
                    cfg.dedup_window_sec > 0
                    and last_seen is not None
                    and now - last_seen < cfg.dedup_window_sec
                ):
                    return GateDecision(False, f"duplicate within {cfg.dedup_window_sec:g}s")

                if (
                    cfg.cooldown_sec > 0
                    and last_sent is not None
                    and now - last_sent < cfg.cooldown_sec
                ):
                    return GateDecision(False, f"cooldown ({cfg.cooldown_sec:g}s) not elapsed")

                if self._in_quiet_hours(now) and severity < cfg.quiet_hours_min_severity:
                    return GateDecision(
                        False,
                        f"quiet hours: {severity.name} below {cfg.quiet_hours_min_severity.name}",
                    )

                return GateDecision(True, "ok")
        except Exception:  # noqa: BLE001 -- noise control must never drop a real alert
            LOG.exception("notification noise gate errored for %s, allowing the send", key)
            return GateDecision(True, "gate-error-fail-open")

    # -- in-flight reservation -----------------------------------------
    def reserve(self, key: str) -> bool:
        """Claim the right to send `key` right now. Returns False if another
        caller holds an un-expired reservation (concurrent double-send)."""
        try:
            with self._lock:
                now = self._clock()
                held = self._reserved_until.get(key)
                if held is not None and held > now:
                    return False
                self._reserved_until[key] = now + self._config.reservation_ttl_sec
                return True
        except Exception:  # noqa: BLE001
            LOG.exception("notification reservation errored for %s, allowing", key)
            return True

    def record_sent(self, key: str) -> None:
        with self._lock:
            self._last_sent[key] = self._clock()
            self._reserved_until.pop(key, None)

    def release(self, key: str) -> None:
        """Drop the reservation without marking a successful send (the send
        failed) so a retry isn't blocked by the TTL."""
        with self._lock:
            self._reserved_until.pop(key, None)


class NotificationDeliveryLog:
    """Append-only per-attempt delivery audit (Stage A, A35). Mirrors
    ``broker/kill_switch.py``'s ``AuditLogger`` — one JSON object per line,
    under the container's writable data root."""

    LOG_PATH = Path(
        os.environ.get(
            "VINU_AGENT_NOTIFY_DELIVERY_LOG",
            os.environ.get("VINU_AGENT_DATA_ROOT", str(Path.home() / ".vinu"))
            + "/notification_delivery.log",
        )
    )

    @classmethod
    def record(
        cls,
        *,
        channel: str,
        chat_id: str,
        key: str,
        severity: Severity | str,
        ok: bool,
        http_status: int | None = None,
        latency_ms: float | None = None,
        error: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "chat_id": chat_id,
            "key": key,
            "severity": severity.name if isinstance(severity, Severity) else str(severity),
            "ok": ok,
            "http_status": http_status,
            "latency_ms": round(latency_ms, 1) if latency_ms is not None else None,
            "retryable": retryable if retryable is not None else _default_retryable(http_status),
            "error": error,
        }
        try:
            cls.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with cls.LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError as exc:
            LOG.warning("failed to write notification delivery log: %s", exc)


def _default_retryable(http_status: int | None) -> bool | None:
    if http_status is None:
        return True  # network-level failure — worth a retry
    if http_status == 429 or 500 <= http_status < 600:
        return True
    if 200 <= http_status < 300:
        return False
    return False  # 4xx other than 429 — a retry won't help


# Process-wide singletons (built lazily so importing this module is cheap
# and env is read once, at first use).
_gate: NotificationNoiseGate | None = None


def get_noise_gate() -> NotificationNoiseGate:
    global _gate
    if _gate is None:
        _gate = NotificationNoiseGate(NoiseConfig.from_env())
    return _gate


def reset_noise_gate(gate: NotificationNoiseGate | None = None) -> None:
    """Test hook -- swap in a fresh/fake gate, or clear the singleton so the
    next get_noise_gate() rebuilds it from the current environment."""
    global _gate
    _gate = gate
