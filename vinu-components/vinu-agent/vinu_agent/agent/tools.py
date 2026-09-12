import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

LOG = logging.getLogger(__name__)


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
        # Tool schemas are static once registered; AgentLoop calls
        # get_definitions() on every LLM turn (_call_llm), so rebuilding the
        # list from scratch each time is pure repeated work over the life of
        # a run. Invalidated on register() -- the only thing that can change
        # the schema list.
        self._definitions_cache: Optional[List[Dict[str, Any]]] = None

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        self._definitions_cache = None

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_definitions(self) -> List[Dict[str, Any]]:
        if self._definitions_cache is None:
            self._definitions_cache = [t.to_openai_schema() for t in self._tools.values()]
        # A fresh list per call (same schema dicts, cheap to copy) so a
        # caller that mutates the list it gets back can't corrupt the cache.
        return list(self._definitions_cache)

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

    def all_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def subset(self, names: List[str]) -> "ToolRegistry":
        """A new registry containing only the named tools -- used to scope
        a team manager or specialist to just the tools its AGENT.md/TEAM.md
        declares, instead of the full shared tool pool. Unknown names are
        logged and skipped rather than raising, since a typo in a markdown
        config file shouldn't crash the whole team."""
        out = ToolRegistry()
        for name in names:
            tool = self._tools.get(name)
            if tool is None:
                LOG.warning("subset(): unknown tool %r requested, skipping", name)
                continue
            out.register(tool)
        return out
