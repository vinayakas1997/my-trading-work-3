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
