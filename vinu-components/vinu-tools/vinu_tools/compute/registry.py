from __future__ import annotations

import ast
import importlib
import logging
from pathlib import Path
from typing import Any, Sequence

from vinu_tools.compute.alpha_meta import ALPHA_THEMES, AlphaMeta
from vinu_tools.compute.factors.recipes import catalog as recipe_catalog
from vinu_tools.compute.indicators._module_names import INDICATOR_MODULE_NAMES
from vinu_tools.compute.indicators._shared.spec import IndicatorMeta, meta_from_module

LOG = logging.getLogger(__name__)

_ALPHA_META_VAR = "__alpha_meta__"
_INDICATOR_MODULES: list[Any] | None = None
_ALPHA158_NAMES: set[str] | None = None
_ALPHA360_NAMES: set[str] | None = None
_ALPHA101_NAMES: set[str] | None = None
_ALPHA_REGISTRY: AlphaRegistry | None = None

# ──────────────────────────────────────────────
# SECTION 1: ALPHA FACTOR DISCOVERY (from alpha_registry.py)
# ──────────────────────────────────────────────

class AlphaModule:
    def __init__(self, path: Path, meta: AlphaMeta) -> None:
        self.path = path
        self.meta = meta

    def __repr__(self) -> str:
        return f"AlphaModule(id={self.meta.id}, path={self.path})"


class AlphaRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(__file__).resolve().parent / "factors" / "singles"
        self._modules: dict[str, AlphaModule] = {}
        self._scanned = False

    def _scan(self) -> None:
        if self._scanned:
            return
        self._modules.clear()
        if not self._root.exists():
            LOG.warning("Alpha root does not exist: %s", self._root)
            self._scanned = True
            return
        for py_file in sorted(self._root.rglob("*.py")):
            if py_file.name == "__init__.py":
                continue
            try:
                meta = self._extract_meta(py_file)
                if meta is not None:
                    self._modules[meta.id] = AlphaModule(py_file, meta)
            except Exception as exc:
                LOG.debug("Failed to parse %s: %s", py_file, exc)
        self._scanned = True

    def _extract_meta(self, path: Path) -> AlphaMeta | None:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == _ALPHA_META_VAR:
                        if isinstance(node.value, ast.Dict):
                            return self._dict_to_meta(node.value)
        return None

    def _dict_to_meta(self, d: ast.Dict) -> AlphaMeta:
        kv: dict[str, Any] = {}
        for k, v in zip(d.keys, d.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                try:
                    val = ast.literal_eval(v)
                    kname = k.value
                    if kname == "theme":
                        if isinstance(val, list):
                            val = str(val[0]) if val else "other"
                        if val not in ALPHA_THEMES:
                            val = "other"
                    if kname == "universe" and isinstance(val, list):
                        val = val[0] if val else "us_equity"
                    if kname == "frequency" and isinstance(val, list):
                        val = val[0] if val else "1d"
                    kv[kname] = val
                except (ValueError, SyntaxError):
                    kv[k.value] = None
        return AlphaMeta.from_dict(kv)

    def list_alphas(self) -> list[AlphaModule]:
        self._scan()
        return list(self._modules.values())

    def get(self, alpha_id: str) -> AlphaModule | None:
        self._scan()
        return self._modules.get(alpha_id)

    def count(self) -> int:
        self._scan()
        return len(self._modules)

    def force_rescan(self) -> None:
        self._scanned = False
        self._scan()


def get_alpha_registry() -> AlphaRegistry:
    global _ALPHA_REGISTRY
    if _ALPHA_REGISTRY is None:
        _ALPHA_REGISTRY = AlphaRegistry()
    return _ALPHA_REGISTRY


# ──────────────────────────────────────────────
# SECTION 2: INDICATOR CATALOG (from feature_catalog.py)
# ──────────────────────────────────────────────

_INDICATOR_META: dict[str, IndicatorMeta] | None = None
_PRESET_CACHE: list[dict] | None = None


def _load_indicator_modules() -> list[Any]:
    global _INDICATOR_MODULES
    if _INDICATOR_MODULES is None:
        _INDICATOR_MODULES = [
            importlib.import_module(f"vinu_tools.compute.indicators.{name}.{name}")
            for name in INDICATOR_MODULE_NAMES
        ]
    return _INDICATOR_MODULES


def _load_indicator_meta() -> dict[str, IndicatorMeta]:
    global _INDICATOR_META
    if _INDICATOR_META is None:
        _INDICATOR_META = {}
        for mod in _load_indicator_modules():
            if hasattr(mod, "KIND"):
                meta = meta_from_module(mod)
                _INDICATOR_META[meta.kind] = meta
    return _INDICATOR_META


def list_indicators() -> list[IndicatorMeta]:
    return list(_load_indicator_meta().values())


def get_indicator(kind: str) -> IndicatorMeta:
    key = kind.strip().lower()
    meta = _load_indicator_meta().get(key)
    if meta is None:
        raise ValueError(f"Unknown indicator kind: {kind}")
    return meta


def get_indicator_module(kind: str) -> Any:
    key = kind.strip().lower()
    for mod in _load_indicator_modules():
        if getattr(mod, "KIND", None) == key:
            return mod
    raise ValueError(f"Unknown indicator kind: {kind}")


def list_indicator_kinds() -> list[str]:
    return sorted(_load_indicator_meta())


def format_indicator_help(kind: str | None = None) -> str:
    if kind:
        meta = get_indicator(kind)
        lines = [
            f"{meta.kind} — {meta.description}",
            "",
            "Params:",
        ]
        if meta.params:
            for name, pdef in meta.params.items():
                bounds = ""
                if pdef.min is not None or pdef.max is not None:
                    bounds = f" (min={pdef.min}, max={pdef.max})"
                lines.append(f"  {name}: {pdef.type}, default={pdef.default}{bounds}")
        else:
            lines.append("  (none)")
        lines.extend(["", "Output columns:"])
        for col in meta.output_columns:
            lines.append(f"  {col}")
        lines.extend(["", "Examples (CLI):"])
        for ex in meta.examples:
            if ":" in ex or ex == meta.kind:
                lines.append(f"  --feature {ex}")
            else:
                lines.append(f"  --features {ex}")
        return "\n".join(lines)

    lines = ["Indicators:", ""]
    for meta in list_indicators():
        param_summary = ", ".join(f"{k}={p.default}" for k, p in meta.params.items()) or "none"
        lines.append(f"  {meta.kind:<22} {meta.description}  [{param_summary}]")
    lines.extend(["", "Presets:", ""])
    for p in _list_presets():
        lines.append(f"  {p['name']:<22} {p['description']}  ({p['feature_count']} features)")
    lines.extend(["", "Run: vinu-tools features help <kind>"])
    return "\n".join(lines)


# ──────────────────────────────────────────────
# SECTION 3: PRESETS (from presets/registry.py)
# ──────────────────────────────────────────────

from dataclasses import dataclass


@dataclass(frozen=True)
class FeaturePreset:
    name: str
    features: tuple[str, ...]
    description: str = ""


def get_preset(name: str) -> FeaturePreset:
    key = name.strip().lower()
    if key not in recipe_catalog.list_recipe_names():
        known = ", ".join(sorted(recipe_catalog.list_recipe_names()))
        raise ValueError(f"Unknown preset '{name}'. Known: {known}")
    meta = recipe_catalog.get_recipe_meta(name)
    feats = recipe_catalog.resolve(name)
    return FeaturePreset(name=name.strip().lower(), features=tuple(feats), description=meta.get("description", ""))


def list_presets() -> list[FeaturePreset]:
    return [
        FeaturePreset(
            name=p["name"],
            features=tuple(p["features"]),
            description=p.get("description", ""),
        )
        for p in _list_presets()
    ]


def resolve_features(*, preset: str | None, features: list[str]) -> list[str]:
    if preset and features:
        raise ValueError("Provide either preset or features, not both")
    if preset:
        return list(recipe_catalog.resolve(preset))
    if not features:
        raise ValueError("Either preset or features is required")
    return list(features)


def _list_presets() -> list[dict]:
    return [
        {
            "name": p["name"],
            "description": p["description"],
            "features": list(p["features"]),
            "feature_count": p["feature_count"],
        }
        for p in recipe_catalog.list_all_presets()
    ]


# ──────────────────────────────────────────────
# SECTION 4: CENTRAL DISPATCH (from original registry.py)
# ──────────────────────────────────────────────


def _alpha_name_sets() -> tuple[set[str], set[str], set[str]]:
    global _ALPHA158_NAMES, _ALPHA360_NAMES, _ALPHA101_NAMES
    if _ALPHA158_NAMES is None:
        _ALPHA158_NAMES = set(recipe_catalog.resolve("alpha158"))
        _ALPHA360_NAMES = set(recipe_catalog.resolve("alpha360"))
        _ALPHA101_NAMES = set(recipe_catalog.resolve("alpha101_benchmark"))
    return _ALPHA158_NAMES, _ALPHA360_NAMES, _ALPHA101_NAMES


def expand_recipe(name: str) -> list[str]:
    return list(recipe_catalog.resolve(name))


def expand_features(names: Sequence[str]) -> list[str]:
    out: list[str] = []
    for raw in names:
        name = raw.strip().lower()
        if not name:
            continue
        if recipe_catalog.is_recipe(name):
            out.extend(recipe_catalog.resolve(name))
        else:
            out.append(name)
    seen: set[str] = set()
    deduped: list[str] = []
    for n in out:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped


def parse_feature_names(names: Sequence[str]) -> list[str]:
    from vinu_tools.compute.feature_spec import validate_and_resolve  # noqa: PLC0415
    return validate_and_resolve(list(names))


def validate_feature_name(name: str) -> None:
    if recipe_catalog.is_recipe(name):
        return
    a158, a360, a101 = _alpha_name_sets()
    if name.upper() in a158 or name.upper() in a360 or name.upper() in a101:
        return
    if _find_indicator_module(name) is not None:
        return
    raise ValueError(f"Unknown feature: {name}")


def list_known_features() -> list[str]:
    base: list[str] = []
    for meta in list_indicators():
        params = {k: v.default for k, v in meta.params.items()}
        for col in meta.output_columns:
            base.append(col.format(**params))
    for p in (5, 10, 20, 50, 100):
        base.append(f"sma_{p}")
    for p in (12, 26, 50):
        base.append(f"ema_{p}")
    return base + recipe_catalog.list_recipe_names()


def warmup_bars_for_features(features: Sequence[str]) -> int:
    expanded = expand_features(features)
    need = 1
    a158, a360, a101 = _alpha_name_sets()
    for name in expanded:
        if recipe_catalog.is_recipe(name):
            need = max(need, recipe_catalog.warmup_for(name))
        elif name in a158 or name in a360 or name in a101:
            need = max(need, 60)
        else:
            mod = _find_indicator_module(name)
            if mod is not None:
                need = max(need, mod.warmup_for(name))
    return need


def apply_indicators(rows: list[dict], names: Sequence[str]) -> list[dict]:
    if not rows or not names:
        return rows
    expanded = expand_features(names)
    out = [dict(r) for r in rows]
    a158, a360, a101 = _alpha_name_sets()

    if any(n in a101 for n in expanded):
        subset = {n for n in expanded if n in a101}
        cols = recipe_catalog.compute_recipe(rows, "alpha101_benchmark", subset=subset)
        for i, row in enumerate(out):
            for n in expanded:
                if n in cols:
                    row[n] = cols[n][i]
    if any(n in a158 for n in expanded):
        subset = {n for n in expanded if n in a158}
        cols = recipe_catalog.compute_recipe(rows, "alpha158", subset=subset)
        for i, row in enumerate(out):
            for n in expanded:
                if n in cols:
                    row[n] = cols[n][i]
    if any(n in a360 for n in expanded):
        subset = {n for n in expanded if n in a360}
        cols = recipe_catalog.compute_recipe(rows, "alpha360", subset=subset)
        for i, row in enumerate(out):
            for n in expanded:
                if n in cols:
                    row[n] = cols[n][i]

    for name in expanded:
        if name.upper() in a158 or name.upper() in a360 or name.upper() in a101:
            continue
        mod = _find_indicator_module(name)
        if mod is None:
            continue
        cols = mod.compute(rows, name=name)
        for i, row in enumerate(out):
            for col, vals in cols.items():
                if col == name:
                    row[col] = vals[i]
                elif col in expanded and col not in row:
                    row[col] = vals[i]
    return out


def _find_indicator_module(name: str) -> Any | None:
    for mod in _get_indicator_modules():
        if mod.matches(name):
            return mod
    return None


def _get_indicator_modules() -> list[Any]:
    return _load_indicator_modules()
