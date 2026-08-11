from __future__ import annotations

import json

from vinu_agent.tools.factor_analysis_tool import FactorAnalysisTool


class TestFactorAnalysisTool:
    def test_count_action_returns_real_registry_count(self) -> None:
        """Regression test for a dead import (vinu_tools.compute.alpha_registry.Registry,
        which doesn't exist) that made every call to this tool raise ModuleNotFoundError.
        The real API is vinu_tools.compute.registry.get_alpha_registry()."""
        result = json.loads(FactorAnalysisTool().execute(action="count"))
        assert result["status"] == "ok"
        assert result["count"] > 0

    def test_list_themes(self) -> None:
        result = json.loads(FactorAnalysisTool().execute(action="list_themes"))
        assert result["status"] == "ok"
        assert isinstance(result["themes"], list)
        assert len(result["themes"]) > 0

    def test_describe_unknown_factor_is_an_error(self) -> None:
        result = json.loads(FactorAnalysisTool().execute(action="describe", alpha_id="not_a_real_factor"))
        assert result["status"] == "error"
