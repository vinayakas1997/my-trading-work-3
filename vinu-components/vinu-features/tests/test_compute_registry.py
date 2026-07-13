"""Registry and recipe tests."""

from vinu_features.compute.bigger_recipe.alpha101.alpha101 import get_feature_config as alpha101
from vinu_features.compute.bigger_recipe.alpha158.alpha158 import get_feature_config as alpha158
from vinu_features.compute.bigger_recipe.alpha360.alpha360 import get_feature_config as alpha360
from vinu_features.compute.registry import apply_indicators, expand_features, parse_feature_names
from vinu_features.presets.registry import list_presets, resolve_features


def _candles(n: int = 120) -> list[dict]:
    rows = []
    for i in range(n):
        p = 100.0 + i * 0.3
        rows.append(
            {
                "ts": 1_700_000_000 + i * 86400,
                "symbol": "AAPL",
                "open": p,
                "high": p + 1,
                "low": p - 1,
                "close": p,
                "volume": 1000 + i,
            }
        )
    return rows


def test_alpha101_count():
    fields, names = alpha101()
    assert len(names) == 101


def test_alpha158_count():
    fields, names = alpha158()
    assert len(names) == 158


def test_alpha360_count():
    fields, names = alpha360()
    assert len(names) == 360


def test_expand_swing_basic():
    feats = expand_features(["swing_basic"])
    assert "sma_100" in feats


def test_apply_rsi():
    out = apply_indicators(_candles(50), ["rsi_14"])
    assert out[30]["rsi_14"] is not None


def test_list_presets_includes_alpha():
    names = {p.name for p in list_presets()}
    assert "alpha158" in names


def test_catalog_discovers_all_recipe_modules():
    from vinu_features.compute.bigger_recipe import catalog

    assert len(catalog.list_recipe_names()) == 11


def test_ml_registry_lists_nine_models():
    from vinu_features.compute.ml_models import registry

    assert len(registry.list_models()) == 9
