from __future__ import annotations

import logging
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from vinu_research.config import ResearchConfig
from vinu_research.models import CalibrationEntry, CalibrationResult, Forecast

logger = logging.getLogger(__name__)

_MIN_WINDOW = 10
_DEFAULT_ACCURACY_NULL = 0.5
_DEFAULT_BRIER_NULL = 0.25
_DEFAULT_MAGNITUDE_MAPE_NULL = 0.50


@dataclass
class ForecastSkillConfig:
    min_calibration_window: int = _MIN_WINDOW
    null_accuracy: float = _DEFAULT_ACCURACY_NULL
    null_brier: float = _DEFAULT_BRIER_NULL
    null_magnitude_mape: float = _DEFAULT_MAGNITUDE_MAPE_NULL
    accuracy_improvement_threshold: float = 0.05
    brier_improvement_threshold: float = 0.03
    magnitude_improvement_threshold: float = 0.05
    llm_model: str = ""
    llm_base_url: str = ""
    llm_max_tokens: int = 2000

    @classmethod
    def from_research_config(cls, cfg: ResearchConfig) -> ForecastSkillConfig:
        return cls(
            llm_model=cfg.llm_model,
            llm_base_url=cfg.llm_base_url,
            llm_max_tokens=cfg.llm_max_tokens,
        )


def compute_brier_score(
    forecast_direction: str,
    forecast_confidence: float,
    actual_return_pct: float,
) -> float:
    if forecast_direction == "long":
        predicted_class = 1.0 if actual_return_pct > 0 else 0.0
        prob = forecast_confidence
    elif forecast_direction == "short":
        predicted_class = 1.0 if actual_return_pct < 0 else 0.0
        prob = forecast_confidence
    else:
        predicted_class = 0.5
        prob = 0.5
    return (prob - predicted_class) ** 2


def compute_directional_error(
    forecast_direction: str,
    actual_return_pct: float,
) -> bool:
    if forecast_direction == "long":
        return actual_return_pct > 0
    if forecast_direction == "short":
        return actual_return_pct < 0
    return False


def compute_calibration(
    entries: list[CalibrationEntry],
    config: ForecastSkillConfig | None = None,
) -> CalibrationResult:
    cfg = config or ForecastSkillConfig()
    n = len(entries)
    if n == 0:
        return CalibrationResult(
            artifact_id="",
            n_entries=0,
            passed=False,
            reasons=["no calibration entries yet"],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    accuracy = sum(1 for e in entries if e.directional_correct) / n
    brier_mean = statistics.mean(e.brier_score for e in entries)
    magnitude_errors = [e.magnitude_error for e in entries if e.forecast_magnitude_pct > 0]
    magnitude_mape = statistics.mean(magnitude_errors) if magnitude_errors else 1.0

    reasons: list[str] = []
    passed = True

    if n >= cfg.min_calibration_window:
        if accuracy <= cfg.null_accuracy + cfg.accuracy_improvement_threshold:
            reasons.append(
                f"accuracy {accuracy:.3f} ≤ null {cfg.null_accuracy} "
                f"+ threshold {cfg.accuracy_improvement_threshold}"
            )
            passed = False
        if brier_mean >= cfg.null_brier - cfg.brier_improvement_threshold:
            reasons.append(
                f"brier {brier_mean:.3f} ≥ null {cfg.null_brier} "
                f"- threshold {cfg.brier_improvement_threshold}"
            )
            passed = False
        if magnitude_mape >= cfg.null_magnitude_mape - cfg.magnitude_improvement_threshold:
            reasons.append(
                f"magnitude MAPE {magnitude_mape:.3f} ≥ null {cfg.null_magnitude_mape}"
            )
            passed = False
    else:
        reasons.append(
            f"insufficient calibration entries ({n} < {cfg.min_calibration_window})"
        )
        passed = False

    return CalibrationResult(
        artifact_id=entries[0].artifact_id,
        n_entries=n,
        accuracy=accuracy,
        brier_mean=brier_mean,
        magnitude_mape=magnitude_mape,
        passed=passed,
        reasons=reasons,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


_FORECAST_SYSTEM_PROMPT = (
    "You are a quantitative forecast generator. Given personality "
    "features and risk state for a symbol, produce a structured "
    "forecast: direction (long/short/neutral), confidence (0-1), "
    "expected magnitude percent, magnitude standard deviation, "
    "and horizon in days. Return ONLY valid JSON with keys: "
    "direction, confidence, magnitude_pct, magnitude_std, horizon_days, reasoning. "
    "No markdown fences."
)


async def generate_forecast(
    symbol: str,
    personality_features: dict[str, Any],
    risk_state: dict[str, Any],
    config: ResearchConfig,
    llm_client: Any | None = None,
) -> Forecast:
    """Produce a direction/magnitude forecast via the research LLM client.

    `llm_client` must expose an async `chat_json(system, user) -> dict | None`
    method — the same interface as `ResearchLlmClient` (vinu_research.llm). A
    client is constructed from `config` when none is supplied.
    """
    if llm_client is None:
        from vinu_research.llm import ResearchLlmClient

        llm_client = ResearchLlmClient(config)

    prompt = _build_forecast_prompt(symbol, personality_features, risk_state)

    data = await llm_client.chat_json(_FORECAST_SYSTEM_PROMPT, prompt)
    if not isinstance(data, dict):
        logger.warning("LLM forecast call failed for %s — using neutral default", symbol)
        data = {
            "direction": "neutral",
            "confidence": 0.0,
            "magnitude_pct": 0.0,
            "magnitude_std": 0.0,
            "horizon_days": 1,
            "reasoning": "LLM call returned no usable output",
        }

    return Forecast(
        direction=data.get("direction", "neutral"),
        confidence=min(max(float(data.get("confidence", 0.0)), 0.0), 1.0),
        magnitude_pct=float(data.get("magnitude_pct", 0.0)),
        magnitude_std=float(data.get("magnitude_std", 0.0)),
        horizon_days=int(data.get("horizon_days", 1)),
        reasoning=str(data.get("reasoning", "")),
    )


def _build_forecast_prompt(
    symbol: str,
    personality: dict[str, Any],
    risk: dict[str, Any],
) -> str:
    lines = [f"Generate a forecast for {symbol}.\n"]
    lines.append("=== Personality Features ===")
    for k, v in _flatten_dict(personality).items():
        lines.append(f"  {k}: {v}")
    lines.append("=== Risk State ===")
    for k, v in _flatten_dict(risk).items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten_dict(v, key))
        else:
            result[key] = v
    return result
