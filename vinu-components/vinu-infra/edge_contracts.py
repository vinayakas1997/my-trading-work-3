"""Layer B of newer-thinking-with-discussed/routing-find-and-fix/01-plan.md: the CONTRACT of a data connection.

`pipeline_edges.yaml` says who sends what to whom. This module says what the payload on a connection must
look like: one pydantic model per connection that carries a JSON payload, registered under the edge id(s) that
carry it. The same models are used three ways:

* static (no data needed, `tests/test_edge_contracts.py`): every model has an example that validates, every
  field appears as a literal in the producer's source, and every REQUIRED field appears in each consumer's
  source -- so a renamed key on either side fails a test instead of silently arriving as "missing";
* runtime (layer C, `check_payload`): a real payload is validated against the model and each problem is
  returned as one short line the edge recorder can log;
* documentation: `contract_schema(edge_id)` is the JSON schema of the connection.

Conventions (kept deliberately small):
* a field is REQUIRED when the producer always emits it and a consumer depends on it; everything else has a
  default. A producer variant that legitimately omits a field (e.g. an `empty` answer) is modelled as a default;
* extra keys are allowed (a producer adding a field must not break a consumer);
* validation is lax about types (an int where a float is declared is fine) but a missing required field or a
  value that cannot be coerced is a problem.

What it cannot tell you: that a value that has the right shape is correct. The static checks look for field
names as quoted literals, so a dynamically built key is invisible to them.
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, ValidationError

# edge id -> model. Filled by `contract_for(...)`.
CONTRACTS: dict[str, type["EdgeContract"]] = {}


class EdgeContract(BaseModel):
    """Base class: extra keys allowed; subclasses declare the fields a consumer may rely on."""

    model_config = ConfigDict(extra="allow")

    # Edge ids that carry this payload. Registered when the class is defined.
    EDGES: ClassVar[tuple[str, ...]] = ()


def contract_for(*edge_ids: str):
    """Class decorator: register a model as the contract of one or more edges."""

    def deco(cls: type[EdgeContract]) -> type[EdgeContract]:
        cls.EDGES = tuple(edge_ids)
        for e in edge_ids:
            if e in CONTRACTS:
                raise ValueError(f"edge {e!r} already has contract {CONTRACTS[e].__name__}")
            CONTRACTS[e] = cls
        return cls

    return deco


# ---------------------------------------------------------------- the connections


class PortfolioWeight(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = ""
    symbol: str = ""
    target_weight: float
    kind: str = ""


class CorrelationMatrix(BaseModel):
    model_config = ConfigDict(extra="allow")
    strategies: list[str]
    values: list[list[float]]


@contract_for("portfolio.state->live.scheduler", "portfolio.state->agent.order_guard")
class PortfolioState(EdgeContract):
    """GET /portfolio/state: the risk-parity book. `weights` is empty (and `status` is `empty`) when no strategy
    is ACTIVE -- both consumers treat that as 'nothing to do'."""

    weights: list[PortfolioWeight]
    status: str = "ok"
    correlation_matrix: CorrelationMatrix | None = None
    n_strategies: int = 0

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{
            "status": "ok", "n_strategies": 1,
            "weights": [{"name": "momo_aapl", "kind": "llm_python", "symbol": "AAPL", "target_weight": 1.0}],
            "correlation_matrix": {"strategies": ["momo_aapl"], "values": [[1.0]]},
        }]},
    )


class DrawdownInfo(BaseModel):
    model_config = ConfigDict(extra="allow")
    action: str
    current_drawdown: float | None = None
    threshold_breached: float | None = None


@contract_for("portfolio.daily_allocation->live.scheduler")
class DailyAllocation(EdgeContract):
    """GET /portfolio/daily-allocation: the portfolio book after every tilt, plus the capital the scheduler may
    actually deploy (`deployable_equity` / `account_equity`)."""

    weights: list[PortfolioWeight]
    status: str
    account_equity: float | None = None
    deployable_equity: float | None = None
    reserve_fraction: float | None = None
    drawdown_status: DrawdownInfo | None = None
    risk_budget: dict[str, Any] | None = None

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{
            "status": "ok",
            "weights": [{"name": "momo_aapl", "symbol": "AAPL", "target_weight": 0.5}],
            "account_equity": 100000.0, "deployable_equity": 90000.0, "reserve_fraction": 0.1,
            "drawdown_status": {"action": "ok", "current_drawdown": 0.0, "threshold_breached": None},
            "risk_budget": {"date": "2026-10-04", "equity": 100000.0, "symbols": [], "aggregate": {}},
        }]},
    )


class SymbolRisk(BaseModel):
    model_config = ConfigDict(extra="allow")
    symbol: str
    halted: bool = False
    daily_pnl_pct: float = 0.0
    suggested_size_multiplier: float | None = None


@contract_for("portfolio.risk_status->agent.order_guard")
class RiskStatus(EdgeContract):
    """GET /portfolio/risk/status. When the portfolio has no allocation the route returns that (empty)
    allocation instead, which has no `symbols`: the order guard cannot tell that apart from 'no position yet'
    (known, recorded in routing-find-and-fix/03-findings.md)."""

    symbols: list[SymbolRisk] = []
    aggregate: dict[str, Any] = {}
    equity: float | None = None
    regime: str | None = None

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{
            "date": "2026-10-04", "equity": 100000.0, "regime": "trend_up",
            "symbols": [{"symbol": "AAPL", "halted": False, "daily_pnl_pct": -0.4, "suggested_size_multiplier": 1.0}],
            "aggregate": {"status": "ok"},
        }]},
    )


@contract_for("maturity.status->live.limits", "maturity.status->agent.live_decision_context")
class MaturityStatus(EdgeContract):
    """GET /research/maturity/status: the system-wide maturity tier. Both consumers fail open when the
    answer lacks `tier`."""

    tier: str
    n_real_trades: int = 0
    n_paper_trading_days: int = 0
    directional_accuracy: float | None = None
    regime_coverage: Any = None

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{
            "tier": "cold_start", "n_real_trades": 0, "n_paper_trading_days": 0,
            "directional_accuracy": 0.0, "regime_coverage": {},
        }]},
    )


@contract_for("strategy.config->live.scheduler")
class StrategyConfig(EdgeContract):
    """GET /strategy/strategies/{name}: one strategy's resolved config. The scheduler reads the live-decision
    position size from it (0.0 means 'no size configured', never an invented default)."""

    name: str = ""
    live_decision_position_size: float = 0.0
    live_decision_stop_pct: float | None = None
    live_decision_max_hold_bars: int | None = None
    universe: list[str] = []

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{
            "name": "momo", "universe": ["AAPL"], "live_decision_position_size": 0.05,
            "live_decision_stop_pct": 0.02, "live_decision_max_hold_bars": 20,
        }]},
    )


@contract_for("strategy.stop_rules->live.poller")
class StrategyStopRules(EdgeContract):
    """The stop and hold limits in the same /strategy/strategies/{name} answer; the live-decision poller applies
    them to every open live-decision position. None means 'not configured', never a default stop."""

    live_decision_stop_pct: float | None = None
    live_decision_max_hold_bars: int | None = None

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{"live_decision_stop_pct": 0.02, "live_decision_max_hold_bars": 20}]},
    )


@contract_for("reflection.synthesis->agent.idea_generator")
class ReflectionSynthesis(EdgeContract):
    """GET /reflection/synthesis/latest: `{"status": "none"}` most cycles (expected, not an error), otherwise
    `{"status": "ok", "synthesis": {...}}`. The agent hands the body to the model unread, so only `status` is
    relied on."""

    status: str
    synthesis: dict[str, Any] | None = None

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{"status": "none"}, {"status": "ok", "synthesis": {"synthesis_id": "abc"}}]},
    )


@contract_for("reflection.notable_beliefs->agent.live_decision_context")
class NotableBeliefs(EdgeContract):
    """GET /reflection/beliefs/notable: `beliefs` is empty most cycles (most scopes are routine)."""

    beliefs: list[dict[str, Any]]
    count: int = 0

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{"beliefs": [{"scope": "regime", "severity": "degrading"}], "count": 1}]},
    )


@contract_for("initial_analysis.trend_lifecycle_rows->agent.live_decision_context")
class AngleRows(EdgeContract):
    """GET /analysis/angle/{angle}/{ticker}: the stored rows of one angle, oldest first; `data` is empty until the angle has run."""

    data: list[dict[str, Any]]
    row_count: int = 0

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{"data": [{"type": "summary", "analogue_n": 5}], "row_count": 1}]},
    )


@contract_for("research.strategy_validations->live.poller")
class StrategyValidations(EdgeContract):
    """GET /research/strategy-validations: one row per live-decision strategy: its verdict and the exact rules it covers."""

    validations: list[dict[str, Any]]
    count: int = 0

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{"validations": [{"strategy_id": "s", "status": "validated", "fingerprint": "abc",
                                                          "detail": {"eligible_tickers": ["AAPL"]}}], "count": 1}]},
    )


@contract_for("research.unconfirmed_moves->agent.live_decision_context")
class UnconfirmedMoves(EdgeContract):
    """GET /research/unconfirmed-moves: real moves with no matching trigger on file."""

    events: list[dict[str, Any]]
    count: int = 0

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{"events": [{"symbol": "AAPL"}], "count": 1}]},
    )


@contract_for("research.unresolved_triggers->live.poller")
class SignalEvidenceList(EdgeContract):
    """GET /research/signal-evidence: recorded must-condition triggers for a symbol, newest first; a row has no
    `outcome_recorded_at` until its horizon has been resolved."""

    triggers: list[dict[str, Any]]
    count: int = 0

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{
            "count": 1,
            "triggers": [{"trigger_id": "t1", "symbol": "AAPL", "trigger_time": "2026-10-04T14:00:00+00:00",
                          "granularity": "15m", "outcome_recorded_at": None}],
        }]},
    )


class RankedCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")
    symbol: str
    final_score: float | None = None


@contract_for("screener.top->agent.planner_worker")
class ScreenerRanking(EdgeContract):
    """GET /screener/rankers/{id}/latest: 404 (not this shape) until the ranker has run once."""

    top: list[RankedCandidate]
    ranker_id: str = ""
    generated_at: float | str | None = None

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{
            "ranker_id": "momentum", "generated_at": 1759536000.0,
            "top": [{"symbol": "AAPL", "final_score": 0.8}],
        }]},
    )


@contract_for("live_decision.input_novelty->live.poller")
class NoveltyResult(EdgeContract):
    """novelty_ratio(...): `status` is `insufficient_reference` (unknown, not novel) until enough history exists."""

    status: str
    ratio: float | None = None
    novelty_high: bool = False
    n_reference: int = 0

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{"status": "ok", "ratio": 1.2, "novelty_high": False, "n_reference": 120}]},
    )


@contract_for("models.angle_compute->initial_analysis.runner")
class ModelAngleCompute(EdgeContract):
    """POST /models/angle/{angle}/compute: the rows the angle's own compute() produced, plus how many came from
    a real model versus the fallback proxy."""

    rows: list[dict[str, Any]]
    angle: str = ""
    row_count: int = 0
    backends: dict[str, int] = {}

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{
            "angle": "chronos", "row_count": 1, "rows": [{"ts": 1759536000, "model_backend": "chronos"}],
            "backends": {"chronos": 1},
        }]},
    )


class FinbertResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    finbert_label: str
    finbert_score: float


@contract_for("models.finbert_score->news.backfill")
class ModelFinbertScore(EdgeContract):
    """POST /models/finbert/score: one result per input text, in order."""

    results: list[FinbertResult]
    count: int = 0

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={"examples": [{"count": 1, "results": [{"finbert_label": "positive", "finbert_score": 0.62}]}]},
    )


# ---------------------------------------------------------------- runtime check (layer C will call this)


def check_payload(edge_id: str, payload: Any) -> list[str]:
    """Problems found validating `payload` against the edge's contract; an empty list means it matches.
    An edge with no contract returns an empty list (it is checked by the static manifest only). Never raises."""
    model = CONTRACTS.get(edge_id)
    if model is None:
        return []
    try:
        model.model_validate(payload)
    except ValidationError as exc:
        return [f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}" for err in exc.errors()]
    except Exception as exc:  # noqa: BLE001 -- observe-only
        return [f"<root>: {exc}"]
    return []


def contract_schema(edge_id: str) -> dict[str, Any] | None:
    model = CONTRACTS.get(edge_id)
    return model.model_json_schema() if model is not None else None


def contract_example(edge_id: str) -> dict[str, Any] | None:
    model = CONTRACTS.get(edge_id)
    if model is None:
        return None
    examples = model.model_config.get("json_schema_extra", {}).get("examples") or []  # type: ignore[union-attr]
    return examples[0] if examples else None


def field_names(model: type[BaseModel], *, required_only: bool = False) -> list[tuple[str, bool]]:
    """(field name, required) for a model and every nested model, in declaration order, de-duplicated.
    A nested field counts as required only when its whole path of parents is required too: a consumer that
    never reads an optional section does not depend on what is inside it."""
    out: dict[str, bool] = {}

    def walk(m: type[BaseModel], parent_required: bool) -> None:
        for name, info in m.model_fields.items():
            req = info.is_required() and parent_required
            out[name] = out.get(name, False) or req
            for sub in _nested_models(info.annotation):
                walk(sub, req)

    walk(model, True)
    return [(n, r) for n, r in out.items() if r or not required_only]


def _nested_models(annotation: Any) -> list[type[BaseModel]]:
    found: list[type[BaseModel]] = []
    stack = [annotation]
    while stack:
        a = stack.pop()
        if isinstance(a, type) and issubclass(a, BaseModel):
            found.append(a)
        stack.extend(getattr(a, "__args__", ()) or ())
    return found


# ---------------------------------------------------------------- static check (no data needed)


def _mentions(text: str, name: str) -> bool:
    return f'"{name}"' in text or f"'{name}'" in text or f"{name}=" in text or f"{name}:" in text


def static_problems(edge: Any, root: Any = None) -> list[str]:
    """Why this edge's contract is not backed by the source; empty when it is. Checks, for a wired edge:
    it names a registered model (or gives a written reason for having none), the model's example validates,
    every field appears in the producer's source, every required field appears in each consumer file set."""
    from vinu_infra.pipeline_edges import DEFAULT_ROOT, _read_all  # local: avoid an import cycle at module load

    root = root or DEFAULT_ROOT
    if edge.status != "wired":
        return []
    if edge.contract_none:
        return [f"{edge.id}: has both contract_none and contract"] if edge.contract else []
    if not edge.contract:
        return [f"{edge.id}: no contract and no contract_none reason"]
    model = CONTRACTS.get(edge.id)
    if model is None:
        return [f"{edge.id}: contract {edge.contract!r} is not registered for this edge in edge_contracts.py"]
    problems: list[str] = []
    if model.__name__ != edge.contract:
        problems.append(f"{edge.id}: manifest says {edge.contract!r} but the registered model is {model.__name__!r}")
    example = contract_example(edge.id)
    if example is None:
        problems.append(f"{edge.id}: {model.__name__} has no example payload")
    else:
        problems += [f"{edge.id}: example does not validate -- {p}" for p in check_payload(edge.id, example)]
    producer_text, missing = _read_all(root, list(edge.producer_files) + list(edge.contract_producer_files))
    if missing:
        problems.append(f"{edge.id}: producer file(s) not found: {missing}")
    consumer_text, missing = _read_all(root, list(edge.consumer_files))
    if missing:
        problems.append(f"{edge.id}: consumer file(s) not found: {missing}")
    for name, required in field_names(model):
        if not _mentions(producer_text, name):
            problems.append(f"{edge.id}: field {name!r} is not mentioned in the producer source")
        if required and not _mentions(consumer_text, name):
            problems.append(f"{edge.id}: required field {name!r} is not mentioned in the consumer source")
    return problems
