"""Generic team runner: loads a team's TEAM.md + agents/*/AGENT.md and runs
its manager as an AgentLoop with a delegate_to_agent tool scoped to just
that team's own specialists.

Every tier (orchestrator, team manager, specialist) is the same underlying
primitive -- an AgentLoop configured with a role, a system prompt, a skill
subset, and a tool subset. What differs between tiers is config (these
markdown files), not code. See
New-talk-agents/01-orchestrator-and-teams-architecture.md for the full
design.
"""

from __future__ import annotations

import json
import os
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from vinu_infra.llm.identity import purpose_scope

from .frontmatter import parse_frontmatter
from .llm import wrap_with_logging
from .loop import AgentLoop
from .tools import BaseTool, ToolRegistry

LOG = logging.getLogger(__name__)

#: Reuses the existing swarm budget config (vinu_agent/config.py's
#: SwarmConfig.max_iterations) rather than inventing a second "how many
#: steps can a sub-agent take" number -- same concept, same default.
_DEFAULT_SPECIALIST_MAX_ITERATIONS = 25

# A standalone `VERDICT:` only. The backtest runner also writes `SELF-VERDICT: PASS` about its own sweep evidence, which
# contains the text "VERDICT: PASS": the old pattern read that as the team's final verdict, so a research run was
# stamped PASS before the risk critic had even been consulted.
_VERDICT_RE = re.compile(r"(?<![\w-])VERDICT:\s*\**\s*(PASS|STOP)", re.IGNORECASE)


def _extract_verdict(content: str) -> str:
    """Best-effort verdict extraction from a manager's final free-text
    answer (see teams/research/agents/risk_critic/prompt.md's required
    "VERDICT: PASS/STOP" line). Not every team's manager necessarily ends
    with this exact shape -- empty string just means "no verdict found",
    not an error."""
    matches = _VERDICT_RE.findall(content or "")
    return matches[-1].upper() if matches else ""        # the LAST one: the final answer, not an earlier quote


#: Teams whose manager must END with a `VERDICT: PASS|STOP` line (from the risk critic). A manager that stops after the
#: backtest with "now I need to send this to the risk_critic" has not decided anything.
TEAMS_REQUIRING_VERDICT = {"research"}
MAX_VERDICT_NUDGES = 2

#: A research run may not end in STOP before the idea generator has been asked for at least this many candidate
#: strategies (each is tested, optimised by its parameter sweep, risk-reviewed, and its failure reasons fed to the next
#: attempt). A PASS ends the run at once. Without this a manager gave up after ONE attempt, claiming it "reached the
#: maximum number of iterations" when it had used 2 of 25.
MIN_RESEARCH_ATTEMPTS = int(os.environ.get("VINU_RESEARCH_MIN_ATTEMPTS", "3"))

_ATTEMPTS_NUDGE = (
    "You stopped after only {n} of the {need} candidate strategies this run requires, so it is too early to give up. You "
    "have NOT run out of iterations (you have used very few of your {budget} turns; there is no other limit). Use what "
    "the failures taught you: delegate to `idea_generator` NOW with the specific failure reasons from the attempts so far "
    "and ask for a genuinely different candidate (a different idea or filter, not the same recipe with new numbers), then "
    "test it with `backtest_runner` and review it with `risk_critic`. Finish only with `VERDICT: PASS` or "
    "`VERDICT: STOP` after at least {need} attempts."
)

_VERDICT_NUDGE = (
    "You have not given a final verdict yet, so this run decided nothing. Do not stop here. If you have backtest "
    "evidence you trust, delegate to `risk_critic` NOW with the strategy description, the metrics and the full "
    "validation reasons; if the evidence is not trustworthy, delegate back to `idea_generator` with that feedback. "
    "Finish only with a line `VERDICT: PASS` or `VERDICT: STOP` (and the JSON block on PASS)."
)


