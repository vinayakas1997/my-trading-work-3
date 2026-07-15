"""MCP server exposing vinu-agent tools via the Model Context Protocol.

Usage:
    python -m vinu_agent.mcp_server

Claude Desktop config (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "vinu-agent": {
          "command": "python",
          "args": ["-m", "vinu_agent.mcp_server"]
        }
      }
    }
"""

import json
import logging
import sys
from typing import Any, Dict, List, Optional

from .agent.tools import ToolRegistry
from .config import load_config
from .tools import build_registry

logger = logging.getLogger(__name__)


class MCPServer:
    def __init__(self) -> None:
        self._registry: Optional[ToolRegistry] = None
        self._initialized = False

    def _get_registry(self) -> ToolRegistry:
        if self._registry is None:
            config = load_config()
            self._registry = build_registry(services_config=config.services)
        return self._registry

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._initialized = True
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "vinu-agent",
                "version": "0.1.0",
            },
        }

    def _handle_list_tools(self, params: Dict[str, Any]) -> Dict[str, Any]:
        registry = self._get_registry()
        tools = []
        for name in registry.tool_names:
            tool = registry.get(name)
            if tool:
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.parameters or {"type": "object", "properties": {}},
                })
        return {"tools": tools}

    def _handle_call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        registry = self._get_registry()

        tool = registry.get(name)
        if not tool:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }

        try:
            result = tool.execute(**arguments)
            if isinstance(result, str):
                return {"content": [{"type": "text", "text": result}]}
            return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            }

    def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    def dispatch(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_list_tools,
            "tools/call": self._handle_call_tool,
            "ping": self._handle_ping,
        }

        handler = handlers.get(method)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        try:
            result = handler(params)
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(exc)},
            }

    def run_stdio(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.dispatch(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                sys.stdout.write(json.dumps({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }) + "\n")
                sys.stdout.flush()
            except Exception as exc:
                sys.stdout.write(json.dumps({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(exc)},
                }) + "\n")
                sys.stdout.flush()


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    server = MCPServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
