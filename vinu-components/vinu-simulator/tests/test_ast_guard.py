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
