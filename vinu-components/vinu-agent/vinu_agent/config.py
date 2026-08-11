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
    # Skill files change rarely -- matches vinu-live's original (pre-split)
    # worker_interval_sec default rather than inventing a new number; not
    # independently tuned. See agent/skill_audit.py's check_skill_edits().
    skill_audit_worker_interval_sec: int = 3600
    # Longer than skill-audit-worker/shadow-worker on purpose: each cycle
    # can fire real LLM team calls (screener + research), not just
    # deterministic checks -- 1800s (30 min) is a first-pass, unvalidated
    # default, same category as every other un-pinned threshold across
    # this build.
    planner_worker_interval_sec: int = 1800
    # Significance Triage delivery (Phase 7, Phase 9 scheduler-wiring) --
    # reuses TELEGRAM_TOKEN/DISCORD_TOKEN, the same env var names
    # `cli.py`'s existing `channel list` command already reads. Empty by
    # default: a channel with no token configured is simply skipped, not
    # an error -- see agent/scheduler_workers.py's significance target
    # builder. Interval shorter than planner-worker (this is detection +
    # a notification, not an LLM team run) but not so short it spams --
    # first-pass, unvalidated default, same category as every other
    # un-pinned threshold across this build.
    telegram_token: str = ""
    telegram_admin_chat_id: str = ""
    discord_token: str = ""
    discord_admin_channel_id: str = ""
    significance_worker_interval_sec: int = 900
    # Watchlist bootstrap gap: TickerSummaryStore.list_summaries() (every
    # scheduled worker's watchlist source) never gains a genuinely new
    # ticker on its own -- confirmed by reading every writer directly, each
    # is only ever invoked FOR a ticker already drawn from that same store.
    # This static, operator-provided seed list is the one place a new
    # ticker enters that loop (see agent/scheduler_workers.py's
    # discover_new_tickers/bootstrap_new_tickers) -- deliberately not an
    # invented external market-data discovery integration. Empty by
    # default: no seed list configured means no bootstrap happens, same
    # "skip, don't guess" contract as every other optional gate.
    watchlist_seed_tickers: list = field(default_factory=list)
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
        skill_audit_worker_interval_sec=int(os.environ.get("VINU_AGENT_SKILL_AUDIT_INTERVAL", "3600")),
        planner_worker_interval_sec=int(os.environ.get("VINU_AGENT_PLANNER_INTERVAL", "1800")),
        telegram_token=os.environ.get("TELEGRAM_TOKEN", ""),
        telegram_admin_chat_id=os.environ.get("VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID", ""),
        discord_token=os.environ.get("DISCORD_TOKEN", ""),
        discord_admin_channel_id=os.environ.get("VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID", ""),
        significance_worker_interval_sec=int(os.environ.get("VINU_AGENT_SIGNIFICANCE_INTERVAL", "900")),
        watchlist_seed_tickers=[
            t.strip() for t in os.environ.get("VINU_AGENT_WATCHLIST_SEED_TICKERS", "").split(",") if t.strip()
        ],
    )
