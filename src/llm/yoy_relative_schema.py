from __future__ import annotations

from typing import Any


YOY_SCORE_BOUNDS = {
    "risk_change_score": (-1.0, 1.0),
    "new_material_risk_score": (0.0, 1.0),
    "risk_mitigation_score": (0.0, 1.0),
    "peer_relative_risk_score": (-1.0, 1.0),
    "direction_score": (-1.0, 1.0),
    "confidence": (0.0, 1.0),
}

YOY_NUMERIC_FIELDS = tuple(YOY_SCORE_BOUNDS)
YOY_TEXT_FIELDS = ("impact_label", "rationale")
YOY_SIGNAL_FIELDS = YOY_NUMERIC_FIELDS + YOY_TEXT_FIELDS


class YOYRelativeSignalValidationError(ValueError):
    """Raised when a YoY relative LLM response cannot be converted into the schema."""


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _coerce_score(payload: dict[str, Any], field: str) -> float:
    if field not in payload:
        raise YOYRelativeSignalValidationError(f"Missing required YoY LLM field: {field}")

    try:
        value = float(payload[field])
    except (TypeError, ValueError) as exc:
        raise YOYRelativeSignalValidationError(f"Invalid numeric YoY LLM field: {field}") from exc

    lower, upper = YOY_SCORE_BOUNDS[field]
    return _clamp(value, lower, upper)


def build_llm_yoy_relative_signal(scores: dict[str, float]) -> float:
    """Combine YoY relative LLM scores into one cross-sectional signal."""
    return float(
        scores["direction_score"]
        + 0.50 * scores["risk_change_score"]
        + 0.50 * scores["risk_mitigation_score"]
        + 0.50 * scores["peer_relative_risk_score"]
        - 0.75 * scores["new_material_risk_score"]
    )


def validate_yoy_relative_payload(payload: dict[str, Any]) -> dict[str, float | str]:
    """Validate and normalize one structured YoY relative LLM response."""
    if not isinstance(payload, dict):
        raise YOYRelativeSignalValidationError("YoY relative LLM response must be a JSON object.")

    scores = {field: _coerce_score(payload, field) for field in YOY_NUMERIC_FIELDS}
    scores["llm_yoy_relative_signal"] = build_llm_yoy_relative_signal(scores)

    impact_label = str(payload.get("impact_label", "")).strip().lower()
    if impact_label not in {"positive", "negative", "neutral", "uncertain"}:
        impact_label = "uncertain"

    rationale = str(payload.get("rationale", "")).strip()
    return {
        **scores,
        "impact_label": impact_label,
        "rationale": rationale[:1_000],
    }
