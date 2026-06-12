from __future__ import annotations

from typing import Any


LLM_SCORE_BOUNDS = {
    "sentiment_score": (-1.0, 1.0),
    "uncertainty_score": (0.0, 1.0),
    "growth_outlook_score": (0.0, 1.0),
    "margin_pressure_score": (0.0, 1.0),
    "risk_severity_score": (0.0, 1.0),
    "confidence": (0.0, 1.0),
}

LLM_NUMERIC_FIELDS = tuple(LLM_SCORE_BOUNDS)
LLM_TEXT_FIELDS = ("rationale",)
LLM_SIGNAL_FIELDS = LLM_NUMERIC_FIELDS + LLM_TEXT_FIELDS


class LLMSignalValidationError(ValueError):
    """Raised when an LLM response cannot be converted into the signal schema."""


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _coerce_score(payload: dict[str, Any], field: str) -> float:
    if field not in payload:
        raise LLMSignalValidationError(f"Missing required LLM score field: {field}")

    try:
        value = float(payload[field])
    except (TypeError, ValueError) as exc:
        raise LLMSignalValidationError(f"Invalid numeric LLM score field: {field}") from exc

    lower, upper = LLM_SCORE_BOUNDS[field]
    return _clamp(value, lower, upper)


def build_llm_text_signal(scores: dict[str, float]) -> float:
    """Combine structured LLM scores into a scalar cross-sectional signal."""
    return float(
        scores["sentiment_score"]
        + 0.50 * scores["growth_outlook_score"]
        - 0.50 * scores["uncertainty_score"]
        - 0.75 * scores["margin_pressure_score"]
        - 0.50 * scores["risk_severity_score"]
    )


def validate_llm_signal_payload(payload: dict[str, Any]) -> dict[str, float | str]:
    """Validate and normalize one structured LLM response."""
    if not isinstance(payload, dict):
        raise LLMSignalValidationError("LLM response must be a JSON object.")

    scores = {field: _coerce_score(payload, field) for field in LLM_NUMERIC_FIELDS}
    scores["llm_text_signal"] = build_llm_text_signal(scores)

    rationale = str(payload.get("rationale", "")).strip()
    return {
        **scores,
        "rationale": rationale[:1_000],
    }
