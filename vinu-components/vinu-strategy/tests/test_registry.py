import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

from vinu_strategy.engine.registry import StrategyRegistry
from vinu_strategy.models.strategy import StrategyConfig


class TestStrategyRegistry:
    def test_load_yaml_strategies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            strategies_dir = Path(tmpdir)
            (strategies_dir / "test.yaml").write_text(
                "name: test_strat\n"
                "description: test\n"
                "schedule: daily\n"
                "features_required:\n"
                "  - SMA_9\n"
                "  - SMA_21\n"
            )
            registry = StrategyRegistry(strategies_dir)
            strategies = registry.load_all()
            assert "test_strat" in strategies
            cfg = strategies["test_strat"]
            assert cfg.name == "test_strat"
            assert cfg.features_required == ["SMA_9", "SMA_21"]

    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = StrategyRegistry(Path(tmpdir))
            assert registry.load_all() == {}

    def test_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            strategies_dir = Path(tmpdir)
            (strategies_dir / "a.yaml").write_text("name: strat_a\n")
            (strategies_dir / "b.yaml").write_text("name: strat_b\n")
            registry = StrategyRegistry(strategies_dir)
            registry.load_all()
            names = registry.list()
            assert "strat_a" in names
            assert "strat_b" in names

    def test_get_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = StrategyRegistry(Path(tmpdir))
            assert registry.get("nonexistent") is None

    def test_yaml_validation_unknown_top_level_keys(self, caplog):
        caplog.set_level(logging.WARNING)
        with tempfile.TemporaryDirectory() as tmpdir:
            strategies_dir = Path(tmpdir)
            (strategies_dir / "test.yaml").write_text(
                "name: test_strat\n"
                "unkown_field: something\n"
                "extra_key: 123\n"
            )
            registry = StrategyRegistry(strategies_dir)
            registry.load_all()
            warning_messages = [r.message for r in caplog.records if "Unknown keys in strategy" in r.message]
            assert len(warning_messages) > 0
            assert "unkown_field" in warning_messages[0]
            assert "extra_key" in warning_messages[0]

    def test_reload_is_atomic_not_visible_partially_repopulated(self):
        """item #22 finding #6: a reload used to clear `self._strategies`
        immediately, then repopulate it entry-by-entry -- a `get()`/`list()`
        call from another thread mid-reload could see a strategy that
        exists in both the old and new config as temporarily gone. Proven
        by spying on `StrategyConfig.from_dict` (called once per yaml file,
        inside the loop) and asserting `self._strategies` is still exactly
        the pre-reload snapshot every single time it's invoked -- i.e. the
        real internal dict is never mutated mid-loop, only swapped in once
        at the end."""
        with tempfile.TemporaryDirectory() as tmpdir:
            strategies_dir = Path(tmpdir)
            (strategies_dir / "a.yaml").write_text("name: strat_a\n")
            (strategies_dir / "b.yaml").write_text("name: strat_b\n")
            registry = StrategyRegistry(strategies_dir)
            registry.load_all()
            pre_reload_snapshot = dict(registry._strategies)
            assert set(pre_reload_snapshot) == {"strat_a", "strat_b"}

            (strategies_dir / "c.yaml").write_text("name: strat_c\n")

            real_from_dict = StrategyConfig.from_dict
            seen_calls = []

            def spy_from_dict(data, **kwargs):
                seen_calls.append(data["name"])
                assert registry._strategies == pre_reload_snapshot, (
                    f"registry._strategies mutated mid-reload before "
                    f"processing {data['name']!r}"
                )
                return real_from_dict(data, **kwargs)

            with patch.object(StrategyConfig, "from_dict", side_effect=spy_from_dict):
                registry.load_all()

            assert set(seen_calls) == {"strat_a", "strat_b", "strat_c"}
            assert set(registry.list()) == {"strat_a", "strat_b", "strat_c"}

    def test_yaml_validation_unknown_method(self, caplog):
        caplog.set_level(logging.WARNING)
        with tempfile.TemporaryDirectory() as tmpdir:
            strategies_dir = Path(tmpdir)
            (strategies_dir / "test.yaml").write_text(
                "name: test_strat\n"
                "pipeline:\n"
                "  selection:\n"
                "    method: bogus_method\n"
            )
            registry = StrategyRegistry(strategies_dir)
            registry.load_all()
            warnings = [r.message for r in caplog.records if "Unknown selection method" in r.message]
            assert len(warnings) > 0
