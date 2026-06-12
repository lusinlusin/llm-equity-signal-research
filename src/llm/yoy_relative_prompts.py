from __future__ import annotations


SYSTEM_PROMPT = """You are a financial research assistant.
Evaluate whether the latest SEC 10-K Item 1A Risk Factors update contains incrementally positive or negative information for the company's stock price.
Return JSON only. Do not include markdown, commentary, or extra keys."""


def build_yoy_relative_messages(
    ticker: str,
    company_name: str,
    sector: str,
    current_filing_date: str,
    prior_filing_date: str,
    current_text: str,
    prior_text: str,
    max_chars_per_filing: int = 10_000,
) -> list[dict[str, str]]:
    """Build DeepSeek chat messages for one current/prior filing pair."""
    current_clipped = current_text[:max_chars_per_filing]
    prior_clipped = prior_text[:max_chars_per_filing]
    user_prompt = f"""Return one valid JSON object with exactly these keys:
- risk_change_score
- new_material_risk_score
- risk_mitigation_score
- peer_relative_risk_score
- direction_score
- impact_label
- confidence
- rationale

Do not copy or default to any example numeric values; no example numeric values are provided.

Scoring guide:
- Do not score absolute risk level. Focus on incremental changes versus the prior filing.
- risk_change_score: -1 means risks clearly worsened, 0 means little change, 1 means risks clearly improved.
- new_material_risk_score: 0 means no important new risk, 1 means severe new or intensified material risks.
- risk_mitigation_score: 0 means no risk mitigation evidence, 1 means clear mitigation or reduced risk language.
- peer_relative_risk_score: -1 means unusually worse than a typical company in this sector, 0 means typical, 1 means unusually better.
- direction_score: 1 means incrementally positive for expected stock returns over the next 1-3 months, 0 means neutral or uncertain, -1 means incrementally negative.
- impact_label must be one of: positive, negative, neutral, uncertain.
- confidence: 0 means weak evidence, 1 means strong evidence.

Sector: {sector}

Current Item 1A Risk Factors:
<<<
{current_clipped}
>>>

Prior-year Item 1A Risk Factors:
<<<
{prior_clipped}
>>>"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
