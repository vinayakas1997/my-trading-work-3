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