def run_until_verdict(
    make_loop: Callable[[], Any], messages: list[dict], *, required: bool, max_nudges: int = MAX_VERDICT_NUDGES,
    attempts: Optional[Callable[[], int]] = None, min_attempts: int = 0, budget: int = 0,
) -> dict:
    """Run the manager loop; for a team that must reach a verdict, ask it to continue (up to `max_nudges` times) when it
    ends its turn without one. The nudge carries the manager's own last answer, so it resumes from where it stopped."""
    result = make_loop().run(messages=messages)
    if not required:
        return result
    for attempt in range(max_nudges):
        content = result.get("content", "")
        if result.get("status") != "completed":
            break
        verdict = _extract_verdict(content)
        made = attempts() if attempts is not None else min_attempts
        if verdict == "PASS" or (verdict == "STOP" and made >= min_attempts):
            break
        if verdict == "STOP":
            LOG.warning("manager gave up after %d of %d required attempts; nudging to continue (%d/%d)",
                        made, min_attempts, attempt + 1, max_nudges)
            nudge = _ATTEMPTS_NUDGE.format(n=made, need=min_attempts, budget=budget)
        else:
            LOG.warning("manager ended without a VERDICT line; nudging to continue (%d/%d)", attempt + 1, max_nudges)
            nudge = _VERDICT_NUDGE
        messages = messages + [{"role": "assistant", "content": content}, {"role": "user", "content": nudge}]
        result = make_loop().run(messages=messages)
    return result


def _apply_team_result_hook(
    team_name: str, content: str, *, strategy_store: Any, run_id: str,
    ticker_ledger_store: Any = None, services_config: Any = None,
) -> Optional[str]:
    """Team-specific hooks that turn a manager's completed final answer into
    a durable write elsewhere in the system (never an agent-callable tool --
    pillar 8). Each hook is best-effort/swallow-and-log internally (see
    broker/debrief.py's contract). Returns an artifact_id for traceability
    (team_runs.related_artifact_id) when the hook actually wrote something,
    else None. Was a single `if self.spec.name == "research"` special case;
    generalized once risk_gatekeeper needed the same shape."""
    if strategy_store is None:
        return None
    if team_name == "research":
        from .research_artifact_writer import write_artifact_from_research_pass
        return write_artifact_from_research_pass(
            content, strategy_store=strategy_store, source_run_id=run_id, services_config=services_config,
        )
    if team_name == "risk_gatekeeper":
        from .risk_gatekeeper_hook import apply_risk_gatekeeper_verdict
        return apply_risk_gatekeeper_verdict(
            content, strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
        )
    if team_name == "capital_allocator":
        from .capital_allocator_hook import apply_capital_allocator_decision
        return apply_capital_allocator_decision(
            content, strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
            services_config=services_config,
        )
    return None


def _tag_event_callback(callback: Optional[Callable], **tags: Any) -> Optional[Callable]:
    """Wraps a session's event_callback so every event a nested AgentLoop
    emits (manager or specialist) carries which team/agent/role it came
    from -- otherwise every nested loop's "llm.call"/"tools.executed"/etc.
    events would be indistinguishable from each other and from the
    orchestrator's own, once they all land on the same SSE stream."""
    if callback is None:
        return None

    def _wrapped(event_type: str, data: dict) -> None:
        callback(event_type, {**data, **tags})

    return _wrapped


@dataclass
class AgentSpec:
    """One specialist's definition, loaded from teams/<team>/agents/<name>/AGENT.md."""

    name: str
    role: str
    prompt: str
    depends_on: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


@dataclass
class TeamSpec:
    """A team's definition, loaded from teams/<team>/TEAM.md."""

    name: str
    manager_prompt: str
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    agents: dict[str, AgentSpec] = field(default_factory=dict)


def _load_prompt(agent_dir: Path, meta: dict[str, Any], default_file: str) -> str:
    prompt_file = meta.get("prompt_file", default_file)
    path = agent_dir / prompt_file
    if not path.exists():
        raise FileNotFoundError(f"prompt_file {prompt_file!r} not found under {agent_dir}")
    return path.read_text(encoding="utf-8")


def load_agent_spec(agent_dir: Path) -> AgentSpec:
    md_path = agent_dir / "AGENT.md"
    meta, _body = parse_frontmatter(md_path.read_text(encoding="utf-8"))
    return AgentSpec(
        name=meta.get("name", agent_dir.name),
        role=meta.get("role", "specialist"),
        prompt=_load_prompt(agent_dir, meta, "prompt.md"),
        depends_on=list(meta.get("depends_on", []) or []),
        tools=list(meta.get("tools", []) or []),
        skills=list(meta.get("skills", []) or []),
    )


