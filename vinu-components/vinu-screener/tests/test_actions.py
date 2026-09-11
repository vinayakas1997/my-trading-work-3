from __future__ import annotations

from vinu_screener.rules.actions import ActionsConfig, resolve_targets


class TestFromDict:
    def test_defaults_when_omitted(self) -> None:
        cfg = ActionsConfig.from_dict(None)
        assert cfg.toast is True
        assert cfg.providers == {}

    def test_parses_toast_and_providers(self) -> None:
        cfg = ActionsConfig.from_dict({"toast": False, "providers": {"telegram": True, "discord": False}})
        assert cfg.toast is False
        assert cfg.providers == {"telegram": True, "discord": False}

    def test_round_trips_through_to_dict(self) -> None:
        cfg = ActionsConfig(toast=False, providers={"telegram": True})
        assert ActionsConfig.from_dict(cfg.to_dict()) == cfg


class TestResolveTargets:
    def test_toast_only_by_default(self) -> None:
        assert resolve_targets(ActionsConfig()) == ["toast"]

    def test_toast_disabled_and_a_provider_enabled(self) -> None:
        cfg = ActionsConfig(toast=False, providers={"telegram": True})
        assert resolve_targets(cfg) == ["telegram"]

    def test_disabled_provider_is_excluded(self) -> None:
        cfg = ActionsConfig(providers={"telegram": True, "discord": False})
        targets = resolve_targets(cfg)
        assert "telegram" in targets
        assert "discord" not in targets

    def test_no_targets_when_everything_disabled(self) -> None:
        cfg = ActionsConfig(toast=False, providers={"telegram": False})
        assert resolve_targets(cfg) == []
