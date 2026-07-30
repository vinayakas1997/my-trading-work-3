from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_tool_catalog import generate_agent_tools


class TestGenerateAgentTools:
    def test_discovers_real_tools_with_expected_shape(self) -> None:
        catalog = generate_agent_tools()
        assert len(catalog) > 0
        assert "run_sweep_candidate" in catalog
        entry = catalog["run_sweep_candidate"]
        assert entry["name"] == "run_sweep_candidate"
        assert isinstance(entry["description"], str) and entry["description"]
        assert isinstance(entry["parameters"], dict)
        assert entry["is_readonly"] is False
        assert entry["module"] == "vinu_agent.tools.run_sweep_candidate_tool"

    def test_readonly_tool_flagged_correctly(self) -> None:
        catalog = generate_agent_tools()
        assert catalog["query_hypotheses"]["is_readonly"] is True

    def test_every_entry_has_required_fields(self) -> None:
        catalog = generate_agent_tools()
        for name, entry in catalog.items():
            assert entry["name"] == name
            assert "description" in entry
            assert "parameters" in entry
            assert "is_readonly" in entry
            assert "module" in entry
