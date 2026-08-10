from typing import Any, Dict

from vinu_agent.agent.tools import BaseTool, ToolRegistry


class SayHelloTool(BaseTool):
    name = "say_hello"
    description = "Greet a person"
    parameters = {"name": {"type": "string", "description": "Person to greet"}}
    is_readonly = False

    def execute(self, **kwargs: Any) -> str:
        return f"Hello, {kwargs.get('name', 'world')}!"


class FailingTool(BaseTool):
    name = "fail"
    description = "Always fails"
    parameters: Dict[str, Any] = {}

    def execute(self, **kwargs: Any) -> str:
        raise RuntimeError("intentional failure")


class UnavailableTool(BaseTool):
    name = "unavailable"
    description = "Not available"
    parameters: Dict[str, Any] = {}

    @classmethod
    def check_available(cls) -> bool:
        return False

    def execute(self, **kwargs: Any) -> str:
        return "should not be called"


class TestBaseTool:
    def test_to_openai_schema(self) -> None:
        tool = SayHelloTool()
        schema = tool.to_openai_schema()
        assert schema == {
            "type": "function",
            "function": {
                "name": "say_hello",
                "description": "Greet a person",
                "parameters": {"name": {"type": "string", "description": "Person to greet"}},
            },
        }

    def test_check_available_default(self) -> None:
        assert SayHelloTool.check_available() is True

    def test_check_available_overridden(self) -> None:
        assert UnavailableTool.check_available() is False


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        r = ToolRegistry()
        tool = SayHelloTool()
        r.register(tool)
        assert r.get("say_hello") is tool
        assert r.get("nonexistent") is None

    def test_get_definitions(self) -> None:
        r = ToolRegistry()
        r.register(SayHelloTool())
        defs = r.get_definitions()
        assert len(defs) == 1
        assert defs[0]["function"]["name"] == "say_hello"

    def test_execute_success(self) -> None:
        r = ToolRegistry()
        r.register(SayHelloTool())
        result = r.execute("say_hello", {"name": "Alice"})
        assert result == "Hello, Alice!"

    def test_execute_unknown_tool(self) -> None:
        r = ToolRegistry()
        result = r.execute("nope", {})
        assert '"status": "error"' in result
        assert '"unknown tool"' in result

    def test_execute_exception(self) -> None:
        r = ToolRegistry()
        r.register(FailingTool())
        result = r.execute("fail", {})
        assert '"status": "error"' in result
        assert '"intentional failure"' in result

    def test_tool_names_property(self) -> None:
        r = ToolRegistry()
        r.register(SayHelloTool())
        r.register(FailingTool())
        assert sorted(r.tool_names) == ["fail", "say_hello"]

    def test_all_tools(self) -> None:
        r = ToolRegistry()
        hello = SayHelloTool()
        fail = FailingTool()
        r.register(hello)
        r.register(fail)
        assert set(r.all_tools()) == {hello, fail}

    def test_subset_includes_only_named_tools(self) -> None:
        r = ToolRegistry()
        r.register(SayHelloTool())
        r.register(FailingTool())
        sub = r.subset(["say_hello"])
        assert sub.tool_names == ["say_hello"]

    def test_subset_empty_names_is_empty_registry(self) -> None:
        r = ToolRegistry()
        r.register(SayHelloTool())
        sub = r.subset([])
        assert sub.tool_names == []

    def test_subset_skips_unknown_names_without_raising(self) -> None:
        r = ToolRegistry()
        r.register(SayHelloTool())
        sub = r.subset(["say_hello", "does_not_exist"])
        assert sub.tool_names == ["say_hello"]

    def test_subset_returns_independent_registry(self) -> None:
        r = ToolRegistry()
        r.register(SayHelloTool())
        sub = r.subset(["say_hello"])
        sub.register(FailingTool())
        assert "fail" not in r.tool_names
