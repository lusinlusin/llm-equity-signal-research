from __future__ import annotations


SYSTEM_PROMPT = """You are a financial research assistant.
Extract a point-in-time equity signal from SEC 10-K Item 1A Risk Factors text.
Return JSON only. Do not include markdown, commentary, or extra keys."""


def build_signal_extraction_messages(
    ticker: str,
    filing_date: str,
    text: str,
    max_chars: int = 12_000,
) -> list[dict[str, str]]:
    """Build DeepSeek chat messages for one filing text."""
    clipped_text = text[:max_chars]
    user_prompt = f"""Return one valid JSON object with exactly these keys:
- sentiment_score
- uncertainty_score
- growth_outlook_score
- margin_pressure_score
- risk_severity_score
- confidence
- rationale

Do not copy or default to any example numeric values; no example numeric values are provided.

Scoring guide:
- sentiment_score: -1 is very negative for expected stock returns, 0 is neutral, 1 is very positive.
- uncertainty_score: 0 means little uncertainty, 1 means high uncertainty.
- growth_outlook_score: 0 means weak or no growth evidence, 1 means strong growth evidence.
- margin_pressure_score: 0 means little margin pressure, 1 means severe margin pressure.
- risk_severity_score: 0 means generic/low severity risks, 1 means severe business or financial risk.
- confidence: 0 means weak evidence, 1 means strong evidence.

SEC text:
<<<
{clipped_text}
>>>"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
