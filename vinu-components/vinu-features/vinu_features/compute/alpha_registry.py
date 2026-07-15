from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

from vinu_features.compute.alpha_meta import ALPHA_THEMES, AlphaMeta

LOG = logging.getLogger(__name__)

_ALPHA_META_VAR = "__alpha_meta__"


class AlphaModule:
    def __init__(self, path: Path, meta: AlphaMeta) -> None:
        self.path = path
        self.meta = meta

    def __repr__(self) -> str:
        return f"AlphaModule(id={self.meta.id}, path={self.path})"


class Registry:
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(__file__).resolve().parent / "alpha_factors"
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
