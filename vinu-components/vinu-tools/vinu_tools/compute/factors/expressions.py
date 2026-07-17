from __future__ import annotations

import operator
from typing import Any

import numpy as np
import pandas as pd

from vinu_tools.compute.registry import AlphaRegistry as Registry
from vinu_tools.compute.operators import rank, zscore, ts_mean, ts_std, ts_sum, ts_max, ts_min

_REGISTRY: Registry | None = None


def _registry() -> Registry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = Registry()
    return _REGISTRY


_FUNCTIONS: dict[str, Any] = {
    "rank": lambda x: rank(x.values) if isinstance(x, pd.DataFrame) else rank(x),
    "zscore": lambda x: zscore(x.values) if isinstance(x, pd.DataFrame) else zscore(x),
    "ts_mean": lambda x, d: ts_mean(x.values if isinstance(x, pd.DataFrame) else x, int(d)),
    "ts_std": lambda x, d: ts_std(x.values if isinstance(x, pd.DataFrame) else x, int(d)),
    "ts_sum": lambda x, d: ts_sum(x.values if isinstance(x, pd.DataFrame) else x, int(d)),
    "ts_max": lambda x, d: ts_max(x.values if isinstance(x, pd.DataFrame) else x, int(d)),
    "ts_min": lambda x, d: ts_min(x.values if isinstance(x, pd.DataFrame) else x, int(d)),
    "abs": lambda x: np.abs(x.values if isinstance(x, pd.DataFrame) else x),
    "neg": lambda x: -(x.values if isinstance(x, pd.DataFrame) else x),
    "sign": lambda x: np.sign(x.values if isinstance(x, pd.DataFrame) else x),
    "delay": lambda x, d: _delay(x, int(d)),
}


def _delay(x: pd.DataFrame | np.ndarray, d: int) -> pd.DataFrame | np.ndarray:
    if isinstance(x, pd.DataFrame):
        return x.shift(d)
    arr = np.roll(x, d, axis=0)
    arr[:d] = np.nan
    return arr


def _safe_div(a, b):
    a_arr = a.values if isinstance(a, pd.DataFrame) else np.asarray(a, dtype=float)
    b_arr = b.values if isinstance(b, pd.DataFrame) else np.asarray(b, dtype=float)
    out = np.zeros(np.broadcast_shapes(a_arr.shape, b_arr.shape), dtype=float)
    valid = (b_arr != 0) & ~np.isnan(b_arr)
    if a_arr.ndim < out.ndim:
        a_arr = np.expand_dims(a_arr, axis=-1)
    np.divide(a_arr, b_arr, out=out, where=valid)
    if isinstance(a, pd.DataFrame) or isinstance(b, pd.DataFrame):
        idx = a.index if isinstance(a, pd.DataFrame) else b.index
        cols = a.columns if isinstance(a, pd.DataFrame) else b.columns
        return pd.DataFrame(out, index=idx, columns=cols)
    return out

_BINOPS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": _safe_div,
}


