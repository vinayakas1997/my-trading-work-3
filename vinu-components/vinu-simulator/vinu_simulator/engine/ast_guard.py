from __future__ import annotations

import ast
from typing import Any

_FORBIDDEN_IMPORTS = frozenset({
    "os", "subprocess", "shutil", "socket", "ctypes",
    "multiprocessing", "threading", "signal",
})

_FORBIDDEN_IMPORT_FROM = frozenset({
    "os", "subprocess", "shutil", "socket", "ctypes",
})

_FORBIDDEN_CALLS = frozenset({
    "eval", "exec", "compile", "__import__", "open",
})

_FORBIDDEN_ATTR_CALLS = frozenset({
    "system", "popen", "run", "call", "check_output",
    "fork", "execve", "execvp",
})


def validate_strategy_code(code: str) -> list[str]:
    violations: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"Syntax error: {exc}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name in _FORBIDDEN_IMPORTS:
                    violations.append(f"Forbidden import: {alias.name}")

        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                mod = node.module.split(".")[0]
                if mod in _FORBIDDEN_IMPORT_FROM:
                    violations.append(f"Forbidden import from: {node.module}")

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in _FORBIDDEN_CALLS:
                    violations.append(f"Forbidden call: {node.func.id}()")
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in _FORBIDDEN_ATTR_CALLS:
                    violations.append(f"Forbidden method call: {node.func.attr}()")

    return violations


def is_code_safe(code: str) -> bool:
    return len(validate_strategy_code(code)) == 0
