from __future__ import annotations

from vinu_simulator.engine.ast_guard import is_code_safe, validate_strategy_code


class TestAstGuard:
    def test_clean_code_passes(self):
        code = """
from typing import Any
import pandas as pd
import numpy as np

class SignalEngine:
    def compute_signals(self, data):
        return data.close * 0
"""
        violations = validate_strategy_code(code)
        assert len(violations) == 0
        assert is_code_safe(code) is True

    def test_forbidden_import_os(self):
        code = "import os\nos.system('ls')"
        violations = validate_strategy_code(code)
        assert any("os" in v for v in violations)
        assert is_code_safe(code) is False

    def test_forbidden_import_subprocess(self):
        code = "import subprocess"
        violations = validate_strategy_code(code)
        assert any("subprocess" in v for v in violations)

    def test_forbidden_call_eval(self):
        code = "eval('1+1')"
        violations = validate_strategy_code(code)
        assert any("eval" in v for v in violations)

    def test_forbidden_call_exec(self):
        code = "exec('x = 1')"
        violations = validate_strategy_code(code)
        assert any("exec" in v for v in violations)

    def test_forbidden_method_system(self):
        code = """
import pandas as pd
df = pd.DataFrame()
df.to_csv.system('ls')
"""
        violations = validate_strategy_code(code)
        assert any("system" in v for v in violations)

    def test_syntax_error_returns_violation(self):
        code = "def foo( bar"
        violations = validate_strategy_code(code)
        assert len(violations) > 0
        assert any("Syntax" in v for v in violations)

    def test_forbidden_from_import(self):
        code = "from os import path"
        violations = validate_strategy_code(code)
        assert any("os" in v for v in violations)


class TestSandboxEscapeGap:
    """item #13 finding #1: the guard used to only inspect `ast.Call`
    nodes, so any escape technique that reaches os/subprocess without a
    blocklisted call name (an `ast.Attribute` reached via reflection
    rather than a plain function call) passed through unblocked. These
    are the exact two techniques the audit named."""

    def test_subclasses_walk_is_blocked(self):
        code = "x = ().__class__.__base__.__subclasses__()"
        violations = validate_strategy_code(code)
        assert any("__subclasses__" in v for v in violations)
        assert any("__class__" in v for v in violations)
        assert any("__base__" in v for v in violations)
        assert is_code_safe(code) is False

    def test_globals_builtins_reach_is_blocked(self):
        code = "x = (lambda: None).__globals__['__builtins__']['eval']"
        violations = validate_strategy_code(code)
        assert any("__globals__" in v for v in violations)
        assert is_code_safe(code) is False

    def test_bare_dunder_attribute_access_is_blocked_even_without_a_call(self):
        """The gap wasn't just about calls -- `.__globals__` is never
        itself called in the technique above, just accessed and
        subscripted. Confirms the check fires on ast.Attribute
        independent of ast.Call."""
        code = "g = (1).__class__"
        violations = validate_strategy_code(code)
        assert any("__class__" in v for v in violations)

    def test_previously_missing_forbidden_calls_are_now_blocked(self):
        for name in ("input", "exit", "quit", "breakpoint", "vars", "globals"):
            violations = validate_strategy_code(f"{name}()")
            assert any(name in v for v in violations), f"{name}() should be forbidden"

    def test_legitimate_strategy_code_with_normal_attribute_access_still_passes(self):
        """Regression guard for the fix itself -- ordinary attribute
        access (dataframe columns, method calls) must not start
        tripping the new dunder-attribute check."""
        code = """
import pandas as pd
import numpy as np

class SignalEngine:
    def compute_signals(self, data):
        sma = data.close.rolling(20).mean()
        return np.where(data.close > sma, 1.0, -1.0)
"""
        violations = validate_strategy_code(code)
        assert violations == []
        assert is_code_safe(code) is True
