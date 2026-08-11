"""The orchestrator's second entry point (Phase 6, New-talk-agents/
new-thinking/new-restructure/phases/phase-6-thesis-intake/): a human
hands the pipeline a raw theory via chat, THGATE checks it before any LLM
call, and only a "no duplicate AND under budget" theory ever reaches the
thesis_intake team. Mirrors delegate_to_team.py's direct-TeamManager-
construction pattern (not a call to that tool) since this needs to run
THGATE first and, on a WORTH_CHECKING verdict, hand off to a SECOND team
(research) afterward -- more than a single delegation.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from ..agent.thesis_intake_gate import CANDIDATE_PROPOSED_EVENT_TYPE, ThesisIntakeGate
from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_block(content: str) -> dict | None:
    match = _JSON_BLOCK_RE.search(content or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


class _InProcessHypothesisReader:
    """THGATE's near-duplicate lookup -- tries vinu-research's real local
    HypothesisRegistry directly first (see broker/research_link.py), falls
    back to HTTP (the same GET /research/hypotheses query_hypotheses_tool.py
    uses) only if that raises."""

    def __init__(self, base_url: str, *, timeout: float = 15.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def query_by_symbol(self, ticker: str) -> list[dict[str, Any]]:
        try:
            from ..broker.research_link import get_hypothesis_registry, serialize_hypothesis

            hypotheses = get_hypothesis_registry().query_by_symbol(ticker)
            return [serialize_hypothesis(h) for h in hypotheses]
        except Exception:
            LOG.debug("THGATE: in-process hypothesis read failed for %s, falling back to HTTP", ticker, exc_info=True)

        import httpx

        resp = httpx.get(
            f"{self._base_url}/research/hypotheses", params={"symbol": ticker}, timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("hypotheses", [])


class SubmitThesisTool(BaseTool):
    name = "submit_thesis"
    description = (
        "Submit a human trading theory for review -- an idea or analogy, not code, not even a "
        "formal recipe. Checked by a cheap, deterministic gate (near-duplicate + per-ticker "
        "candidate budget) before any LLM call; only a genuinely new, under-budget theory reaches "
        "the thesis_intake team's real review against angle data, the Summary Agent's read, and "
        "prior hypothesis history. On a WORTH_CHECKING verdict, hands off to the research team's "
        "own loop -- same downstream loop any system-generated idea uses."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "The stock symbol the theory is about"},
            "title": {"type": "string", "description": "A short title for the theory"},
            "thesis": {"type": "string", "description": "The theory itself, in the human's own words"},
        },
        "required": ["ticker", "title", "thesis"],
    }
    is_readonly = False
    repeatable = True

    def __init__(self) -> None:
        self._teams_dir: str = ""
        self._full_registry: Any = None
        self._llm: Any = None
        self._skills_loader: Any = None
        self._event_callback: Any = None
        self._run_store: Any = None
        self._llm_call_store: Any = None
        self._session_id: str = ""
        self._strategy_store: Any = None
        self._ticker_summary_store: Any = None
        self._ticker_ledger_store: Any = None
        self._services_config: dict = {}

    def execute(self, **kwargs: Any) -> str:
        ticker = kwargs["ticker"].upper()
        title = kwargs["title"]
        thesis = kwargs["thesis"]

        if not self._teams_dir or self._full_registry is None or self._llm is None:
            return json.dumps({"status": "error", "error": "submit_thesis not fully wired (missing teams_dir/registry/llm)"})
        if self._ticker_ledger_store is None:
            return json.dumps({"status": "error", "error": "submit_thesis not fully wired (missing ticker_ledger_store)"})

        research_api_url = self._services_config.get("vinu_research", "http://localhost:8087")
        gate = ThesisIntakeGate(_InProcessHypothesisReader(research_api_url), self._ticker_ledger_store)
        gate_result = gate.check(ticker, thesis)

        if not gate_result.allowed:
            return json.dumps({
                "status": "blocked_by_thgate",
                "ticker": ticker,
                "reason": gate_result.reason,
                "matched_hypothesis_id": gate_result.matched_hypothesis_id,
                "matched_thesis": gate_result.matched_thesis,
            })

        review_result = self._run_team(
            "thesis_intake",
            f"Ticker: {ticker}\nTitle: {title}\nThesis (verbatim, do not paraphrase): {thesis}",
        )
        if review_result.get("status") != "completed":
            return json.dumps({
                "status": "error", "error": "thesis_intake team did not complete",
                "detail": review_result,
            })

        verdict_data = _extract_json_block(review_result.get("content", "")) or {}
        verdict = verdict_data.get("verdict", "")

        if verdict != "WORTH_CHECKING":
            return json.dumps({
                "status": "does_not_hold_up",
                "ticker": ticker,
                "reasoning": verdict_data.get("reasoning", ""),
                "content": review_result.get("content", ""),
            })

        hypothesis_id = self._record_human_hypothesis(research_api_url, ticker, title, thesis)
        self._write_candidate_proposed_event(ticker, hypothesis_id)

        handoff_result = self._run_team(
            "research",
            f"Investigate this human-submitted, evidence-reviewed idea for {ticker}: {thesis}",
        )

        return json.dumps({
            "status": "worth_checking",
            "ticker": ticker,
            "hypothesis_id": hypothesis_id,
            "reasoning": verdict_data.get("reasoning", ""),
            "handoff_status": handoff_result.get("status"),
            "handoff_content": handoff_result.get("content", ""),
        })

    def _run_team(self, team_name: str, task: str) -> dict[str, Any]:
        from ..agent.team import TeamManager

        team_dir = Path(self._teams_dir) / team_name
        manager = TeamManager(
            team_dir,
            full_registry=self._full_registry,
            llm=self._llm,
            skills_loader=self._skills_loader,
            event_callback=self._event_callback,
            run_store=self._run_store,
            llm_call_store=self._llm_call_store,
            triggered_by_session_id=self._session_id,
            strategy_store=self._strategy_store,
            ticker_summary_store=self._ticker_summary_store,
            ticker_ledger_store=self._ticker_ledger_store,
            services_config=self._services_config,
        )
        return manager.run(task)

    def _record_human_hypothesis(self, research_api_url: str, ticker: str, title: str, thesis: str) -> str:
        """The ONLY write path for a human theory -- always tags
        source="human" (Hypothesis.create_from_human has no source
        parameter to override). In-process first (see
        broker/research_link.py), HTTP fallback (POST /hypotheses/human)
        only if that raises. Best-effort either way: a total failure is
        logged, not raised -- the review already completed and must not be
        lost because this specific write failed."""
        try:
            from vinu_research.models import Hypothesis

            from ..broker.research_link import get_hypothesis_registry

            h = Hypothesis.create_from_human(title=title, thesis=thesis, universe=[ticker])
            get_hypothesis_registry().create(h)
            return h.hypothesis_id
        except Exception:
            LOG.debug("in-process human-hypothesis write failed for %s, falling back to HTTP", ticker, exc_info=True)

        try:
            import httpx

            resp = httpx.post(
                f"{research_api_url}/research/hypotheses/human",
                json={"title": title, "thesis": thesis, "universe": [ticker]},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("hypothesis_id", "")
        except Exception:
            LOG.exception("failed to record human hypothesis for %s, continuing without it", ticker)
            return ""

    def _write_candidate_proposed_event(self, ticker: str, hypothesis_id: str) -> None:
        """The shared K-cap counter's write side (THGATE's own read side
        is in agent/thesis_intake_gate.py) -- best-effort, never blocks
        the real hand-off below it."""
        try:
            self._ticker_ledger_store.add_event(
                ticker=ticker, stage="thesis_intake", event_type=CANDIDATE_PROPOSED_EVENT_TYPE,
                text="human-submitted theory passed review, handed off to research",
                ref_id=hypothesis_id, source="human",
            )
        except Exception:
            LOG.exception("failed to write candidate_proposed TickerLedger event for %s, continuing without it", ticker)
