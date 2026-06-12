from __future__ import annotations

import json
from typing import Any


DIFF_SCORE_BOUNDS = {
    "boilerplate_share": (0.0, 1.0),
    "company_specific_positive": (0.0, 10.0),
    "company_specific_negative": (0.0, 10.0),
    "net_signal": (-5.0, 5.0),
    "confidence": (0.0, 10.0),
}

DIFF_INTEGER_FIELDS = (
    "company_specific_positive",
    "company_specific_negative",
    "net_signal",
    "confidence",
)

DIFF_NUMERIC_FIELDS = tuple(DIFF_SCORE_BOUNDS)
DIFF_CHANGE_SCOPES = ("company_specific", "sector_wide", "market_wide")
DIFF_CHANGE_DIRECTIONS = ("positive", "negative")
MATERIALITY_GATE = 6.0


class DiffSurpriseSignalValidationError(ValueError):
    """Raised when a diff-surprise LLM response cannot be converted into the schema."""


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _coerce_score(payload: dict[str, Any], field: str) -> float:
    if field not in payload:
        raise DiffSurpriseSignalValidationError(f"Missing required diff LLM field: {field}")

    try:
        value = float(payload[field])
    except (TypeError, ValueError) as exc:
        raise DiffSurpriseSignalValidationError(f"Invalid numeric diff LLM field: {field}") from exc

    lower, upper = DIFF_SCORE_BOUNDS[field]
    value = _clamp(value, lower, upper)
    if field in DIFF_INTEGER_FIELDS:
        value = float(round(value))
    return value


def _coerce_material_changes(payload: dict[str, Any]) -> list[dict[str, float | str]]:
    raw_changes = payload.get("material_changes", [])
    if raw_changes is None:
        raw_changes = []
    if not isinstance(raw_changes, list):
        raise DiffSurpriseSignalValidationError("material_changes must be a JSON array.")

    changes: list[dict[str, float | str]] = []
    for raw in raw_changes[:5]:
        if not isinstance(raw, dict):
            raise DiffSurpriseSignalValidationError("Each material change must be a JSON object.")
        scope = str(raw.get("scope", "")).strip().lower()
        if scope not in DIFF_CHANGE_SCOPES:
            raise DiffSurpriseSignalValidationError(f"Invalid material change scope: {scope!r}")
        direction = str(raw.get("direction", "")).strip().lower()
        if direction not in DIFF_CHANGE_DIRECTIONS:
            raise DiffSurpriseSignalValidationError(f"Invalid material change direction: {direction!r}")
        try:
            materiality = float(raw.get("materiality"))
        except (TypeError, ValueError) as exc:
            raise DiffSurpriseSignalValidationError("Invalid material change materiality.") from exc
        changes.append(
            {
                "summary": str(raw.get("summary", "")).strip(),
                "scope": scope,
                "direction": direction,
                "materiality": float(round(_clamp(materiality, 0.0, 10.0))),
            }
        )
    return changes


def build_llm_diff_surprise_signal(scores: dict[str, float]) -> float:
    """Combine diff-surprise LLM scores into one cross-sectional signal.

    `net_signal` is the primary judgment; the company-specific intensity spread
    adds within-bucket granularity so tied committed scores can still be ranked.
    Rows with `net_signal == 0` stay exactly 0: the prompt's materiality rule says
    no position without a high-materiality company-specific change, so sub-threshold
    intensity must not leak a direction into the neutral bucket.
    """
    if scores["net_signal"] == 0:
        return 0.0
    return float(
        scores["net_signal"]
        + 0.25 * (scores["company_specific_positive"] - scores["company_specific_negative"])
    )


def gate_violated(net_signal: float, changes: list[dict[str, float | str]]) -> bool:
    """True when net_signal is nonzero without a qualifying company-specific change."""
    if net_signal == 0:
        return False
    return not any(
        change["scope"] == "company_specific" and float(change["materiality"]) >= MATERIALITY_GATE
        for change in changes
    )


def validate_diff_surprise_payload(payload: dict[str, Any]) -> dict[str, float | str]:
    """Validate and normalize one structured diff-surprise LLM response."""
    if not isinstance(payload, dict):
        raise DiffSurpriseSignalValidationError("Diff-surprise LLM response must be a JSON object.")

    scores = {field: _coerce_score(payload, field) for field in DIFF_NUMERIC_FIELDS}
    changes = _coerce_material_changes(payload)

    result: dict[str, float | str] = dict(scores)
    result["material_changes"] = json.dumps(changes)
    result["n_material_changes"] = float(len(changes))
    result["n_company_specific_changes"] = float(
        sum(1 for change in changes if change["scope"] == "company_specific")
    )
    result["gate_violation"] = float(gate_violated(scores["net_signal"], changes))
    result["llm_diff_surprise_signal"] = build_llm_diff_surprise_signal(scores)
    result["rationale"] = str(payload.get("rationale", "")).strip()
    return result