def load_team_spec(team_dir: Path) -> TeamSpec:
    md_path = team_dir / "TEAM.md"
    if not md_path.exists():
        raise FileNotFoundError(f"No TEAM.md found under {team_dir}")
    meta, _body = parse_frontmatter(md_path.read_text(encoding="utf-8"))

    agents: dict[str, AgentSpec] = {}
    agents_dir = team_dir / "agents"
    if agents_dir.exists():
        for sub in sorted(agents_dir.iterdir()):
            if sub.is_dir() and (sub / "AGENT.md").exists():
                spec = load_agent_spec(sub)
                agents[spec.name] = spec

    return TeamSpec(
        name=meta.get("name", team_dir.name),
        manager_prompt=_load_prompt(team_dir, meta, "manager_prompt.md"),
        tools=list(meta.get("tools", []) or []),
        skills=list(meta.get("skills", []) or []),
        agents=agents,
    )


def _skills_block(skills_loader: Any, names: list[str]) -> str:
    if not skills_loader or not names:
        return ""
    parts = []
    for name in names:
        content = skills_loader.get_content(name)
        if content:
            parts.append(content)
        else:
            LOG.warning("team/agent requested unknown skill %r, skipping", name)
    return "\n\n".join(parts)


def _roster_block(agents: dict[str, AgentSpec]) -> str:
    """Describes each specialist's role and declared depends_on to the
    manager, so it sequences delegate_to_agent calls sensibly on its own --
    depends_on here is informational context for the LLM, not a hard-coded
    DAG executor (a manager may need a variable number of extra passes,
    e.g. another backtest before it's confident)."""
    lines = ["Specialists available to you via delegate_to_agent:"]
    for spec in agents.values():
        dep_note = f" (normally after: {', '.join(spec.depends_on)})" if spec.depends_on else ""
        lines.append(f"- {spec.name} ({spec.role}){dep_note}")
    return "\n".join(lines)


class DelegateToAgentTool(BaseTool):
    """Bound to one team's own roster at construction time -- a manager can
    only ever reach its own team's specialists, never another team's."""

    name = "delegate_to_agent"
    description = "Delegate a task to one of this team's specialist agents and get back its result."
    parameters = {
        "type": "object",
        "properties": {
            "agent_name": {"type": "string", "description": "Which specialist to delegate to"},
            "task": {"type": "string", "description": "The task/question for the specialist"},
        },
        "required": ["agent_name", "task"],
    }
    is_readonly = False
    repeatable = True

    def __init__(
        self,
        agents: dict[str, AgentSpec],
        *,
        full_registry: ToolRegistry,
        llm: Any,
        skills_loader: Any = None,
        team_name: str = "",
        event_callback: Optional[Callable] = None,
        run_store: Any = None,
        run_id: str = "",
        llm_call_store: Any = None,
        session_id: str = "",
    ) -> None:
        self._agents = agents
        # how many times each specialist was handed a task in this run (the research manager is held to a minimum number
        # of idea_generator attempts before it may give up)
        self.delegations: dict[str, int] = {}
        self._full_registry = full_registry
        self._llm = llm
        self._skills_loader = skills_loader
        self._team_name = team_name
        self._event_callback = event_callback
        self._run_store = run_store
        self._run_id = run_id
        self._llm_call_store = llm_call_store
        self._session_id = session_id
        roster = ", ".join(agents.keys()) or "(none configured)"
        self.description = (
            f"Delegate a task to one of this team's specialist agents and get back its "
            f"result. Available agents: {roster}."
        )

    def execute(self, **kwargs: Any) -> str:
        agent_name = kwargs.get("agent_name", "")
        task = kwargs.get("task", "")
        spec = self._agents.get(agent_name)
        if spec is None:
            return json.dumps({
                "status": "error",
                "error": f"Unknown agent {agent_name!r}. Available: {list(self._agents)}",
            })

        self.delegations[agent_name] = self.delegations.get(agent_name, 0) + 1
        db_task = None
        if self._run_store is not None and self._run_id:
            db_task = self._run_store.add_task(
                self._run_id, agent_name=agent_name, role=spec.role, depends_on=spec.depends_on,
            )
            self._run_store.mark_task_running(db_task.task_id)

        scoped_registry = self._full_registry.subset(spec.tools)
        skills_text = _skills_block(self._skills_loader, spec.skills)
        system_prompt = spec.prompt
        if skills_text:
            system_prompt = f"{system_prompt}\n\n## Reference knowledge\n{skills_text}"

        specialist_callback = _tag_event_callback(
            self._event_callback, team=self._team_name, agent=agent_name, role=spec.role,
        )
        specialist_llm = wrap_with_logging(
            self._llm, self._llm_call_store,
            service="vinu-agent", tier="specialist", team=self._team_name,
            agent=agent_name, role=spec.role, session_id=self._session_id,
        )
        sub_loop = AgentLoop(
            registry=scoped_registry,
            llm=specialist_llm,
            event_callback=specialist_callback,
            max_iterations=_DEFAULT_SPECIALIST_MAX_ITERATIONS,
        )
        result = sub_loop.run(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ])

        content = result.get("content", "")
        status = result.get("status", "completed")
        if db_task is not None:
            if status == "completed":
                self._run_store.mark_task_completed(db_task.task_id, result=content)
            else:
                self._run_store.mark_task_failed(db_task.task_id, error=content)

        # Only a bounded, structured result crosses back up -- never the
        # specialist's full trace/history. See the architecture doc's
        # "every sub-agent returns a small structured result" rule.
        return json.dumps({
            "status": status,
            "agent": agent_name,
            "content": content,
        })


