from __future__ import annotations

import ast
import operator
from typing import Any

_ALLOWED_FUNCTIONS = {
    "max": max,
    "min": min,
    "abs": abs,
    "round": round,
}

_ALLOWED_NODES = (
    ast.Expression,
    ast.Constant,
    ast.Name,
    ast.UnaryOp,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.Call,
    ast.Load,
)


class ExpressionError(ValueError):
    pass


def _validate(node: ast.AST) -> None:
    if not isinstance(node, _ALLOWED_NODES):
        raise ExpressionError(f"Unsupported expression node: {type(node).__name__}")
    for child in ast.iter_child_nodes(node):
        _validate(child)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ExpressionError("Only simple function calls are allowed")
        if node.func.id not in _ALLOWED_FUNCTIONS:
            raise ExpressionError(f"Function '{node.func.id}' is not allowed")


def _eval_node(node: ast.AST, context: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return 1.0 if node.value else 0.0
        if isinstance(node.value, int):
            return float(node.value)
        return float(node.value) if node.value is not None else 0.0
    if isinstance(node, ast.Name):
        val = context.get(node.id)
        if val is None:
            raise ExpressionError(f"Unknown variable: '{node.id}'")
        return float(val)
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, context)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, context)
        right = _eval_node(node.right, context)
        op_map: dict[type, Any] = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.Mod: operator.mod,
        }
        op_func = op_map.get(type(node.op))
        if op_func is None:
            raise ExpressionError(f"Unsupported operator: {type(node.op).__name__}")
        return float(op_func(left, right))
    if isinstance(node, ast.Call):
        func = _ALLOWED_FUNCTIONS[node.func.id]
        args = [_eval_node(a, context) for a in node.args]
        if node.func.id == "round" and len(args) == 2:
            args[1] = int(args[1])
        return float(func(*args))
    raise ExpressionError(f"Unsupported node: {type(node).__name__}")


def evaluate_expression(expr: str, context: dict[str, float]) -> float:
    if not expr or not expr.strip():
        raise ExpressionError("Expression is empty")
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise ExpressionError(f"Invalid expression syntax: {e}") from e
    _validate(tree)
    ctx_lower = {k.lower(): v for k, v in context.items()}
    return _eval_node(tree.body, _CaseInsensitiveContext(context, ctx_lower))


class _CaseInsensitiveContext:
    def __init__(self, original: dict[str, float], lower: dict[str, float]):
        self._original = original
        self._lower = lower

    def get(self, key: str) -> float | None:
        val = self._original.get(key)
        if val is not None:
            return val
        val = self._lower.get(key.lower())
        if val is not None:
            return val
        return self._original.get(key.upper())
