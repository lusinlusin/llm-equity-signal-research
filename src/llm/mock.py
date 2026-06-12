from __future__ import annotations

from src.features.text_signals import score_text
from src.llm.schema import validate_llm_signal_payload


def mock_extract_signal(ticker: str, filing_date: str, text: str) -> dict[str, float | str]:
    """Build a deterministic LLM-shaped payload for local dry-run tests."""
    base = score_text(text)
    payload = {
        "sentiment_score": base["sentiment_score"],
        "uncertainty_score": base["uncertainty_score"],
        "growth_outlook_score": base["growth_outlook_score"],
        "margin_pressure_score": base["margin_pressure_score"],
        "risk_severity_score": min(1.0, base["risk_intensity_rate"] / 10.0),
        "confidence": base["confidence"],
        "rationale": f"Mock extraction for {ticker} filing {filing_date}; derived from existing lexical scores.",
    }
    return validate_llm_signal_payload(payload)
