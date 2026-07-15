# After-Plan: LLM Agent Infrastructure for vinu-components

## Purpose

This document is the complete implementation plan for adapting Vibe-Trading's autonomous agent infrastructure into vinu-components. It is written so that **any future agent** can read it, understand the architecture, and implement the work without needing additional context.

**Prerequisites**: Read these files first:
1. `advanced-part-2-plan.md` — Part 2 plan (ML fix, session features, news features)
2. `mimo-agent-analysis-vibe-vinu.md` — Feature-by-feature comparison of Vibe-Trading vs vinu-components

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Phase A — Agent Core](#3-phase-a--agent-core)
4. [Phase B — Session Management](#4-phase-b--session-management)
5. [Phase C — Skills System](#5-phase-c--skills-system)
6. [Phase D — Swarm Orchestration](#6-phase-d--swarm-orchestration)
7. [Phase E — IM Channels](#7-phase-e--im-channels)
8. [Phase F — Persistent Memory + Config](#8-phase-f--persistent-memory--config)
9. [Tool Mapping — All 7 Services as Agent Tools](#9-tool-mapping--all-7-services-as-agent-tools)
10. [Skills Library — 15 Core Skills](#10-skills-library--15-core-skills)
11. [Swarm Presets — 4 Multi-Agent Configs](#11-swarm-presets--4-multi-agent-configs)
12. [API Endpoints](#12-api-endpoints)
13. [File Tree](#13-file-tree)
14. [Key Design Decisions](#14-key-design-decisions)
15. [Migration Path](#15-migration-path)

---

## 1. Executive Summary

### What We're Building

A new service called **`vinu-agent`** that becomes the single intelligent entry point to the entire vinu-components ecosystem. It is:

1. **An autonomous ReAct agent** — an LLM that reasons, calls tools (the 7 vinu services), and iterates until a goal is met
2. **A session-based chat system** — persistent conversations with SSE streaming
3. **A swarm orchestrator** — multi-agent teams for complex research tasks
4. **An IM-connected assistant** — Telegram/Discord/Slack integration
5. **A knowledge library** — progressive-disclosure skills for research methodology

### Why This Matters

Today, vinu-components is a set of CLI commands and HTTP APIs. You run `vinu-research run --symbol AAPL` and get a report. The agent infrastructure transforms it into:

- "Hey Vinu, research AAPL momentum decay and tell me if it still works" (IM chat)
- "Run the investment committee on NVDA" (swarm orchestration)
- "What happened in my last 3 research sessions?" (session search)
- "Keep monitoring my strategies daily" (scheduled research via agent)

### The Mental Model

```
BEFORE (today):
  User → CLI command → vinu-research → calls other services → report

AFTER (with agent):
  User → Chat (IM/Web/CLI) → vinu-agent → reasons about goal →
    calls vinu-features (get indicators) →
    calls vinu-simulator (run backtest) →
    calls vinu-correlation (check news impact) →
    calls vinu-research (iterate strategy) →
    streams progress via SSE →
    returns final answer
```

---

## 2. Architecture Overview

### New Service: `vinu-agent`

```
vinu-agent/
  vinu_agent/
    __init__.py
    config.py              # VinuAgentConfig (Pydantic EnvConfig pattern)
    service.py             # AgentService facade (context manager)
    cli.py                 # CLI entry points
    server/
      __init__.py
      app.py               # FastAPI create_app() factory
      routes_sessions.py   # Session CRUD + message send + SSE stream
      routes_swarm.py      # Swarm run/cancel/status
      routes_channels.py   # IM channel status/start/stop
      routes_system.py     # /health, /status
      schemas.py           # Pydantic request/response models
    agent/
      __init__.py
      loop.py              # AgentLoop — the ReAct core (1607 LOC equivalent)
      tools.py             # BaseTool ABC + ToolRegistry
      context.py           # ContextBuilder — system prompt + message assembly
      skills.py            # SkillsLoader — progressive disclosure
      frontmatter.py       # YAML frontmatter parser for skills
    session/
      __init__.py
      service.py           # SessionService — message handling + attempt lifecycle
      store.py             # SessionStore — JSONL persistence
      events.py            # EventBus — SSE streaming
      models.py            # Session, Message, Attempt dataclasses
      search.py            # FTS5 full-text search
    swarm/
      __init__.py
      runtime.py           # SwarmRuntime — DAG orchestration
      worker.py            # Worker loop (mini ReAct per agent)
      models.py            # SwarmRun, SwarmTask, SwarmEvent
      store.py             # SwarmStore — JSON persistence
      task_store.py        # DAG validation + topological sort
      presets/             # YAML preset definitions
        investment_committee.yaml
        quant_strategy_desk.yaml
        risk_committee.yaml
        research_team.yaml
    channels/
      __init__.py
      base.py              # BaseChannel ABC
      registry.py          # Auto-discovery + plugin system
      manager.py           # ChannelManager — message dispatch
      telegram.py          # Telegram adapter (first IM)
      discord.py           # Discord adapter (second IM)
    memory/
      __init__.py
      persistent.py        # PersistentMemory — cross-session research memory
    tools/
      __init__.py          # Auto-discovery + build_registry()
      backtest_tool.py     # Calls vinu-simulator
      features_tool.py     # Calls vinu-features
      news_tool.py         # Calls vinu-news
      correlation_tool.py  # Calls vinu-correlation
      stock_price_tool.py  # Calls vinu-stock-price
      strategy_tool.py     # Calls vinu-strategy
      research_tool.py     # Calls vinu-research
      web_search_tool.py   # Web search (if needed)
      load_skill_tool.py   # Loads full skill docs on demand
      remember_tool.py     # Saves to persistent memory
      session_search_tool.py  # FTS5 search across sessions
  tests/
    test_loop.py
    test_tools.py
    test_session.py
    test_swarm.py
```

### Dependency Graph

```
vinu-agent
  ├── vinu-lib (ResilientClient, config, SQLite, Parquet)
  ├── vinu-simulator (backtest execution)
  ├── vinu-features (indicator computation)
  ├── vinu-news (news data)
  ├── vinu-correlation (news-price correlation)
  ├── vinu-stock-price (price data)
  ├── vinu-strategy (strategy pipeline)
  └── vinu-research (research loop, walk-forward, validation)
```

### Port Allocation

| Service | Port | Notes |
|---------|------|-------|
| vinu-news | 8080 | existing |
| vinu-stock-price | 8081 | existing |
| vinu-features | 8082 | existing |
| vinu-correlation | 8083 | existing |
| vinu-strategy | 8084 | existing |
| vinu-simulator | 8085 | existing |
| vinu-agent | 8086 | **NEW** — the brain |

---

## 3. Phase A — Agent Core

**Goal**: Build the autonomous ReAct reasoning engine that can call all 7 vinu services as tools.

### A.1 — BaseTool ABC + ToolRegistry

**File**: `vinu-agent/vinu_agent/agent/tools.py`

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseTool(ABC):
    """Base class for all agent tools. Each tool wraps a vinu service endpoint."""
    
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}   # JSON Schema format
    repeatable: bool = False           # Can be called multiple times
    is_readonly: bool = True           # Read tools can run in parallel

    @classmethod
    def check_available(cls) -> bool:
        """Override to check if dependencies (API keys, services) are available."""
        return True

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Execute the tool. Must return a JSON string."""
        ...

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry of all available tools. Wraps execution in try/except for safety."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_definitions(self) -> List[Dict[str, Any]]:
        """All tools in OpenAI function calling format."""
        return [t.to_openai_schema() for t in self._tools.values()]

    def execute(self, name: str, params: Dict[str, Any]) -> str:
        """Execute a tool. ALWAYS returns JSON — never raises."""
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
```

**Why this works**: The `execute()` method guarantees JSON output. The LLM never sees Python tracebacks. The `check_available()` classmethod allows lazy registration — tools whose services are down simply don't register.

### A.2 — Agent Loop (ReAct Core)

**File**: `vinu-agent/vinu_agent/agent/loop.py`

This is the most complex file (~1600 lines). Key structure:

```python
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .tools import ToolRegistry


class AgentLoop:
    """
    ReAct agent loop with 5-layer context management.
    
    The loop:
    1. Builds system prompt + history + user message
    2. Sends to LLM with tool definitions
    3. If LLM returns tool calls → execute tools → append results → loop
    4. If LLM returns text → return as final answer
    5. Manages context window via 5 compression layers
    """

    def __init__(
        self,
        registry: ToolRegistry,
        llm: Any,  # ChatLLM instance
        memory: Any = None,  # WorkspaceMemory
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        max_iterations: int = 50,
        persistent_memory: Any = None,
    ) -> None:
        self.registry = registry
        self.llm = llm
        self.memory = memory
        self.event_callback = event_callback
        self.max_iterations = max_iterations
        self.persistent_memory = persistent_memory
        self._cancel_event = threading.Event()
        self._called_ok: set = set()
        self._previous_summary: str = ""

    def run(self, messages: List[Dict], session_id: str = "") -> Dict:
        """
        Main entry point. Runs the ReAct loop until:
        - LLM returns a final text answer
        - max_iterations reached
        - Cancel event set
        
        Returns: {"status": "completed", "content": "...", "iterations": N}
        """
        # 1. Build context (system prompt + history + user message)
        # 2. Main loop: while iteration < max_iterations
        #    a. Apply context management layers
        #    b. Call LLM with tool definitions
        #    c. If tool_calls → _process_tool_calls()
        #    d. If content → return final answer
        #    e. Increment iteration
        # 3. If max_iterations reached → force text output
        ...

    def cancel(self) -> None:
        """Cooperative cancellation — checked at every iteration boundary."""
        self._cancel_event.set()

    def _process_tool_calls(self, tool_calls: List[Dict]) -> List[Dict]:
        """
        Execute tool calls with read/write batching:
        - Consecutive readonly tools → parallel (ThreadPoolExecutor)
        - Write tools → serial (one at a time)
        """
        ...

    def _apply_context_layers(self, messages: List[Dict]) -> List[Dict]:
        """
        5-layer context management:
        Layer 1 (microcompact): Prune old tool results beyond most recent 3
        Layer 2 (context_collapse): Fold long text blocks > 2400 chars
        Layer 3 (auto_compact): LLM-powered structured summary
        Layer 4 (compact tool): Model explicitly requests compression
        Layer 5 (iterative update): Update previous summary with new turns
        """
        ...
```

**The 5-Layer Context Management (critical detail)**:

| Layer | Trigger | Action | Cost |
|-------|---------|--------|------|
| 1. microcompact | Token usage > 50% | Replace tool results > 100 chars with `"[cleared]"` beyond most recent 3 | Zero API calls |
| 2. context_collapse | Token usage > 70% | For messages > 6 from end, keep head 900 + tail 500 chars, collapse middle | Zero API calls |
| 3. auto_compact | Token usage > 100% | LLM summarizes entire conversation into structured format | 1 LLM call |
| 4. compact tool | LLM decides | Model calls `compact` tool explicitly with optional focus_topic | 1 LLM call |
| 5. iterative update | Subsequent compactions | Update previous summary with new turns (avoids info decay) | 1 LLM call |

**Token estimation**: Use a simple heuristic (1 token ≈ 4 chars for English, ~1.5 chars for CJK) rather than calling a tokenizer. This is fast and approximate.

### A.3 — Context Builder

**File**: `vinu-agent/vinu_agent/agent/context.py`

```python
class ContextBuilder:
    """Builds the system prompt and message history for the LLM."""

    def __init__(
        self,
        registry: ToolRegistry,
        memory: Any,  # WorkspaceMemory
        skills_loader: Any = None,  # SkillsLoader
        persistent_memory: Any = None,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.skills_loader = skills_loader
        self.persistent_memory = persistent_memory

    def build_system_prompt(self) -> str:
        """
        Constructs the system prompt with:
        - Tool descriptions (formatted from registry)
        - Skill summaries (one-line per skill)
        - Memory summary (run_dir, tool counters)
        - Current datetime
        - Task routing instructions
        """
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
        """
        Assembles full message list:
        1. System prompt
        2. History messages
        3. User message (with auto-recalled memories injected)
        """
        messages = [{"role": "system", "content": self.build_system_prompt()}]
        messages.extend(history)
        
        # Auto-recall relevant memories
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
        """Format all tools as readable descriptions for the system prompt."""
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
```

**System Prompt Template** (the `_SYSTEM_PROMPT` constant):

```
You are Vinu, an AI quantitative trading research assistant. You have access to {tool_count} tools and {skill_count} specialized knowledge domains.

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
5. If a tool returns an error, explain what went wrong and suggest fixes
```

### A.4 — Tool Auto-Discovery

**File**: `vinu-agent/vinu_agent/tools/__init__.py`

```python
import importlib
import pkgutil
from pathlib import Path

from ..agent.tools import BaseTool, ToolRegistry

_SUBCLASSES_CACHE: list = []


def _discover_subclasses() -> list:
    """Auto-discover all BaseTool subclasses by importing all modules in tools/."""
    global _SUBCLASSES_CACHE
    if _SUBCLASSES_CACHE:
        return _SUBCLASSES_CACHE
    
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name.startswith("_"):
            continue
        importlib.import_module(f".{module_name}", package=__package__)
    
    _SUBCLASSES_CACHE = list(BaseTool.__subclasses__())
    return _SUBCLASSES_CACHE


def build_registry(
    *,
    persistent_memory=None,
    session_id: str = "",
    event_callback=None,
    services_config: dict = None,
) -> ToolRegistry:
    """
    Build the tool registry:
    1. Discover all BaseTool subclasses
    2. Check availability (skip unavailable)
    3. Inject dependencies (memory, session_id, service URLs)
    4. Register each tool
    """
    registry = ToolRegistry()
    subclasses = _discover_subclasses()
    
    for cls in subclasses:
        if not cls.check_available():
            continue
        # Inject dependencies
        tool = cls()
        if hasattr(tool, "_persistent_memory"):
            tool._persistent_memory = persistent_memory
        if hasattr(tool, "_session_id"):
            tool._session_id = session_id
        if hasattr(tool, "_event_callback"):
            tool._event_callback = event_callback
        if services_config and hasattr(tool, "_services_config"):
            tool._services_config = services_config
        registry.register(tool)
    
    return registry
```

---

## 4. Phase B — Session Management

**Goal**: Persistent conversations with SSE streaming. Every user interaction creates a session, every agent response creates an attempt.

### B.1 — Session Models

**File**: `vinu-agent/vinu_agent/session/models.py`

```python
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class AttemptStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Session:
    session_id: str = field(default_factory=_new_id)
    title: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    last_attempt_id: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_attempt_id": self.last_attempt_id,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Session":
        return cls(
            session_id=d["session_id"],
            title=d.get("title", ""),
            status=SessionStatus(d.get("status", "active")),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            last_attempt_id=d.get("last_attempt_id"),
            config=d.get("config", {}),
        )


@dataclass
class Message:
    message_id: str = field(default_factory=_new_id)
    session_id: str = ""
    role: str = "user"  # user | assistant | system | tool
    content: str = ""
    created_at: str = field(default_factory=_utc_now_iso)
    linked_attempt_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "linked_attempt_id": self.linked_attempt_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Message":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Attempt:
    attempt_id: str = field(default_factory=_new_id)
    session_id: str = ""
    parent_attempt_id: Optional[str] = None
    status: AttemptStatus = AttemptStatus.PENDING
    prompt: str = ""
    run_dir: Optional[str] = None
    summary: Optional[str] = None
    react_trace: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=_utc_now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def mark_running(self) -> None:
        self.status = AttemptStatus.RUNNING
        self.started_at = _utc_now_iso()

    def mark_completed(self, summary: str = "") -> None:
        self.status = AttemptStatus.COMPLETED
        self.summary = summary
        self.completed_at = _utc_now_iso()

    def mark_failed(self, error: str) -> None:
        self.status = AttemptStatus.FAILED
        self.error = error
        self.completed_at = _utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "parent_attempt_id": self.parent_attempt_id,
            "status": self.status.value,
            "prompt": self.prompt,
            "run_dir": self.run_dir,
            "summary": self.summary,
            "error": self.error,
            "metrics": self.metrics,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
```

### B.2 — Session Store (JSONL Persistence)

**File**: `vinu-agent/vinu_agent/session/store.py`

```
Disk layout:
  sessions/
    {session_id}/
      session.json           # Session metadata
      messages.jsonl          # Append-only message log (one JSON per line)
      attempts/
        {attempt_id}/
          attempt.json        # Attempt metadata
```

Key implementation details:
- `append_message()`: Opens JSONL in append mode, writes JSON line + `os.fsync()` for crash safety
- `get_messages()`: Reads all lines, parses JSON, returns last N messages
- `delete_session()`: `shutil.rmtree()` on the session directory
- `list_sessions()`: Scans all dirs, loads `session.json`, sorts by `updated_at` desc

### B.3 — Event Bus (SSE Streaming)

**File**: `vinu-agent/vinu_agent/session/events.py`

```python
import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional


@dataclass
class SSEEvent:
    event_id: Optional[str] = field(default_factory=lambda: uuid.uuid4().hex[:16])
    event_type: str = "message"
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = json.dumps(self.data, default=str)
        return f"id: {self.event_id}\nevent: {self.event_type}\ndata: {payload}\n\n"


class EventBus:
    """
    Thread-safe event bus for SSE streaming.
    
    - publish() is thread-safe (called from agent threads)
    - subscribe() is async (consumed by FastAPI SSE endpoint)
    - Buffer replays events to new subscribers (reconnection support)
    """

    def __init__(self, max_buffer_size: int = 500) -> None:
        self._lock = threading.Lock()
        self._buffer: list = []
        self._max_buffer_size = max_buffer_size
        self._subscribers: Dict[str, asyncio.Queue] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Call during FastAPI startup to inject the asyncio event loop."""
        self._loop = loop

    def publish(self, event: SSEEvent) -> None:
        """Thread-safe publish. Called from agent worker threads."""
        with self._lock:
            self._buffer.append(event)
            if len(self._buffer) > self._max_buffer_size:
                self._buffer = self._buffer[-self._max_buffer_size:]
            for queue in self._subscribers.values():
                if self._loop:
                    self._loop.call_soon_threadsafe(queue.put_nowait, event)

    async def subscribe(
        self, session_id: str, last_event_id: Optional[str] = None
    ) -> AsyncGenerator[SSEEvent, None]:
        """Async generator yielding events for a session. Supports replay."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subscribers[session_id] = queue
        
        # Replay buffered events since last_event_id
        if last_event_id:
            for event in self._replay(session_id, last_event_id):
                yield event

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield SSEEvent(event_type="heartbeat", data={})
        finally:
            with self._lock:
                self._subscribers.pop(session_id, None)

    def _replay(self, session_id: str, last_event_id: str) -> list:
        """Find events after last_event_id for the given session."""
        found = False
        result = []
        for event in self._buffer:
            if event.session_id != session_id:
                continue
            if found:
                result.append(event)
            if event.event_id == last_event_id:
                found = True
        return result
```

### B.4 — Session Service

**File**: `vinu-agent/vinu_agent/session/service.py`

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from .events import EventBus, SSEEvent
from .models import Attempt, AttemptStatus, Message, Session
from .store import SessionStore


class SessionService:
    """
    Orchestrates session lifecycle:
    1. User sends message → append to store → emit event
    2. Create Attempt → schedule agent loop in thread pool
    3. Agent produces response → append assistant message → emit event
    4. Update attempt status
    """

    _AGENT_EXECUTOR = ThreadPoolExecutor(max_workers=4)

    def __init__(self, store: SessionStore, event_bus: EventBus) -> None:
        self.store = store
        self.event_bus = event_bus
        self._active_loops: Dict[str, Any] = {}  # session_id -> AgentLoop

    async def send_message(
        self, session_id: str, content: str, role: str = "user"
    ) -> Dict:
        """
        Handle incoming message:
        1. Append user message to store
        2. Emit message.received event
        3. Create Attempt
        4. Schedule _run_attempt() as background task
        5. Return {message_id, attempt_id}
        """
        session = self.store.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Append user message
        msg = Message(
            session_id=session_id,
            role=role,
            content=content,
        )
        self.store.append_message(session_id, msg)

        # Emit event
        self.event_bus.publish(SSEEvent(
            event_type="message.received",
            data=msg.to_dict(),
            session_id=session_id,
        ))

        if role != "user":
            return {"message_id": msg.message_id}

        # Create attempt
        attempt = Attempt(
            session_id=session_id,
            prompt=content,
        )
        self.store.save_attempt(session_id, attempt)

        self.event_bus.publish(SSEEvent(
            event_type="attempt.created",
            data=attempt.to_dict(),
            session_id=session_id,
        ))

        # Schedule background execution
        asyncio.create_task(self._run_attempt(session_id, attempt.attempt_id))

        return {"message_id": msg.message_id, "attempt_id": attempt.attempt_id}

    async def _run_attempt(self, session_id: str, attempt_id: str) -> None:
        """Run the agent loop in a thread pool, then create assistant message."""
        attempt = self.store.get_attempt(session_id, attempt_id)
        attempt.mark_running()

        try:
            # Build agent components (in executor to avoid blocking)
            loop = await asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._AGENT_EXECUTOR,
                self._run_with_agent,
                session_id,
                attempt,
            )

            # Create assistant message
            assistant_msg = Message(
                session_id=session_id,
                role="assistant",
                content=result.get("content", ""),
                linked_attempt_id=attempt_id,
            )
            self.store.append_message(session_id, assistant_msg)

            attempt.mark_completed(summary=result.get("content", "")[:500])
            self.store.save_attempt(session_id, attempt)

            self.event_bus.publish(SSEEvent(
                event_type="attempt.completed",
                data=attempt.to_dict(),
                session_id=session_id,
            ))

        except Exception as exc:
            attempt.mark_failed(error=str(exc))
            self.store.save_attempt(session_id, attempt)

            self.event_bus.publish(SSEEvent(
                event_type="attempt.failed",
                data=attempt.to_dict(),
                session_id=session_id,
            ))

    def _run_with_agent(self, session_id: str, attempt: Attempt) -> Dict:
        """Build and run the AgentLoop. This runs in a worker thread."""
        from ..agent.loop import AgentLoop
        from ..tools import build_registry

        # Build registry (discovers all tools)
        registry = build_registry(session_id=session_id)

        # Build LLM client (from config)
        llm = self._build_llm()

        # Build event callback that publishes to EventBus
        def event_callback(event_type: str, data: dict):
            self.event_bus.publish(SSEEvent(
                event_type=event_type,
                data=data,
                session_id=session_id,
            ))

        # Create and run agent loop
        agent_loop = AgentLoop(
            registry=registry,
            llm=llm,
            event_callback=event_callback,
            max_iterations=50,
        )
        self._active_loops[session_id] = agent_loop

        try:
            messages = self.store.get_messages(session_id, limit=50)
            history = [
                {"role": m.role, "content": m.content}
                for m in messages[:-1]  # Exclude the just-added user message
            ]
            result = agent_loop.run(
                messages=history,
                session_id=session_id,
            )
            return result
        finally:
            self._active_loops.pop(session_id, None)

    def cancel_current(self, session_id: str) -> bool:
        """Cancel the active agent loop for a session."""
        loop = self._active_loops.get(session_id)
        if loop:
            loop.cancel()
            return True
        return False
```

### B.5 — Session Store Implementation

**File**: `vinu-agent/vinu_agent/session/store.py`

```python
import json
import os
import shutil
from pathlib import Path
from typing import List, Optional

from .models import Attempt, Message, Session


class SessionStore:
    """
    File-based session persistence.
    
    Disk layout:
      sessions/
        {session_id}/
          session.json
          messages.jsonl
          attempts/
            {attempt_id}/
              attempt.json
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, session: Session) -> Session:
        session_dir = self.base_dir / session.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "attempts").mkdir(exist_ok=True)
        self._write_json(session_dir / "session.json", session.to_dict())
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        path = self.base_dir / session_id / "session.json"
        if not path.exists():
            return None
        return Session.from_dict(self._read_json(path))

    def list_sessions(self, limit: int = 50) -> List[Session]:
        sessions = []
        for d in self.base_dir.iterdir():
            if not d.is_dir():
                continue
            session_file = d / "session.json"
            if session_file.exists():
                sessions.append(Session.from_dict(self._read_json(session_file)))
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        session_dir = self.base_dir / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
            return True
        return False

    def append_message(self, session_id: str, message: Message) -> None:
        jsonl_path = self.base_dir / session_id / "messages.jsonl"
        with open(jsonl_path, "a") as f:
            f.write(json.dumps(message.to_dict(), default=str) + "\n")
            os.fsync(f.fileno())

    def get_messages(self, session_id: str, limit: int = 100) -> List[Message]:
        jsonl_path = self.base_dir / session_id / "messages.jsonl"
        if not jsonl_path.exists():
            return []
        messages = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(Message.from_dict(json.loads(line)))
        return messages[-limit:]

    def save_attempt(self, session_id: str, attempt: Attempt) -> None:
        attempt_dir = (
            self.base_dir / session_id / "attempts" / attempt.attempt_id
        )
        attempt_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(attempt_dir / "attempt.json", attempt.to_dict())

    def get_attempt(self, session_id: str, attempt_id: str) -> Attempt:
        path = (
            self.base_dir / session_id / "attempts" / attempt_id / "attempt.json"
        )
        return Attempt.from_dict(self._read_json(path))

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        os.replace(str(tmp), str(path))

    @staticmethod
    def _read_json(path: Path) -> dict:
        return json.loads(path.read_text())
```

---

## 5. Phase C — Skills System

**Goal**: Progressive disclosure of research methodology knowledge. System prompt gets one-line summaries; full docs load on demand.

### C.1 — Skills Loader

**File**: `vinu-agent/vinu_agent/agent/skills.py`

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Skill:
    name: str
    description: str = ""
    category: str = "other"
    body: str = ""
    dir_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def load_support_file(self, filename: str) -> Optional[str]:
        """Load a supporting file from the skill directory."""
        if not self.dir_path:
            return None
        path = self.dir_path / filename
        if path.exists():
            return path.read_text()
        return None


class SkillsLoader:
    """
    Progressive disclosure skill loader.
    
    - System prompt gets one-line summaries (cheap)
    - Full docs load on demand via get_content() (expensive)
    - User skills override bundled skills of the same name
    """

    # Category display order
    CATEGORY_ORDER = [
        "data-source", "strategy", "analysis", "asset-class",
        "crypto", "flow", "tool", "other",
    ]

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        user_skills_dir: Optional[Path] = None,
    ) -> None:
        self._skills: Dict[str, Skill] = {}
        
        # Load bundled skills first
        if skills_dir and skills_dir.exists():
            self._load_from_dir(skills_dir)
        
        # User skills override bundled
        if user_skills_dir and user_skills_dir.exists():
            self._load_from_dir(user_skills_dir)

    def _load_from_dir(self, directory: Path) -> None:
        """Load all skills from a directory. Each subdirectory must have SKILL.md."""
        for skill_dir in directory.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            
            content = skill_md.read_text()
            metadata, body = parse_frontmatter(content)
            
            skill = Skill(
                name=skill_dir.name,
                description=metadata.get("description", ""),
                category=metadata.get("category", "other"),
                body=body,
                dir_path=skill_dir,
                metadata=metadata,
            )
            self._skills[skill.name] = skill

    def get_descriptions(self) -> str:
        """
        One-line summaries grouped by category for system prompt injection.
        This is CHEAP — no full docs loaded.
        """
        by_category: Dict[str, List[str]] = {}
        for skill in self._skills.values():
            by_category.setdefault(skill.category, []).append(
                f"- {skill.name}: {skill.description}"
            )
        
        lines = []
        for cat in self.CATEGORY_ORDER:
            if cat in by_category:
                lines.append(f"\n**{cat.upper()}:**")
                lines.extend(by_category[cat])
        
        # Categories not in CATEGORY_ORDER
        for cat, skills in by_category.items():
            if cat not in self.CATEGORY_ORDER:
                lines.append(f"\n**{cat.upper()}:**")
                lines.extend(skills)
        
        return "\n".join(lines)

    def get_content(self, name: str) -> Optional[str]:
        """Get full skill content. Called by load_skill tool at runtime."""
        skill = self._skills.get(name)
        if not skill:
            # Try disk lookup for mid-session created skills
            return None
        return f'<skill name="{name}">\n{skill.body}\n</skill>'
```

### C.2 — Frontmatter Parser

**File**: `vinu-agent/vinu_agent/agent/frontmatter.py`

```python
import re
from typing import Any, Dict, Tuple


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse YAML-like frontmatter from SKILL.md files.
    
    Input:
        ---
        name: strategy-generate
        description: Create and backtest trading strategies
        category: strategy
        ---
        Full skill body content here...
    
    Returns:
        ({name: "strategy-generate", description: "...", category: "strategy"},
         "Full skill body content here...")
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    
    raw_metadata = match.group(1)
    body = match.group(2).strip()
    
    metadata = {}
    for line in raw_metadata.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        
        # Parse lists: [a, b, c]
        if value.startswith("[") and value.endswith("]"):
            value = [
                v.strip().strip('"').strip("'")
                for v in value[1:-1].split(",")
            ]
        # Parse booleans
        elif value.lower() in ("true", "false"):
            value = value.lower() == "true"
        # Strip quotes
        elif (value.startswith('"') and value.endswith('"')) or \
             (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        
        metadata[key] = value
    
    return metadata, body
```

---

## 6. Phase D — Swarm Orchestration

**Goal**: Multi-agent teams with DAG-based scheduling. Each worker runs its own mini agent loop.

### D.1 — Swarm Models

**File**: `vinu-agent/vinu_agent/swarm/models.py`

```python
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class TaskStatus(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    TOKEN_LIMIT = "token_limit"
    INCOMPLETE = "incomplete"


class SwarmAgentSpec(BaseModel):
    """Definition of a single agent in the swarm."""
    id: str
    role: str
    system_prompt: str
    tools: List[str] = []        # Whitelist of allowed tool names
    skills: List[str] = []       # Allowed skill names
    max_iterations: int = 25
    timeout_seconds: int = 300
    model_name: Optional[str] = None
    max_retries: int = 2


class SwarmTask(BaseModel):
    """A single task in the DAG."""
    id: str
    agent_id: str
    prompt_template: str           # Supports {var} placeholders
    depends_on: List[str] = []     # Upstream task IDs
    blocked_by: List[str] = []     # Shrinks at runtime as deps complete
    input_from: Dict[str, str] = {}  # Maps context_key -> source_task_id
    status: TaskStatus = TaskStatus.PENDING
    summary: Optional[str] = None
    artifacts: List[str] = []
    error: Optional[str] = None
    worker_iterations: int = 0


class SwarmRun(BaseModel):
    """A complete swarm execution."""
    id: str
    preset_name: str
    status: RunStatus
    user_vars: Dict[str, str]
    agents: List[SwarmAgentSpec]
    tasks: List[SwarmTask]
    final_report: Optional[str] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    provider: Optional[str] = None
    model: Optional[str] = None


class WorkerResult(BaseModel):
    """Result from a single worker execution."""
    status: WorkerStatus
    summary: str
    artifact_paths: List[str] = []
    iterations: int = 0
    error: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
```

### D.2 — DAG Task Store

**File**: `vinu-agent/vinu_agent/swarm/task_store.py`

```python
from typing import Dict, List, Set
from .models import SwarmTask, TaskStatus


def validate_dag(tasks: List[SwarmTask]) -> None:
    """Validate that the task graph is a DAG (no cycles)."""
    task_ids = {t.id for t in tasks}
    for task in tasks:
        for dep in task.depends_on:
            if dep not in task_ids:
                raise ValueError(
                    f"Task '{task.id}' depends on unknown task '{dep}'"
                )
    # Cycle detection via topological sort
    topological_layers(tasks)


def topological_layers(tasks: List[SwarmTask]) -> List[List[SwarmTask]]:
    """
    Sort tasks into layers for parallel execution.
    
    Layer 0: tasks with no dependencies
    Layer 1: tasks whose dependencies are all in layer 0
    Layer N: tasks whose dependencies are all in layers < N
    
    Within each layer, tasks can run in parallel.
    """
    task_map = {t.id: t for t in tasks}
    completed: Set[str] = set()
    layers: List[List[SwarmTask]] = []
    
    remaining = list(tasks)
    while remaining:
        # Find tasks whose deps are all completed
        ready = [
            t for t in remaining
            if all(dep in completed for dep in t.depends_on)
        ]
        if not ready:
            raise ValueError(
                "Circular dependency detected in task graph"
            )
        layers.append(ready)
        for t in ready:
            completed.add(t.id)
            remaining.remove(t)
    
    return layers


def resolve_dependencies(
    task: SwarmTask, completed_tasks: Dict[str, SwarmTask]
) -> Dict[str, str]:
    """
    Resolve input_from references for a task.
    Returns a dict of context_key -> upstream summary.
    """
    context = {}
    for context_key, source_task_id in task.input_from.items():
        source = completed_tasks.get(source_task_id)
        if source and source.summary:
            context[context_key] = source.summary
    return context
```

### D.3 — Swarm Runtime

**File**: `vinu-agent/vinu_agent/swarm/runtime.py`

```python
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, Optional

from .models import (
    RunStatus, SwarmAgentSpec, SwarmRun, SwarmTask, TaskStatus, WorkerResult,
)
from .task_store import resolve_dependencies, topological_layers, validate_dag


class SwarmRuntime:
    """
    DAG-based multi-agent orchestration.
    
    1. Parse preset YAML into SwarmRun
    2. Validate DAG
    3. Compute topological layers
    4. For each layer: submit all tasks in parallel
    5. Collect results, update downstream dependencies
    6. Repeat until all tasks complete
    """

    def __init__(
        self,
        max_workers: int = 4,
        agent_config: Optional[dict] = None,
    ) -> None:
        self.max_workers = max_workers
        self.agent_config = agent_config
        self._cancel_events: Dict[str, threading.Event] = {}
        self._live_callbacks: Dict[str, Callable] = {}

    def start_run(
        self,
        preset_name: str,
        user_vars: Dict[str, str],
        run: SwarmRun,
        live_callback: Optional[Callable] = None,
    ) -> SwarmRun:
        """Start a swarm run in a background thread."""
        validate_dag(run.tasks)
        
        cancel_event = threading.Event()
        self._cancel_events[run.id] = cancel_event
        if live_callback:
            self._live_callbacks[run.id] = live_callback
        
        thread = threading.Thread(
            target=self._execute_run,
            args=(run, cancel_event),
            daemon=True,
        )
        thread.start()
        return run

    def cancel_run(self, run_id: str) -> bool:
        event = self._cancel_events.get(run_id)
        if event:
            event.set()
            return True
        return False

    def _execute_run(
        self, run: SwarmRun, cancel_event: threading.Event
    ) -> None:
        """Core orchestration loop. Runs in a daemon thread."""
        run.status = RunStatus.RUNNING
        layers = topological_layers(run.tasks)
        completed_tasks: Dict[str, SwarmTask] = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for layer_idx, layer in enumerate(layers):
                if cancel_event.is_set():
                    run.status = RunStatus.CANCELLED
                    return
                
                # Submit all tasks in this layer
                futures = {}
                for task in layer:
                    # Check if blocked by failed upstream
                    blocked = any(
                        dep in completed_tasks
                        and completed_tasks[dep].status != TaskStatus.COMPLETED
                        for dep in task.depends_on
                    )
                    if blocked:
                        task.status = TaskStatus.BLOCKED
                        continue
                    
                    task.status = TaskStatus.IN_PROGRESS
                    upstream = resolve_dependencies(task, completed_tasks)
                    
                    agent_spec = next(
                        (a for a in run.agents if a.id == task.agent_id),
                        None,
                    )
                    if not agent_spec:
                        task.status = TaskStatus.FAILED
                        task.error = f"Agent '{task.agent_id}' not found"
                        continue
                    
                    future = executor.submit(
                        self._run_worker_with_retries,
                        agent_spec,
                        task,
                        upstream,
                        run.user_vars,
                    )
                    futures[future] = task
                
                # Collect results
                for future in as_completed(futures):
                    task = futures[future]
                    try:
                        result = future.result()
                        task.status = TaskStatus.COMPLETED
                        task.summary = result.summary
                        task.worker_iterations = result.iterations
                        task.artifacts = result.artifact_paths
                    except Exception as exc:
                        task.status = TaskStatus.FAILED
                        task.error = str(exc)
                    
                    completed_tasks[task.id] = task
        
        # Finalize
        failed = [t for t in run.tasks if t.status == TaskStatus.FAILED]
        if failed:
            run.status = RunStatus.FAILED
        else:
            run.status = RunStatus.COMPLETED
            # Set final report from last layer's aggregation task
            last_layer_tasks = layers[-1]
            if last_layer_tasks:
                run.final_report = last_layer_tasks[-1].summary

    def _run_worker_with_retries(
        self,
        agent_spec: SwarmAgentSpec,
        task: SwarmTask,
        upstream: Dict[str, str],
        user_vars: Dict[str, str],
    ) -> WorkerResult:
        """Run a worker with retry logic."""
        from .worker import run_worker
        
        last_error = None
        for attempt in range(agent_spec.max_retries + 1):
            try:
                result = run_worker(
                    agent_spec=agent_spec,
                    task=task,
                    upstream_summaries=upstream,
                    user_vars=user_vars,
                )
                if result.status.value == "completed":
                    return result
                last_error = result.error
            except Exception as exc:
                last_error = str(exc)
        
        return WorkerResult(
            status="failed",
            summary=f"Failed after {agent_spec.max_retries + 1} attempts",
            error=last_error,
        )
```

### D.4 — Swarm Worker (Mini ReAct Loop)

**File**: `vinu-agent/vinu_agent/swarm/worker.py`

Each worker runs a simplified version of the main agent loop:
- Only microcompact layer (no full 5-layer compression)
- Filtered tool whitelist (only tools the agent is allowed to use)
- Filtered skill list
- Hard limits: 20 tool-call max, timeout, token limit
- Wrap-up nudge at 80% of max iterations

### D.5 — Swarm Presets (YAML)

**File**: `vinu-agent/vinu_agent/swarm/presets/investment_committee.yaml`

```yaml
name: investment_committee
title: "Investment Committee"
description: "Long-short debate → risk review → PM final call"

agents:
  - id: bull_advocate
    role: Bull-side Researcher
    system_prompt: |
      You are the bull-side researcher for an investment committee.
      Your job: build the strongest possible case for buying {target}.
      Search for positive catalysts, growth drivers, and margin of safety.
      Cite specific numbers. Acknowledge risks but explain why they're priced in.
      Your audience is a skeptical risk officer who will challenge every claim.
    tools: [run_backtest, get_features, get_stock_price, web_search, load_skill]
    skills: [technical-basic, fundamental-filter, research-discipline]
    max_iterations: 25
    timeout_seconds: 600

  - id: bear_advocate
    role: Bear-side Researcher
    system_prompt: |
      You are the bear-side researcher for an investment committee.
      Your job: build the strongest possible case for NOT buying {target}.
      Search for risks, competitive threats, and valuation concerns.
      Cite specific numbers. The bull advocate will counter — make your case airtight.
    tools: [run_backtest, get_features, get_stock_price, web_search, load_skill]
    skills: [technical-basic, fundamental-filter, research-discipline]
    max_iterations: 25
    timeout_seconds: 600

  - id: risk_officer
    role: Risk Officer
    system_prompt: |
      You are the risk officer reviewing bull and bear arguments for {target}.
      Read both reports. Identify: (1) which claims lack evidence,
      (2) which risks are underweighted, (3) what the base case misses.
      Produce a risk-adjusted recommendation with position sizing.
      Be specific: "reduce by X%" not "be cautious."
    tools: [run_backtest, get_features, get_correlation, load_skill]
    skills: [risk-analysis, execution-model]
    max_iterations: 20
    timeout_seconds: 400

tasks:
  - id: task-bull
    agent_id: bull_advocate
    prompt_template: "Research the bull case for {target} in {market}. Cover: technicals, fundamentals, catalysts, and valuation."
    depends_on: []

  - id: task-bear
    agent_id: bear_advocate
    prompt_template: "Research the bear case for {target} in {market}. Cover: technicals, fundamentals, risks, and valuation concerns."
    depends_on: []

  - id: task-risk
    agent_id: risk_officer
    prompt_template: "Review bull and bear reports. Produce risk-adjusted recommendation with position sizing."
    depends_on: [task-bull, task-bear]
    input_from:
      bull_report: task-bull
      bear_report: task-bear

variables:
  - name: target
    description: "Security to analyze (e.g., AAPL, 600519.SH, BTC-USDT)"
    required: true
  - name: market
    description: "Market context (e.g., us_equity, a_share, crypto)"
    required: true
```

---

## 7. Phase E — IM Channels

**Goal**: Connect vinu-agent to Telegram/Discord so users can interact via chat.

### E.1 — BaseChannel ABC

**File**: `vinu-agent/vinu_agent/channels/base.py`

```python
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseChannel(ABC):
    """Base class for all IM channel adapters."""
    
    name: str = "base"
    display_name: str = "Base"
    send_progress: bool = True
    send_tool_hints: bool = False
    show_reasoning: bool = True

    def __init__(self, config: Any, bus: Any) -> None:
        self.config = config
        self.bus = bus

    @abstractmethod
    async def start(self) -> None:
        """Start the channel (connect to platform API)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel gracefully."""
        ...

    @abstractmethod
    async def send(self, msg: Any) -> None:
        """Send an outbound message to the platform."""
        ...

    async def send_delta(self, chat_id: str, delta: str, metadata: dict) -> None:
        """Streaming text delta (override if platform supports streaming)."""
        pass

    async def login(self, force: bool = False) -> bool:
        """Platform-specific login (e.g., QR code for Telegram)."""
        return True

    def is_allowed(self, sender_id: str) -> bool:
        """Check if sender is authorized. Override for permission logic."""
        return True
```

### E.2 — Telegram Adapter (First IM)

**File**: `vinu-agent/vinu_agent/channels/telegram.py`

```python
import httpx
from .base import BaseChannel


class TelegramChannel(BaseChannel):
    name = "telegram"
    display_name = "Telegram"

    def __init__(self, config: dict, bus: Any) -> None:
        super().__init__(config, bus)
        self.bot_token = config.get("bot_token", "")
        self.allowed_users = config.get("allowed_users", [])
        self._polling = False

    @classmethod
    def check_available(cls) -> bool:
        return True  # Uses httpx, always available

    async def start(self) -> None:
        """Start long-polling for messages."""
        self._polling = True
        offset = 0
        async with httpx.AsyncClient() as client:
            while self._polling:
                resp = await client.get(
                    f"https://api.telegram.org/bot{self.bot_token}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                    timeout=35,
                )
                for update in resp.json().get("result", []):
                    offset = update["update_id"] + 1
                    await self._handle_update(update)

    async def stop(self) -> None:
        self._polling = False

    async def send(self, msg: Any) -> None:
        """Send message via Telegram Bot API."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": msg.chat_id,
                    "text": msg.content,
                    "parse_mode": "Markdown",
                },
            )

    async def send_delta(self, chat_id: str, delta: str, metadata: dict) -> None:
        """Edit previous message for streaming effect."""
        # Implementation: use editMessageText for streaming
        pass

    async def _handle_update(self, update: dict) -> None:
        """Route incoming message to the session service."""
        message = update.get("message", {})
        sender_id = str(message.get("from", {}).get("id", ""))
        chat_id = str(message.get("chat", {}).get("id", ""))
        content = message.get("text", "")
        
        if not self.is_allowed(sender_id):
            await self._send_reply(chat_id, "Unauthorized. Contact admin.")
            return
        
        # Publish to message bus for session service
        from ..session.events import SSEEvent
        self.bus.publish(SSEEvent(
            event_type="channel.message",
            data={
                "channel": "telegram",
                "sender_id": sender_id,
                "chat_id": chat_id,
                "content": content,
            },
        ))

    def is_allowed(self, sender_id: str) -> bool:
        if not self.allowed_users:
            return True
        return sender_id in self.allowed_users
```

### E.3 — Channel Manager

**File**: `vinu-agent/vinu_agent/channels/manager.py`

```python
import asyncio
from typing import Dict, Optional
from .base import BaseChannel
from .registry import discover_enabled


class ChannelManager:
    """
    Manages all enabled IM channels.
    
    - Discovers and instantiates channels from config
    - Dispatches outbound messages from EventBus to channels
    - Handles streaming coalescing and retry
    """

    def __init__(
        self,
        config: dict,
        bus: Any,
        session_service: Any = None,
    ) -> None:
        self.config = config
        self.bus = bus
        self.session_service = session_service
        self._channels: Dict[str, BaseChannel] = {}
        self._running = False

    async def start_all(self) -> None:
        """Discover and start all enabled channels."""
        enabled = discover_enabled(self.config)
        for name, channel_class in enabled.items():
            channel_config = self.config.get("channels", {}).get(name, {})
            channel = channel_class(config=channel_config, bus=self.bus)
            self._channels[name] = channel
            await channel.start()

        # Start outbound dispatch loop
        self._running = True
        asyncio.create_task(self._dispatch_outbound())

    async def stop_all(self) -> None:
        """Stop all channels gracefully."""
        self._running = False
        for channel in self._channels.values():
            await channel.stop()

    async def _dispatch_outbound(self) -> None:
        """Consume outbound events from EventBus and route to channels."""
        async for event in self.bus.consume_outbound():
            if not self._running:
                break
            
            # Route to appropriate channel based on event metadata
            channel_name = event.data.get("channel")
            if channel_name and channel_name in self._channels:
                channel = self._channels[channel_name]
                await self._send_with_retry(channel, event)
```

---

## 8. Phase F — Persistent Memory + Config

### F.1 — Persistent Memory

**File**: `vinu-agent/vinu_agent/memory/persistent.py`

Cross-session memory stored as Markdown files with YAML frontmatter:

```
~/.vinu/memory/
  MEMORY.md              # Index (frozen at session start for prompt cache)
  user_prefs.md          # Individual entries
  aapl_research.md
  momentum_decay_findings.md
  ...
```

Key operations:
- `add(name, content, memory_type, description)` — Create new memory entry
- `find_relevant(query, max_results)` — Keyword-based relevance search
- `snapshot` — Frozen text for system prompt injection

### F.2 — Pydantic Config

**File**: `vinu-lib/vinu_lib/config_v2.py`

Replace manual `@dataclass` + `os.environ.get()` with Pydantic:

```python
from pydantic import BaseModel, ConfigDict, model_validator
import os


class _EnvBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _load_from_env(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return data
        result = {}
        for field_name, field_info in cls.model_fields.items():
            env_key = field_info.alias or field_name.upper()
            value = os.environ.get(env_key)
            if value is not None:
                result[field_name] = value
        return result


class LLMConfig(_EnvBase):
    provider: str = "openai"
    model_name: str = "gpt-4"
    api_key: str = ""
    base_url: str = ""
    timeout: int = 120


class SwarmConfig(_EnvBase):
    max_workers: int = 4
    default_timeout: int = 300
    max_iterations: int = 25


class AgentConfig(_EnvBase):
    llm: LLMConfig = LLMConfig()
    swarm: SwarmConfig = SwarmConfig()
    max_iterations: int = 50
    skills_dir: str = ""
    user_skills_dir: str = ""
    sessions_dir: str = ""
    memory_dir: str = ""


def get_agent_config() -> AgentConfig:
    return AgentConfig()
```

---

## 9. Tool Mapping — All 7 Services as Agent Tools

Each vinu service becomes a `BaseTool` the agent can call. Here's the exact mapping:

| Tool Name | Service Called | Endpoint | Parameters | Description |
|-----------|---------------|----------|------------|-------------|
| `run_backtest` | vinu-simulator | `POST /simulate/custom` | `strategy_code`, `symbol`, `start_date`, `end_date`, `interval`, `initial_capital` | Run a backtest for a user-defined strategy |
| `get_features` | vinu-features | `POST /features/submit` | `symbol`, `indicators`, `start_date`, `end_date` | Compute technical indicators for a symbol |
| `get_stock_price` | vinu-stock-price | `GET /candles/{symbol}` | `symbol`, `start_date`, `end_date`, `interval` | Fetch historical OHLCV data |
| `get_news` | vinu-news | `GET /news/query` | `symbol`, `start_date`, `end_date`, `limit` | Fetch news articles for a symbol |
| `get_correlation` | vinu-correlation | `POST /correlation/compute` | `symbol`, `start_date`, `end_date` | Compute news-price correlation analysis |
| `run_strategy` | vinu-strategy | `POST /strategy/evaluate` | `strategy_name`, `universe`, `date` | Evaluate a YAML-defined strategy |
| `run_research` | vinu-research | `POST /research/run` | `idea`, `symbol`, `from_date`, `to_date`, `interval` | Run the full research loop |
| `load_skill` | (local) | — | `name` | Load full skill documentation |
| `remember` | (local) | — | `name`, `content`, `memory_type` | Save to persistent memory |
| `search_sessions` | (local) | — | `query` | Search across all past sessions |
| `web_search` | (external) | — | `query` | Search the web for information |

### Example Tool Implementation

**File**: `vinu-agent/vinu_agent/tools/backtest_tool.py`

```python
import json
from ..agent.tools import BaseTool


class BacktestTool(BaseTool):
    name = "run_backtest"
    description = (
        "Run a backtest for a trading strategy. The strategy_code must define "
        "a class Strategy with a generate_weights(self, data) -> pd.Series method. "
        "Returns metrics (sharpe, max_drawdown, total_return) and trade count."
    )
    parameters = {
        "strategy_code": {
            "type": "string",
            "description": "Python code defining a Strategy class with generate_weights method",
        },
        "symbol": {
            "type": "string",
            "description": "Stock symbol (e.g., AAPL, 600519.SH, BTC-USDT)",
        },
        "start_date": {
            "type": "string",
            "description": "Start date in YYYY-MM-DD format",
        },
        "end_date": {
            "type": "string",
            "description": "End date in YYYY-MM-DD format",
        },
        "interval": {
            "type": "string",
            "description": "Bar interval: 1m, 5m, 15m, 1h, 1D (default: 1D)",
            "default": "1D",
        },
        "initial_capital": {
            "type": "number",
            "description": "Starting capital in USD (default: 100000)",
            "default": 100000,
        },
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        
        simulator_url = self._services_config.get(
            "vinu_simulator", "http://localhost:8085"
        )
        
        payload = {
            "strategy_code": kwargs["strategy_code"],
            "symbol": kwargs["symbol"],
            "start_date": kwargs["start_date"],
            "end_date": kwargs["end_date"],
            "interval": kwargs.get("interval", "1D"),
            "initial_capital": kwargs.get("initial_capital", 100000),
        }
        
        resp = httpx.post(
            f"{simulator_url}/simulate/custom",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.text
```

---

## 10. Skills Library — 15 Core Skills

These are the most valuable skills to import from Vibe-Trading, organized by priority:

### Tier 1 — Critical (implement first)

| # | Skill Name | Category | What It Does | Why It Matters |
|---|-----------|----------|-------------|----------------|
| 1 | `research-discipline` | analysis | 5-bias self-check (leader, English, narrative, confirmation, recency) | Highest-ROI improvement — zero code, just prompt injection |
| 2 | `strategy-generate` | strategy | 7-step strategy development workflow with SignalEngine contract | Core workflow for any strategy development |
| 3 | `backtest-diagnose` | tool | Error taxonomy + hard-gate checklist for failed backtests | Prevents cascading errors in the research loop |
| 4 | `execution-model` | strategy | Slippage models (fixed/linear/square-root), VWAP/TWAP, cost tables | Makes backtest results realistic |
| 5 | `factor-research` | analysis | IC/IR evaluation, quantile backtesting, factor combination | Rigorous methodology for factor evaluation |

### Tier 2 — High Value

| # | Skill Name | Category | What It Does | Why It Matters |
|---|-----------|----------|-------------|----------------|
| 6 | `risk-analysis` | analysis | VaR/CVaR, Monte Carlo, stress testing, tail-risk (EVT/GPD) | Comprehensive risk measurement |
| 7 | `report-generate` | tool | Professional report templates, rating system, terminology | Transforms analysis into publication-grade output |
| 8 | `shadow-account` | analysis | Trade journal extraction → shadow backtest → attribution | Unique "mirror" for behavioral improvement |
| 9 | `thesis-tracker` | strategy | Buy-side discipline: thesis → assumptions → red lines → health score | Bridges research → ongoing monitoring |
| 10 | `technical-basic` | strategy | EMA/ADX + BB/RSI + OBV/volume three-dimensional voting | Clean, well-tested indicator implementation |

### Tier 3 — Enhancement

| # | Skill Name | Category | What It Does | Why It Matters |
|---|-----------|----------|-------------|----------------|
| 11 | `alpha-zoo` | research | Browse 450+ prebuilt alphas, bench IC/IR | Massive factor library |
| 12 | `multi-factor` | strategy | Cross-sectional ranking with z-score, IC-weighted | Portfolio construction from factors |
| 13 | `sentiment-analysis` | analysis | Fear/Greed, PCR, margin, northbound, social media composite | Quantified sentiment framework |
| 14 | `quant-statistics` | analysis | ADF/cointegration, GARCH, regression diagnostics | Statistical rigor |
| 15 | `valuation-model` | analysis | DCF, PE-Band, PB-ROE, valuation trap detection | Fundamental valuation framework |

---

## 11. Swarm Presets — 4 Multi-Agent Configs

| Preset | Agents | DAG Pattern | Use Case |
|--------|--------|-------------|----------|
| `investment_committee` | bull_advocate, bear_advocate, risk_officer | 2 parallel → 1 merge | Full bull/bear debate with risk review |
| `quant_strategy_desk` | screener, factor_miner, backtester, risk_auditor | 2 parallel → 1 → 1 | Factor screening → backtest → audit |
| `risk_committee` | drawdown_analyst, tail_risk_analyst, regime_analyst, aggregator | 3 parallel → 1 merge | Multi-dimensional risk assessment |
| `research_team` | tech_analyst, fundamental_analyst, sentiment_analyst, synthesizer | 3 parallel → 1 merge | Comprehensive research synthesis |

---

## 12. API Endpoints

### Session Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/sessions` | Create new session |
| `GET` | `/sessions` | List sessions (limit, offset) |
| `GET` | `/sessions/{id}` | Get session details |
| `DELETE` | `/sessions/{id}` | Delete session |
| `POST` | `/sessions/{id}/messages` | Send message (triggers agent) |
| `POST` | `/sessions/{id}/cancel` | Cancel active agent loop |
| `GET` | `/sessions/{id}/messages` | List messages |
| `GET` | `/sessions/{id}/events` | SSE stream (last_event_id recovery) |

### Swarm Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/swarm/runs` | Start a swarm run |
| `GET` | `/swarm/runs/{id}` | Get run status |
| `POST` | `/swarm/runs/{id}/cancel` | Cancel a run |
| `GET` | `/swarm/presets` | List available presets |

### Channel Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/channels/status` | Get all channel statuses |
| `POST` | `/channels/start` | Start a channel |
| `POST` | `/channels/stop` | Stop a channel |

### System Routes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check (all services) |
| `GET` | `/status` | Agent status (active sessions, loops) |

---

## 13. File Tree

```
vinu-agent/
  vinu_agent/
    __init__.py
    config.py
    service.py
    cli.py
    server/
      __init__.py
      app.py
      routes_sessions.py
      routes_swarm.py
      routes_channels.py
      routes_system.py
      schemas.py
    agent/
      __init__.py
      loop.py              # ~1600 lines (the ReAct core)
      tools.py             # BaseTool + ToolRegistry (~100 lines)
      context.py           # ContextBuilder (~350 lines)
      skills.py            # SkillsLoader (~200 lines)
      frontmatter.py       # parse_frontmatter() (~50 lines)
    session/
      __init__.py
      service.py           # SessionService (~350 lines)
      store.py             # SessionStore (~250 lines)
      events.py            # EventBus + SSEEvent (~250 lines)
      models.py            # Session, Message, Attempt (~200 lines)
      search.py            # FTS5 search (~200 lines)
    swarm/
      __init__.py
      runtime.py           # SwarmRuntime (~750 lines)
      worker.py            # run_worker() (~950 lines)
      models.py            # SwarmRun, SwarmTask, etc. (~220 lines)
      store.py             # SwarmStore (~100 lines)
      task_store.py        # DAG validation (~100 lines)
      presets/
        investment_committee.yaml
        quant_strategy_desk.yaml
        risk_committee.yaml
        research_team.yaml
    channels/
      __init__.py
      base.py              # BaseChannel ABC (~250 lines)
      registry.py          # Auto-discovery (~280 lines)
      manager.py           # ChannelManager (~480 lines)
      telegram.py          # Telegram adapter (~200 lines)
      discord.py           # Discord adapter (~200 lines)
    memory/
      __init__.py
      persistent.py        # PersistentMemory (~370 lines)
    tools/
      __init__.py          # Auto-discovery + build_registry (~360 lines)
      backtest_tool.py
      features_tool.py
      news_tool.py
      correlation_tool.py
      stock_price_tool.py
      strategy_tool.py
      research_tool.py
      web_search_tool.py
      load_skill_tool.py
      remember_tool.py
      session_search_tool.py
  skills/                  # 15 core skill directories
    research-discipline/
      SKILL.md
    strategy-generate/
      SKILL.md
    backtest-diagnose/
      SKILL.md
    execution-model/
      SKILL.md
    factor-research/
      SKILL.md
    risk-analysis/
      SKILL.md
    report-generate/
      SKILL.md
    shadow-account/
      SKILL.md
    thesis-tracker/
      SKILL.md
    technical-basic/
      SKILL.md
    alpha-zoo/
      SKILL.md
    multi-factor/
      SKILL.md
    sentiment-analysis/
      SKILL.md
    quant-statistics/
      SKILL.md
    valuation-model/
      SKILL.md
  tests/
    test_loop.py
    test_tools.py
    test_session.py
    test_swarm.py
    test_skills.py
  Dockerfile
  pyproject.toml
```

**Estimated total**: ~8,000–10,000 lines of new code across all files.

---

## 14. Key Design Decisions

### 1. Thread-based, not async

The agent loop uses **threads** (not asyncio) for LLM calls and tool execution. The FastAPI server bridges with `run_in_executor`. This matches Vibe-Trading's proven architecture and avoids the complexity of mixing async/sync.

**Why**: LLM calls are blocking (waiting for response). Threads are simpler than asyncio for blocking I/O. The SessionService handles the async→thread bridge.

### 2. 5-layer context management

Adopt Vibe-Trading's exact hierarchy because it's proven to work across millions of tokens of real research sessions. The key insight: **cheap layers first** (microcompact, context_collapse) before expensive LLM-based compression.

### 3. Skills as Markdown files

Each skill is a directory with `SKILL.md` (YAML frontmatter + body). This is the simplest possible format — no database, no code, just text. The system prompt gets one-line summaries; full docs load on demand. This keeps the context window lean.

### 4. DAG-based swarm

Topological layer scheduling with dependency-aware gating. Failed upstream blocks downstream. This is the standard DAG execution model — well-understood and proven.

### 5. Services as tools (not embedded)

The agent calls vinu services via HTTP (using `ResilientClient` from vinu-lib), not by importing their code directly. This maintains the microservices architecture and allows independent deployment.

### 6. JSONL for messages, JSON for metadata

Messages use JSONL (append-only, crash-safe with fsync). Sessions and attempts use JSON (read-modify-write). This matches Vibe-Trading's proven persistence model.

---

## 15. Migration Path

### How to Transition from CLI-only to Agent

**Step 1**: Build vinu-agent alongside existing services (no breaking changes)
**Step 2**: Test agent loop with all 7 services as tools
**Step 3**: Add session management + SSE streaming
**Step 4**: Add first IM channel (Telegram)
**Step 5**: Add swarm orchestration with 1 preset
**Step 6**: Migrate vinu-research CLI to use vinu-agent as backend
**Step 7**: Add remaining IM channels and swarm presets

### What Stays the Same

- All 7 existing services continue unchanged
- All existing CLI commands continue working
- Docker Compose adds one new service (vinu-agent on port 8086)
- Existing API contracts are not modified

### What Changes

- `vinu-research run` can optionally route through vinu-agent for autonomous execution
- New web UI can connect via SSE for real-time streaming
- Telegram/Discord bots become available as new interfaces
- Multi-agent research becomes possible via swarm presets

---

## Appendix: How to Use This Document

**For a future agent implementing this plan:**

1. Start with Phase A (Agent Core) — it's the foundation everything else depends on
2. Each phase is independent — you can implement B, C, D, E, F in any order after A
3. The tool mapping (Section 9) tells you exactly how each vinu service becomes an agent tool
4. The skills library (Section 10) tells you which Vibe-Trading skills to import
5. The swarm presets (Section 11) tell you the exact YAML structure for multi-agent configs
6. The API endpoints (Section 12) tell you what the FastAPI server exposes
7. The file tree (Section 13) tells you exactly what files to create

**For a human developer:**

- The estimated total is ~8,000–10,000 lines of new code
- Phase A is the hardest part (~3,000 lines for the agent loop + context builder)
- Phases B-F are more mechanical (~1,000–1,500 lines each)
- The 15 skills are just Markdown files — no code required
- The 4 swarm presets are YAML files — no code required
- Testing can be done against existing vinu services running locally