def compute_expression(expression: str, panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Evaluate a factor expression string against a panel of OHLCV data.

    Factors are referenced by their alpha ID (e.g. ``alpha101_001``).
    Supported operators: ``+``, ``-``, ``*``, ``/``, and functions
    ``rank()``, ``zscore()``, ``ts_mean()``, ``ts_std()``, ``ts_sum()``,
    ``ts_max()``, ``ts_min()``, ``abs()``, ``neg()``, ``sign()``, ``delay()``.

    Example expressions::

        alpha101_001 + alpha101_002
        rank(alpha101_001) * zscore(gtja191_005)
        ts_mean(alpha101_001 - alpha101_002, 10) / ts_std(alpha101_001, 10)
        (alpha101_001 + alpha101_002) / 2

    Args:
        expression: Factor expression string.
        panel: Dict of DataFrame arrays keyed by column name (close, open, high, low, volume, returns, etc.)

    Returns:
        A DataFrame with the computed expression result.
    """
    _registry().force_rescan()
    tokens = _tokenize(expression)
    ast = _parse(tokens)
    return _evaluate(ast, panel)


def list_expression_variables(expression: str) -> list[str]:
    """Extract alpha ID references from an expression without computing."""
    tokens = _tokenize(expression)
    ast = _parse(tokens)
    return sorted(_find_ids(ast))


# --- Tokenizer ---

_TOKENS_RE = None


def _tokenize(expr: str) -> list[dict[str, Any]]:
    import re
    pattern = r"(\d+\.?\d*|[A-Za-z_]\w*|[+\-*/(),])"
    tokens: list[dict[str, Any]] = []
    for m in re.finditer(pattern, expr):
        raw = m.group(0)
        if raw in ("+", "-", "*", "/", "(", ")", ","):
            tokens.append({"type": "op", "value": raw})
        elif raw[0].isdigit() or "." in raw:
            tokens.append({"type": "num", "value": float(raw) if "." in raw else int(raw)})
        elif raw in _FUNCTIONS:
            tokens.append({"type": "func", "value": raw})
        else:
            tokens.append({"type": "id", "value": raw})
    return tokens


# --- Parser (recursive descent) ---

class _ParseError(ValueError):
    pass


def _parse(tokens: list[dict[str, Any]]) -> dict[str, Any]:
    pos = 0

    def peek() -> dict[str, Any] | None:
        return tokens[pos] if pos < len(tokens) else None

    def consume(expected_type: str | None = None) -> dict[str, Any]:
        nonlocal pos
        if pos >= len(tokens):
            raise _ParseError("Unexpected end of expression")
        tok = tokens[pos]
        if expected_type and tok["type"] != expected_type:
            raise _ParseError(f"Expected {expected_type}, got {tok}")
        pos += 1
        return tok

    def parse_atom() -> dict[str, Any]:
        tok = peek()
        if tok is None:
            raise _ParseError("Expected value")

        if tok["type"] == "id":
            consume()
            return {"type": "ref", "value": tok["value"]}

        if tok["type"] == "num":
            consume()
            return {"type": "num", "value": tok["value"]}

        if tok["type"] == "func":
            consume()
            args: list[dict[str, Any]] = []
            if peek() and peek()["type"] == "op" and peek()["value"] == "(":
                consume("op")  # (
                args.append(parse_expr())
                while peek() and peek()["type"] == "op" and peek()["value"] == ",":
                    consume()  # ,
                    args.append(parse_expr())
                if not (peek() and peek()["type"] == "op" and peek()["value"] == ")"):
                    raise _ParseError("Expected ')'")
                consume("op")  # )
            else:
                # Single arg without parens: rank alpha101_001
                args.append(parse_atom())
            return {"type": "call", "func": tok["value"], "args": args}

        if tok["type"] == "op" and tok["value"] == "(":
            consume()
            node = parse_expr()
            if not (peek() and peek()["type"] == "op" and peek()["value"] == ")"):
                raise _ParseError("Expected ')'")
            consume("op")
            return node

        if tok["type"] == "op" and tok["value"] == "-":
            consume()
            return {"type": "call", "func": "neg", "args": [parse_atom()]}

        raise _ParseError(f"Unexpected token: {tok}")

    def parse_mul() -> dict[str, Any]:
        left = parse_atom()
        while peek() and peek()["type"] == "op" and peek()["value"] in ("*", "/"):
            op = consume()["value"]
            right = parse_atom()
            left = {"type": "binop", "op": op, "left": left, "right": right}
        return left

    def parse_expr() -> dict[str, Any]:
        left = parse_mul()
        while peek() and peek()["type"] == "op" and peek()["value"] in ("+", "-"):
            op = consume()["value"]
            right = parse_mul()
            left = {"type": "binop", "op": op, "left": left, "right": right}
        return left

    result = parse_expr()
    if pos != len(tokens):
        raise _ParseError(f"Unexpected tokens after expression: {tokens[pos:]}")
    return result


# --- Evaluator ---

def _compute_factor(alpha_id: str, panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    mod = _registry().get(alpha_id)
    if mod is None:
        raise ValueError(f"Unknown factor: {alpha_id}")
    import importlib
    # Convert file path to importable module path
    # e.g. .../vinu_tools/compute/factors/singles/alpha101/alpha_001.py
    #    -> vinu_tools.compute.factors.singles.alpha101.alpha_001
    parts = mod.path.parts
    try:
        idx = parts.index("vinu_tools")
    except ValueError:
        raise RuntimeError(f"Cannot determine module path for {mod.path}")
    dotted = ".".join(parts[idx:]).removesuffix(".py")
    module = importlib.import_module(dotted)
    return module.compute(panel)


def _evaluate(node: dict[str, Any], panel: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if node["type"] == "ref":
        result = _compute_factor(node["value"], panel)
        return result

    if node["type"] == "num":
        return node["value"]

    if node["type"] == "call":
        func_name = node["func"]
        fn = _FUNCTIONS.get(func_name)
        if fn is None:
            raise ValueError(f"Unknown function: {func_name}")
        args = [_evaluate(a, panel) for a in node["args"]]
        result = fn(*args)
        if isinstance(result, np.ndarray):
            template = _evaluate(node["args"][0], panel)
            return pd.DataFrame(result, index=template.index, columns=template.columns)
        return result

    if node["type"] == "binop":
        left = _evaluate(node["left"], panel)
        right = _evaluate(node["right"], panel)
        op_fn = _BINOPS.get(node["op"])
        if op_fn is None:
            raise ValueError(f"Unknown operator: {node['op']}")
        return op_fn(left, right)

    raise ValueError(f"Unknown node type: {node['type']}")


def _find_ids(node: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    if node["type"] == "ref":
        ids.append(node["value"])
    elif node["type"] in ("call",):
        for a in node.get("args", []):
            ids.extend(_find_ids(a))
    elif node["type"] == "binop":
        ids.extend(_find_ids(node["left"]))
        ids.extend(_find_ids(node["right"]))
    return ids
