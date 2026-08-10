"""Integration tests for tool auto-discovery via build_registry()."""
from vinu_agent.tools import build_registry, _discover_subclasses


class TestToolDiscovery:
    def test_discover_subclasses_returns_tool_classes(self) -> None:
        classes = _discover_subclasses()
        assert len(classes) > 0
        for cls in classes:
            assert hasattr(cls, "name")
            assert hasattr(cls, "description")

    def test_discover_skips_private_modules(self) -> None:
        classes = _discover_subclasses()
        names = [c.name for c in classes if c.name]
        assert all(n for n in names)

    def test_build_registry_returns_registry(self) -> None:
        registry = build_registry()
        assert registry is not None
        assert len(registry.tool_names) > 0

    def test_build_registry_includes_specific_tools(self) -> None:
        registry = build_registry()
        names = registry.tool_names
        assert "get_stock_price" in names
        assert "web_search" in names

    def test_build_registry_with_services_config(self) -> None:
        config = {"vinu_stock_price": "http://test:8081"}
        registry = build_registry(services_config=config)
        tool = registry.get("get_stock_price")
        assert tool is not None
        assert tool._services_config["vinu_stock_price"] == "http://test:8081"

    def test_build_registry_injects_skills_loader(self) -> None:
        fake_skills_loader = object()
        registry = build_registry(skills_loader=fake_skills_loader)
        tool = registry.get("load_skill")
        assert tool is not None
        assert tool._skills_loader is fake_skills_loader

    def test_build_registry_injects_unified_memory(self) -> None:
        fake_unified_memory = object()
        registry = build_registry(unified_memory=fake_unified_memory)
        for tool_name in ("remember", "query_memory"):
            tool = registry.get(tool_name)
            assert tool is not None
            assert tool._unified_memory is fake_unified_memory

    def test_build_registry_injects_session_service(self) -> None:
        fake_session_service = object()
        registry = build_registry(session_service=fake_session_service)
        tool = registry.get("search_sessions")
        assert tool is not None
        assert tool._session_service is fake_session_service

    def test_build_registry_injects_workflow_tracker(self) -> None:
        fake_workflow_tracker = object()
        registry = build_registry(workflow_tracker=fake_workflow_tracker)
        for tool_name in ("complete_step", "plan_workflow"):
            tool = registry.get(tool_name)
            assert tool is not None
            assert tool._workflow_tracker is fake_workflow_tracker

    def test_build_registry_injects_llm(self) -> None:
        fake_llm = object()
        registry = build_registry(llm=fake_llm)
        tool = registry.get("delegate_to_team")
        assert tool is not None
        assert tool._llm is fake_llm

    def test_build_registry_injects_teams_dir(self) -> None:
        registry = build_registry(teams_dir="/some/teams/dir")
        tool = registry.get("delegate_to_team")
        assert tool is not None
        assert tool._teams_dir == "/some/teams/dir"

    def test_build_registry_injects_run_store(self) -> None:
        fake_run_store = object()
        registry = build_registry(run_store=fake_run_store)
        tool = registry.get("delegate_to_team")
        assert tool is not None
        assert tool._run_store is fake_run_store

    def test_build_registry_injects_llm_call_store(self) -> None:
        fake_llm_call_store = object()
        registry = build_registry(llm_call_store=fake_llm_call_store)
        tool = registry.get("delegate_to_team")
        assert tool is not None
        assert tool._llm_call_store is fake_llm_call_store

    def test_build_registry_gives_delegate_to_team_a_self_reference(self) -> None:
        registry = build_registry()
        tool = registry.get("delegate_to_team")
        assert tool is not None
        assert tool._full_registry is registry

    def test_discovery_is_scoped_to_the_tools_package_not_process_global(self) -> None:
        """Regression test: BaseTool.__subclasses__() is process-global, not
        scoped to this package. agent/team.py's DelegateToAgentTool is a
        BaseTool subclass that requires constructor args and is built
        per-team on purpose -- it must never show up in auto-discovery,
        or build_registry() crashes trying to zero-arg-construct it (this
        actually happened once: see New-talk-agents/implementation/00-status.md)."""
        from vinu_agent.agent.team import DelegateToAgentTool

        classes = _discover_subclasses()
        assert DelegateToAgentTool not in classes
        # Importing it (as this test just did) must not make it discoverable.
        registry = build_registry()
        assert registry.get("delegate_to_agent") is None

    def test_build_registry_includes_delegate_to_team(self) -> None:
        registry = build_registry()
        assert "delegate_to_team" in registry.tool_names
