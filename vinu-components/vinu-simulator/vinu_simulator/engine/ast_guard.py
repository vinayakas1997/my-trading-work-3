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
    "input", "exit", "quit", "breakpoint", "vars", "globals",
})

_FORBIDDEN_ATTR_CALLS = frozenset({
    "system", "popen", "run", "call", "check_output",
    "fork", "execve", "execvp",
})

# item #13 finding #1: the loop below used to only inspect `ast.Call`
# nodes, so any sandbox-escape technique that reaches `os`/`subprocess`
# via attribute *access* rather than a blocklisted call name -- e.g.
# `().__class__.__base__.__subclasses__()` (the final call's own name,
# `__subclasses__`, was never in `_FORBIDDEN_ATTR_CALLS`) or
# `(lambda: None).__globals__['__builtins__']['eval']` (never a `Call`
# at the point `__globals__` is touched at all) -- passed through
# completely unblocked. `exec(code, namespace)` in service.py runs
# with a plain dict, so the real `__builtins__` (eval/open/etc.
# included) is present in the executed namespace regardless; this
# blocklist is the only thing standing between that and arbitrary code
# reachable through it. Every `ast.Attribute` node is now checked on
# its own, independent of whether it's part of a `Call` -- both the
# `.__subclasses__()` case (an `ast.Attribute` that also happens to be
# a `Call`'s `.func`) and the `.__globals__[...]` case (an
# `ast.Attribute` used as a plain value, never called) are the same
# node type and get caught the same way.
_FORBIDDEN_ATTRS = frozenset({
    "__class__", "__base__", "__bases__", "__mro__", "__subclasses__",
    "__globals__", "__builtins__", "__builtin__", "__code__",
    "__closure__", "__func__", "__self__", "__dict__", "__getattribute__",
    "__reduce__", "__reduce_ex__", "__init_subclass__", "__subclasshook__",
    "__import__", "__loader__", "__spec__",
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

        elif isinstance(node, ast.Attribute):
            if node.attr in _FORBIDDEN_ATTRS:
                violations.append(f"Forbidden attribute access: {node.attr}")

    return violations


def is_code_safe(code: str) -> bool:
    return len(validate_strategy_code(code)) == 0
