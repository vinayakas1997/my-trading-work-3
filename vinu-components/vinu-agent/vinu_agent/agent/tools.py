from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}
    repeatable: bool = False
    is_readonly: bool = True

    @classmethod
    def check_available(cls) -> bool:
        return True

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        ...

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_definitions(self) -> List[Dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, params: Dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return '{"status": "error", "error": "unknown tool"}'
        try:
            return tool.execute(**params)
        except Exception as exc:
            return f'{{"status": "error", "tool": "{name}", "error": "{exc}"}}'

    @property
    def tool_names(self) -> List[str]:
        return list(self._tools.keys())
