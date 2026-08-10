import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class LLMConfig:
    provider: str = "openai"
    model_name: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    timeout: int = 120
    #: Explicit override for the model's real context window (tokens). 0
    #: means "auto-detect via the backing server's /models endpoint" — see
    #: agent/llm.py::resolve_context_window. Set this when the server
    #: doesn't expose a queryable context length, or to pin a known value
    #: without depending on a network call at startup.
    context_window: int = 0


@dataclass
class SwarmConfig:
    max_workers: int = 4
    default_timeout: int = 300
    max_iterations: int = 25


@dataclass
class AgentConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    #: Independent LLM config for the orchestrator's own top-level loop --
    #: None means "share vinu_agent.llm" (today's behavior, unchanged).
    #: Teams/specialists always use `llm` above, not this one -- see
    #: New-talk-agents/01-orchestrator-and-teams-architecture.md.
    orchestrator_llm: Optional[LLMConfig] = None
    swarm: SwarmConfig = field(default_factory=SwarmConfig)
    max_iterations: int = 50
    skills_dir: str = ""
    user_skills_dir: str = ""
    teams_dir: str = ""
    orchestrator_dir: str = ""
    sessions_dir: str = ""
    memory_dir: str = ""
    services: dict = field(default_factory=lambda: {
        "vinu_simulator": os.environ.get("VINU_SIMULATOR_API_URL", "http://localhost:8085"),
        "vinu_tools": os.environ.get("VINU_TOOLS_API_URL", "http://localhost:8082"),
        "vinu_news": os.environ.get("VINU_NEWS_API_URL", "http://localhost:8080"),
        "vinu_initial_analysis": os.environ.get("VINU_INITIAL_ANALYSIS_API_URL", "http://localhost:8083"),
        "vinu_stock_price": os.environ.get("VINU_STOCK_PRICE_API_URL", "http://localhost:8081"),
        "vinu_strategy": os.environ.get("VINU_STRATEGY_API_URL", "http://localhost:8084"),
        "vinu_research": os.environ.get("VINU_RESEARCH_API_URL", "http://localhost:8087"),
        "vinu_portfolio": os.environ.get("VINU_PORTFOLIO_API_URL", "http://localhost:8090"),
        "vinu_live": os.environ.get("VINU_LIVE_API_URL", "http://localhost:8091"),
    })


def _load_orchestrator_llm_config() -> Optional[LLMConfig]:
    """Only builds a distinct orchestrator LLMConfig if at least one
    VINU_ORCHESTRATOR_LLM_* var is actually set -- otherwise returns None
    so the orchestrator transparently shares the same LLM as teams/
    specialists (today's behavior, unchanged for anyone who hasn't opted
    in). Fields left unset fall back to LLMConfig's own plain defaults,
    not the shared VINU_LLM_* values -- mixing a shared local model's
    name with a different provider (e.g. VINU_LLM_MODEL="qwen36-35B" under
    provider="openai") would silently be nonsense."""
    keys = (
        "VINU_ORCHESTRATOR_LLM_PROVIDER",
        "VINU_ORCHESTRATOR_LLM_MODEL",
        "VINU_ORCHESTRATOR_LLM_BASE_URL",
        "VINU_ORCHESTRATOR_LLM_API_KEY",
    )
    if not any(os.environ.get(k) for k in keys):
        return None
    return LLMConfig(
        provider=os.environ.get("VINU_ORCHESTRATOR_LLM_PROVIDER", "openai"),
        model_name=os.environ.get("VINU_ORCHESTRATOR_LLM_MODEL", "gpt-4o-mini"),
        api_key=os.environ.get("VINU_ORCHESTRATOR_LLM_API_KEY", ""),
        base_url=os.environ.get("VINU_ORCHESTRATOR_LLM_BASE_URL", ""),
        timeout=int(os.environ.get("VINU_ORCHESTRATOR_LLM_TIMEOUT", "120")),
        context_window=int(os.environ.get("VINU_ORCHESTRATOR_LLM_CONTEXT_WINDOW", "0")),
    )


def load_config() -> AgentConfig:
    load_dotenv()
    data_root = Path(os.environ.get("VINU_AGENT_DATA_ROOT", Path.home() / ".vinu"))
    return AgentConfig(
        llm=LLMConfig(
            provider=os.environ.get("VINU_LLM_PROVIDER", "openai"),
            model_name=os.environ.get("VINU_LLM_MODEL", "gpt-4o-mini"),
            api_key=os.environ.get("VINU_LLM_API_KEY", ""),
            base_url=os.environ.get("VINU_LLM_BASE_URL", ""),
            timeout=int(os.environ.get("VINU_LLM_TIMEOUT", "120")),
            context_window=int(os.environ.get("VINU_LLM_CONTEXT_WINDOW", "0")),
        ),
        orchestrator_llm=_load_orchestrator_llm_config(),
        swarm=SwarmConfig(
            max_workers=int(os.environ.get("VINU_SWARM_MAX_WORKERS", "4")),
            default_timeout=int(os.environ.get("VINU_SWARM_TIMEOUT", "300")),
            max_iterations=int(os.environ.get("VINU_SWARM_MAX_ITERATIONS", "25")),
        ),
        max_iterations=int(os.environ.get("VINU_AGENT_MAX_ITERATIONS", "50")),
        skills_dir=os.environ.get("VINU_AGENT_SKILLS_DIR", os.environ.get("VINU_AGENT_SKILLS_PATH", str(Path(__file__).parent.parent / "skills"))),
        user_skills_dir=os.environ.get("VINU_AGENT_USER_SKILLS_DIR", ""),
        teams_dir=os.environ.get("VINU_AGENT_TEAMS_DIR", str(Path(__file__).parent.parent / "teams")),
        orchestrator_dir=os.environ.get("VINU_AGENT_ORCHESTRATOR_DIR", str(Path(__file__).parent.parent / "orchestrator")),
        sessions_dir=os.environ.get("VINU_AGENT_SESSIONS_DIR", str(data_root / "sessions")),
        memory_dir=os.environ.get("VINU_AGENT_MEMORY_DIR", str(data_root / "memory")),
    )
