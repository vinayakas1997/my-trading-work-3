"""Stage A (A33/A34/A35): notification noise gate + urgent routing +
per-attempt delivery audit."""

from __future__ import annotations

import json

import pytest

from vinu_agent.agent.notification_noise import (
    GateDecision,
    NoiseConfig,
    NotificationDeliveryLog,
    NotificationNoiseGate,
    Severity,
)
from vinu_agent.agent.scheduler_workers import build_channel_targets


class _Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class TestNoiseGate:
    def test_permissive_by_default(self) -> None:
        gate = NotificationNoiseGate(NoiseConfig())
        for _ in range(5):
            assert gate.evaluate("k", Severity.INFO).send is True

    def test_dedup_window_suppresses_repeat(self) -> None:
        clk = _Clock()
        gate = NotificationNoiseGate(NoiseConfig(dedup_window_sec=60.0), clock=clk)
        assert gate.evaluate("k").send is True
        clk.t += 10
        d = gate.evaluate("k")
        assert d.send is False and "duplicate" in d.reason
        clk.t += 60
        assert gate.evaluate("k").send is True

    def test_cooldown_measured_from_last_confirmed_send(self) -> None:
        clk = _Clock()
        gate = NotificationNoiseGate(NoiseConfig(cooldown_sec=300.0), clock=clk)
        assert gate.evaluate("k").send is True
        gate.record_sent("k")
        clk.t += 100
        assert gate.evaluate("k").send is False  # within cooldown
        clk.t += 250
        assert gate.evaluate("k").send is True   # cooldown elapsed

    def test_quiet_hours_lets_critical_through_only(self) -> None:
        # 2am, quiet window 22:00-06:00
        import datetime as _dt

        two_am = _dt.datetime(2026, 1, 2, 2, 0, 0).timestamp()
        gate = NotificationNoiseGate(
            NoiseConfig(quiet_start_hour=22, quiet_end_hour=6,
                        quiet_hours_min_severity=Severity.CRITICAL),
            clock=_Clock(two_am),
        )
        assert gate.evaluate("a", Severity.INFO).send is False
        assert gate.evaluate("b", Severity.WARNING).send is False
        assert gate.evaluate("c", Severity.CRITICAL).send is True

    def test_reservation_blocks_a_concurrent_second_sender(self) -> None:
        gate = NotificationNoiseGate(NoiseConfig())
        assert gate.reserve("k") is True
        assert gate.reserve("k") is False       # held
        gate.record_sent("k")
        assert gate.reserve("k") is True         # released after a send

    def test_stale_reservation_expires(self) -> None:
        clk = _Clock()
        gate = NotificationNoiseGate(NoiseConfig(reservation_ttl_sec=30.0), clock=clk)
        assert gate.reserve("k") is True
        clk.t += 31
        assert gate.reserve("k") is True         # previous holder crashed; TTL passed

    def test_evaluate_fails_open_on_internal_error(self) -> None:
        gate = NotificationNoiseGate(NoiseConfig(dedup_window_sec=1.0))
        gate._last_seen = None  # type: ignore[assignment]  -- force an AttributeError inside evaluate
        assert gate.evaluate("k").send is True


class TestUrgentRouting:
    class _Cfg:
        telegram_token = "tg"
        telegram_admin_chat_id = "normal-tg"
        telegram_urgent_chat_id = "urgent-tg"
        discord_token = ""
        discord_admin_channel_id = ""
        discord_urgent_channel_id = ""

    def test_normal_notifications_go_to_the_admin_chat(self) -> None:
        targets = build_channel_targets(self._Cfg())
        assert [t.chat_id for t in targets] == ["normal-tg"]

    def test_urgent_notifications_go_to_the_urgent_chat_when_set(self) -> None:
        targets = build_channel_targets(self._Cfg(), urgent=True)
        assert [t.chat_id for t in targets] == ["urgent-tg"]

    def test_urgent_falls_back_to_admin_when_no_urgent_id(self) -> None:
        class Cfg(self._Cfg):
            telegram_urgent_chat_id = ""

        targets = build_channel_targets(Cfg(), urgent=True)
        assert [t.chat_id for t in targets] == ["normal-tg"]


class TestDeliveryLog:
    def test_records_one_json_line_per_attempt(self, tmp_path, monkeypatch) -> None:
        path = tmp_path / "delivery.log"
        monkeypatch.setattr(NotificationDeliveryLog, "LOG_PATH", path)

        NotificationDeliveryLog.record(
            channel="HttpTelegramChannel", chat_id="123", key="k",
            severity=Severity.WARNING, ok=True, http_status=200, latency_ms=42.4,
        )
        NotificationDeliveryLog.record(
            channel="HttpDiscordChannel", chat_id="456", key="k",
            severity=Severity.CRITICAL, ok=False, http_status=503, error="unavailable",
        )
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2
        first, second = json.loads(lines[0]), json.loads(lines[1])
        assert first["ok"] is True and first["retryable"] is False and first["latency_ms"] == 42.4
        assert second["ok"] is False and second["retryable"] is True  # 503 -> retryable
        assert second["severity"] == "CRITICAL"

    def test_network_failure_is_retryable_by_default(self, tmp_path, monkeypatch) -> None:
        path = tmp_path / "d.log"
        monkeypatch.setattr(NotificationDeliveryLog, "LOG_PATH", path)
        NotificationDeliveryLog.record(
            channel="c", chat_id="1", key="k", severity="WARNING", ok=False, error="timeout",
        )
        rec = json.loads(path.read_text().strip())
        assert rec["retryable"] is True and rec["http_status"] is None


class TestSeverityParse:
    def test_parse_from_string_and_fallback(self) -> None:
        assert Severity.parse("critical", Severity.INFO) is Severity.CRITICAL
        assert Severity.parse("nonsense", Severity.INFO) is Severity.INFO
        assert Severity.parse(None, Severity.WARNING) is Severity.WARNING
