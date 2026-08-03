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


_KNOWN_CONSTRAINTS_SENTINEL = "<known-constraints"
_FRESHNESS_WARNINGS_SENTINEL = "<freshness-warnings"
_RECENT_RESEARCH_SENTINEL = "<recent-research"


class ContextBuilder:
    def __init__(
        self,
        registry: ToolRegistry,
        memory: Any = None,
        skills_loader: Any = None,
        persistent_memory: Any = None,
        unified_memory: Any = None,
        max_memory_tokens: int = 2000,
        as_of: str | None = None,
        ground_truth_injector: Any = None,
        held_symbols: list[str] | None = None,
        facts_registry: Any = None,
        freshness_checker: Any = None,
        research_digest_reader: Any = None,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.skills_loader = skills_loader
        self.persistent_memory = persistent_memory
        self.unified_memory = unified_memory
        self.max_memory_tokens = max_memory_tokens
        self.as_of = as_of
        self._ground_truth_injector = ground_truth_injector
        self._held_symbols = held_symbols or []
        self._last_ground_truth_msg: dict | None = None
        self.facts_registry = facts_registry
        self._last_facts_msg: dict | None = None
        self.freshness_checker = freshness_checker
        self.research_digest_reader = research_digest_reader
        self._last_research_digest_msg: dict | None = None
        self._last_freshness_msg: dict | None = None

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
        current_datetime = self.as_of or _utc_now_iso()
        replay_marker = (
            "\n**REPLAY MODE — this is historical data as of the following date, not live.**"
            + " Treat every tool result as current to that time only; never assume anything happened after it."
            if self.as_of
            else ""
        )

        return _SYSTEM_PROMPT.format(
            tool_count=tool_count,
            skill_count=skill_count,
            tool_descriptions=tool_descriptions,
            skill_descriptions=skill_descriptions,
            memory_section=memory_summary,
            current_datetime=current_datetime + replay_marker,
        )

    def _extract_symbols(self, text: str) -> list[str]:
        import re
        candidates = re.findall(r"\b[A-Z]{1,5}\b", text)
        symbols = []
        for c in candidates:
            if len(c) >= 1 and len(c) <= 5 and c.isalpha():
                symbols.append(c)
        return symbols[:5]

    @property
    def last_ground_truth_msg(self) -> dict | None:
        return self._last_ground_truth_msg

    @property
    def last_facts_msg(self) -> dict | None:
        return self._last_facts_msg

    @property
    def last_freshness_msg(self) -> dict | None:
        return self._last_freshness_msg

    @property
    def last_research_digest_msg(self) -> dict | None:
        return self._last_research_digest_msg

    @staticmethod
    def is_known_constraints_msg(msg: dict) -> bool:
        content = msg.get("content", "")
        return isinstance(content, str) and content.startswith(_KNOWN_CONSTRAINTS_SENTINEL)

    @staticmethod
    def is_freshness_warnings_msg(msg: dict) -> bool:
        content = msg.get("content", "")
        return isinstance(content, str) and content.startswith(_FRESHNESS_WARNINGS_SENTINEL)

    @staticmethod
    def is_recent_research_msg(msg: dict) -> bool:
        content = msg.get("content", "")
        return isinstance(content, str) and content.startswith(_RECENT_RESEARCH_SENTINEL)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return len(text) // 4

    def build_messages(
        self, history: List[Dict], user_message: str, *, session_id: str = ""
    ) -> List[Dict]:
        messages: list[dict] = [{"role": "system", "content": self.build_system_prompt()}]

        if self._ground_truth_injector:
            _, gt_msg = self._ground_truth_injector.build_block(
                self._held_symbols, session_id=session_id,
            )
            if gt_msg is not None:
                messages.append(gt_msg)
                self._last_ground_truth_msg = gt_msg
            else:
                self._last_ground_truth_msg = None
        else:
            self._last_ground_truth_msg = None

        if self.facts_registry:
            lookup_symbols = sorted(set(self._held_symbols) | set(self._extract_symbols(user_message)))
            facts = self.facts_registry.active_facts_for(symbols=lookup_symbols)
            if facts:
                lines = [
                    f"{_KNOWN_CONSTRAINTS_SENTINEL}>",
                    "Facts already established in this project — do not "
                    "silently re-derive, contradict, or repeat a mistake "
                    "these already cover without new evidence.",
                    "",
                ]
                for f in facts:
                    lines.append(f"- [{f.kind}] {f.statement}")
                lines.append("</known-constraints>")
                facts_msg = {"role": "system", "content": "\n".join(lines)}
                messages.append(facts_msg)
                self._last_facts_msg = facts_msg
            else:
                self._last_facts_msg = None
        else:
            self._last_facts_msg = None

        if self.freshness_checker:
            lookup_symbols = sorted(set(self._held_symbols) | set(self._extract_symbols(user_message)))
            findings = self.freshness_checker.check_symbols(lookup_symbols) if lookup_symbols else []
            if findings:
                lines = [
                    f"{_FRESHNESS_WARNINGS_SENTINEL}>",
                    "The following symbols' regime/correlation data is STALE — "
                    "older than the recompute schedule allows. Treat conclusions "
                    "drawn from this angle for these symbols with reduced "
                    "confidence until it refreshes.",
                    "",
                ]
                for f in findings:
                    lines.append(
                        f"- {f['symbol']} [{f['angle']}]: last computed {f['analysis_at']} "
                        f"({f['age_days']} days ago)"
                    )
                lines.append("</freshness-warnings>")
                freshness_msg = {"role": "system", "content": "\n".join(lines)}
                messages.append(freshness_msg)
                self._last_freshness_msg = freshness_msg
            else:
                self._last_freshness_msg = None
        else:
            self._last_freshness_msg = None

        if self.research_digest_reader:
            lookup_symbols = sorted(set(self._held_symbols) | set(self._extract_symbols(user_message)))
            digests = self.research_digest_reader.check_symbols(lookup_symbols) if lookup_symbols else []
            if digests:
                lines = [
                    f"{_RECENT_RESEARCH_SENTINEL}>",
                    "A research run finished for the following symbols since "
                    "you last saw them. This is a one-time notice — it will "
                    "not repeat on later turns.",
                    "",
                ]
                for d in digests:
                    lines.append(f"- {d['symbol']} (run {d['run_id']}): {d['summary_text']}")
                lines.append("</recent-research>")
                digest_msg = {"role": "system", "content": "\n".join(lines)}
                messages.append(digest_msg)
                self._last_research_digest_msg = digest_msg
            else:
                self._last_research_digest_msg = None
        else:
            self._last_research_digest_msg = None

        messages.extend(history)

        combined_context = []
        if self.persistent_memory:
            recalls = self.persistent_memory.find_relevant(user_message, max_results=3)
            if recalls:
                combined_context.append("<agent-memories>")
                for r in recalls:
                    combined_context.append(f"- {r.name}: {r.description}")
                combined_context.append("</agent-memories>")

        if self.unified_memory:
            symbols = self._extract_symbols(user_message)
            budget_remaining = self.max_memory_tokens

            for sym in symbols:
                entries = self.unified_memory.list_by_symbol(sym, limit=10)
                if not entries:
                    continue

                block_lines: list[str] = []
                block_lines.append(f"<memory symbol={sym}>")
                for e in entries:
                    line = f"  [{e.source}/{e.memory_type}] {e.title}: {e.summary}"
                    block_lines.append(line)
                block_lines.append(f"</memory>")

                block_text = "\n".join(block_lines)
                block_tokens = self._estimate_tokens(block_text)

                if block_tokens <= budget_remaining:
                    combined_context.append(block_text)
                    budget_remaining -= block_tokens
                else:
                    trimmed_lines: list[str] = []
                    trimmed_lines.append(f"<memory symbol={sym}>")
                    sub_budget = budget_remaining
                    for e in entries:
                        line = f"  [{e.source}/{e.memory_type}] {e.title}: {e.summary}"
                        line_tokens = self._estimate_tokens(line)
                        if line_tokens <= sub_budget and sub_budget > 20:
                            trimmed_lines.append(line)
                            sub_budget -= line_tokens
                        else:
                            break
                    trimmed_lines.append(f"</memory>")
                    if len(trimmed_lines) > 2:
                        combined_context.append("\n".join(trimmed_lines))
                    break

        if combined_context:
            user_message = "\n".join(combined_context) + "\n\n" + user_message

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
