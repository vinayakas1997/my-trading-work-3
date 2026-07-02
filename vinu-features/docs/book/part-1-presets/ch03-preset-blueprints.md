# Chapter 3 — Preset Blueprints

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/compute/bigger_recipe/catalog.py` |
| **Status** | v1 |
| **Prerequisites** | ch02 |

## Learning objectives

- List built-in presets and resolve features from preset name.
- Submit either `preset` or explicit `features`, not both.

## Built-in presets

Defined in `PRESETS` dict: `basic_ta`, `swing_basic`, `momentum`.

```python
from vinu_features.presets.registry import get_preset, resolve_features
resolve_features(preset="swing_basic", features=[])
```

## API

`GET /presets` returns name, features, description for each blueprint.
