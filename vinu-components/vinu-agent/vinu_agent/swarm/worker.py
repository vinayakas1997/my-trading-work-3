import json
from typing import Any, Dict, Optional

from ..agent.loop import AgentLoop
from ..agent.tools import ToolRegistry
from ..tools import build_registry


def run_worker(
    task_prompt: str,
    agent_name: str,
    role: str,
    context: Optional[str],
    services_config: Optional[dict] = None,
) -> Dict[str, Any]:
    system_prompt = f"""You are {agent_name}, serving as {role} in a multi-agent committee.

Your task:
{task_prompt}

{context or ""}

You have access to all vinu data tools. Use them to gather evidence.
Respond with a thorough analysis citing specific numbers.
Your output will be reviewed by other agents and a synthesizer."""
    from ..service import LLMWrapper
    from ..config import AgentConfig
    config = AgentConfig()
    llm = LLMWrapper(config)

    registry = build_registry(services_config=services_config or {})

    loop = AgentLoop(
        registry=registry,
        llm=llm,
        max_iterations=15,
    )

    messages = [{"role": "system", "content": system_prompt}]
    if context:
        messages.append({"role": "user", "content": f"Context from peers:\n{context}\n\nNow produce your analysis."})

    result = loop.run(messages=messages)

    return {
        "status": result.get("status", "completed"),
        "content": result.get("content", ""),
        "iterations": result.get("iterations", 0),
        "token_usage": result.get("token_usage", {}),
    }
