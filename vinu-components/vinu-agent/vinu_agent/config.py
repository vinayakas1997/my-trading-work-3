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


@dataclass
class SwarmConfig:
    max_workers: int = 4
    default_timeout: int = 300
    max_iterations: int = 25


@dataclass
class AgentConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    swarm: SwarmConfig = field(default_factory=SwarmConfig)
    max_iterations: int = 50
    skills_dir: str = ""
    user_skills_dir: str = ""
    sessions_dir: str = ""
    memory_dir: str = ""
    services: dict = field(default_factory=lambda: {
        "vinu_simulator": os.environ.get("VINU_SIMULATOR_API_URL", "http://localhost:8085"),
        "vinu_tools": os.environ.get("VINU_TOOLS_API_URL", "http://localhost:8082"),
        "vinu_news": os.environ.get("VINU_NEWS_API_URL", "http://localhost:8080"),
        "vinu_initial_analysis": os.environ.get("VINU_INITIAL_ANALYSIS_API_URL", "http://localhost:8083"),
        "vinu_stock_price": os.environ.get("VINU_STOCK_PRICE_API_URL", "http://localhost:8081"),
        "vinu_strategy": os.environ.get("VINU_STRATEGY_API_URL", "http://localhost:8084"),
        "vinu_research": os.environ.get("VINU_RESEARCH_API_URL", "http://localhost:8086"),
    })


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
        ),
        swarm=SwarmConfig(
            max_workers=int(os.environ.get("VINU_SWARM_MAX_WORKERS", "4")),
            default_timeout=int(os.environ.get("VINU_SWARM_TIMEOUT", "300")),
            max_iterations=int(os.environ.get("VINU_SWARM_MAX_ITERATIONS", "25")),
        ),
        max_iterations=int(os.environ.get("VINU_AGENT_MAX_ITERATIONS", "50")),
        skills_dir=os.environ.get("VINU_AGENT_SKILLS_DIR", os.environ.get("VINU_AGENT_SKILLS_PATH", str(Path(__file__).parent.parent / "skills"))),
        user_skills_dir=os.environ.get("VINU_AGENT_USER_SKILLS_DIR", ""),
        sessions_dir=os.environ.get("VINU_AGENT_SESSIONS_DIR", str(data_root / "sessions")),
        memory_dir=os.environ.get("VINU_AGENT_MEMORY_DIR", str(data_root / "memory")),
    )
