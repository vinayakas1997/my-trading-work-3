import time
from typing import Any, Dict, List, Optional

from .tools import ToolRegistry

_SYSTEM_PROMPT = """You are Vinu, an AI quantitative trading research assistant. You have access to {tool_count} tools and {skill_count} specialized knowledge domains.

## Available Tools
{tool_descriptions}

## Research Methodology (Skills)
{skill_descriptions}

## Current Context
{memory_section}
Current time: {current_datetime}

## How to Use Tools
- Call tools by name with the required parameters
- Tools return JSON strings — parse them for results
- If a tool fails, analyze the error and try a different approach
- You can call multiple tools in sequence to complete complex tasks

## Workflow Rules
1. For backtest tasks: load_skill("strategy-generate") first, then follow its workflow
2. For research tasks: load_skill("research-discipline") first, then conduct research
3. Always cite specific numbers from tool results — never fabricate data
4. When analyzing results, compute metrics yourself to verify tool output
5. If a tool returns an error, explain what went wrong and suggest fixes"""


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class ContextBuilder:
    def __init__(
        self,
        registry: ToolRegistry,
        memory: Any = None,
        skills_loader: Any = None,
        persistent_memory: Any = None,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.skills_loader = skills_loader
        self.persistent_memory = persistent_memory

    def build_system_prompt(self) -> str:
        tool_count = len(self.registry.tool_names)
        skill_count = (
            len(self.skills_loader.get_descriptions())
            if self.skills_loader
            else 0
        )
        tool_descriptions = self._format_tool_descriptions()
        skill_descriptions = (
            self.skills_loader.get_descriptions()
            if self.skills_loader
            else "No skills loaded."
        )
        memory_summary = self.memory.to_summary() if self.memory else ""

        return _SYSTEM_PROMPT.format(
            tool_count=tool_count,
            skill_count=skill_count,
            tool_descriptions=tool_descriptions,
            skill_descriptions=skill_descriptions,
            memory_section=memory_summary,
            current_datetime=_utc_now_iso(),
        )

    def build_messages(
        self, history: List[Dict], user_message: str
    ) -> List[Dict]:
        messages = [{"role": "system", "content": self.build_system_prompt()}]
        messages.extend(history)

        if self.persistent_memory:
            recalls = self.persistent_memory.find_relevant(user_message, max_results=3)
            if recalls:
                recalled_text = "\n".join(
                    f"- {r.name}: {r.description}" for r in recalls
                )
                user_message = (
                    f"<recalled-memories>\n{recalled_text}\n</recalled-memories>\n\n"
                    + user_message
                )

        messages.append({"role": "user", "content": user_message})
        return messages

    def _format_tool_descriptions(self) -> str:
        lines = []
        for tool_def in self.registry.get_definitions():
            func = tool_def["function"]
            params = func.get("parameters", {}).get("properties", {})
            required = func.get("parameters", {}).get("required", [])
            param_strs = []
            for pname, pinfo in params.items():
                req_marker = " (required)" if pname in required else ""
                param_strs.append(
                    f"    - {pname}: {pinfo.get('description', '')}{req_marker}"
                )
            lines.append(f"### {func['name']}\n{func['description']}")
            if param_strs:
                lines.append("  Parameters:")
                lines.extend(param_strs)
        return "\n".join(lines)