# What each team's answers are for. The gateway turns the purpose into a queue priority, so a live trading decision
# is not stuck behind a summary. A team not listed here uses the agent's default purpose.
TEAM_PURPOSE: dict[str, str] = {
    "live_decision": "live_decision",
    "risk_gatekeeper": "risk_gate",
    "capital_allocator": "risk_gate",
    "research": "research",
    "screener": "summary",
    "thesis_intake": "planner",
}

class TeamManager:
    """Loads one team's TEAM.md + agents/*/AGENT.md and exposes a single
    run(task) entrypoint -- the manager's own AgentLoop, scoped to its
    declared tools plus a delegate_to_agent tool bound to just its own
    roster."""

    def __init__(
        self,
        team_dir: Path,
        *,
        full_registry: ToolRegistry,
        llm: Any,
        skills_loader: Any = None,
        max_iterations: int = _DEFAULT_SPECIALIST_MAX_ITERATIONS,
        event_callback: Optional[Callable] = None,
        run_store: Any = None,
        triggered_by_session_id: str = "",
        llm_call_store: Any = None,
        strategy_store: Any = None,
        ticker_summary_store: Any = None,
        ticker_ledger_store: Any = None,
        services_config: Any = None,
    ) -> None:
        self.spec = load_team_spec(team_dir)
        self._full_registry = full_registry
        self._llm = llm
        self._skills_loader = skills_loader
        self._max_iterations = max_iterations
        self._event_callback = event_callback
        self._run_store = run_store
        self._triggered_by_session_id = triggered_by_session_id
        self._llm_call_store = llm_call_store
        # Only ever read by the team-specific hooks in run() below -- None
        # is fine for every team that doesn't need it.
        self._strategy_store = strategy_store
        # Only read by the "screener" hook below -- writes durable
        # per-ticker summaries, a different shape than the artifact_id
        # hooks above (no single artifact_id, no team_runs traceability
        # link -- see storage/ticker_summaries.py).
        self._ticker_summary_store = ticker_summary_store
        # Only read by the "risk_gatekeeper" hook below -- best-effort
        # audit row for the PEND transition, see risk_gatekeeper_hook.py.
        self._ticker_ledger_store = ticker_ledger_store
        # Only read by the "capital_allocator" hook -- the rebalancer's
        # unwind requests need vinu-live's base URL to POST to, see
        # capital_allocator_hook.py.
        self._services_config = services_config

    def run(self, task: str, *, context: Optional[str] = None) -> dict:
        """Run the team; every LLM call it makes tells the gateway what it is for (see TEAM_PURPOSE)."""
        purpose = TEAM_PURPOSE.get(self.spec.name)
        if purpose is None:
            return self._run(task, context=context)
        with purpose_scope(purpose):
            return self._run(task, context=context)

    def _run(self, task: str, *, context: Optional[str] = None) -> dict:
        db_run = None
        if self._run_store is not None:
            db_run = self._run_store.create_run(
                self.spec.name, triggered_by_session_id=self._triggered_by_session_id,
            )
            self._run_store.mark_running(db_run.run_id)

        delegate_tool = DelegateToAgentTool(
            self.spec.agents,
            full_registry=self._full_registry,
            llm=self._llm,
            skills_loader=self._skills_loader,
            team_name=self.spec.name,
            event_callback=self._event_callback,
            run_store=self._run_store,
            run_id=db_run.run_id if db_run else "",
            llm_call_store=self._llm_call_store,
            session_id=self._triggered_by_session_id,
        )
        manager_registry = self._full_registry.subset(self.spec.tools)
        manager_registry.register(delegate_tool)

        skills_text = _skills_block(self._skills_loader, self.spec.skills)
        system_prompt = f"{self.spec.manager_prompt}\n\n{_roster_block(self.spec.agents)}"
        if skills_text:
            system_prompt = f"{system_prompt}\n\n## Reference knowledge\n{skills_text}"

        user_content = f"{context}\n\n{task}" if context else task

        manager_callback = _tag_event_callback(
            self._event_callback, team=self.spec.name, agent="manager", role="manager",
        )
        manager_llm = wrap_with_logging(
            self._llm, self._llm_call_store,
            service="vinu-agent", tier="manager", team=self.spec.name,
            agent="manager", role="manager", session_id=self._triggered_by_session_id,
        )
        t0 = time.perf_counter()

        def _new_loop() -> AgentLoop:
            return AgentLoop(
                registry=manager_registry,
                llm=manager_llm,
                event_callback=manager_callback,
                max_iterations=self._max_iterations,
            )

        needs_verdict = self.spec.name in TEAMS_REQUIRING_VERDICT
        min_attempts = MIN_RESEARCH_ATTEMPTS if self.spec.name == "research" else 0
        if min_attempts:
            user_content += (
                f"\n\nBudget: make at least {min_attempts} distinct candidate attempts (each: idea_generator, then "
                f"backtest_runner, then risk_critic, feeding every failure reason into the next idea) before you may "
                f"give up; a PASS ends the run earlier. You have {self._max_iterations} turns, not a handful: never "
                f"claim you ran out of iterations unless you really used them."
            )
        result = run_until_verdict(
            _new_loop,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            required=needs_verdict,
            max_nudges=MAX_VERDICT_NUDGES + min_attempts,
            attempts=lambda: delegate_tool.delegations.get("idea_generator", 0),
            min_attempts=min_attempts,
            budget=self._max_iterations,
        )
        elapsed = time.perf_counter() - t0

        if db_run is not None:
            content = result.get("content", "")
            if result.get("status") == "completed":
                result_json: dict[str, Any] = {"content": content, "status": result.get("status")}
                artifact_id = _apply_team_result_hook(
                    self.spec.name, content,
                    strategy_store=self._strategy_store, run_id=db_run.run_id,
                    ticker_ledger_store=self._ticker_ledger_store,
                    services_config=self._services_config,
                )
                if artifact_id:
                    result_json["artifact_id"] = artifact_id
                    # Pillar 7's traceability link, made real: this run
                    # touched this artifact -- findable later via
                    # run_store.list_by_artifact_id(artifact_id).
                    self._run_store.set_related_artifact_id(db_run.run_id, artifact_id)
                if self.spec.name == "screener" and self._ticker_summary_store is not None:
                    from .screener_summary_writer import write_ticker_summaries
                    tickers_written = write_ticker_summaries(
                        content, ticker_summary_store=self._ticker_summary_store,
                        source_run_id=db_run.run_id,
                    )
                    if tickers_written:
                        result_json["tickers_written"] = tickers_written
                self._run_store.mark_done(
                    db_run.run_id,
                    verdict=_extract_verdict(content),
                    result_json=result_json,
                    llm_calls_used=result.get("iterations", 0),
                    time_used_seconds=elapsed,
                )
            else:
                self._run_store.mark_failed(db_run.run_id, error_message=content)
            result = {**result, "run_id": db_run.run_id}

        return result
