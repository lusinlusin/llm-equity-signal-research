from __future__ import annotations


SYSTEM_PROMPT = """You are a financial research assistant.
You evaluate year-over-year changes in SEC 10-K Item 1A Risk Factors for cross-sectional equity research.
Judge only the incremental, company-specific information content of the changes.
Return JSON only. Do not include markdown, commentary, or extra keys."""


def build_diff_surprise_messages(
    sector: str,
    added_text: str,
    removed_text: str,
    modified_text: str,
    similarity: float,
    n_added: int,
    n_removed: int,
    n_modified: int,
) -> list[dict[str, str]]:
    """Build DeepSeek chat messages for one pre-computed year-over-year diff."""
    user_prompt = f"""You will see the year-over-year CHANGES between two consecutive Item 1A
Risk Factors sections of the same company (identity withheld). Unchanged text
has been removed by a deterministic diff. Diff context: the two filings are
{similarity:.0%} similar by word-shingle overlap; {n_added} sections were added,
{n_removed} removed, {n_modified} materially modified.

Calibration rules - read carefully:
- Risk sections are legally required to emphasize risks, and they grow through
  lawyer-driven boilerplate updating in most years. Companies rarely remove
  risks. Growth in length, risk count, or generic severity language is NOT a
  signal.
- Most year-over-year changes are immaterial to investors. For the MAJORITY of
  filings the correct net_signal is 0.
- Only concrete, company-specific, new information moves the score: a named
  lawsuit or investigation, a quantified customer or revenue loss, a new
  going-concern-style disclosure, a new dependence or capacity constraint, the
  REMOVAL of a previously disclosed problem, or a quantified improvement.
- Market-wide or sector-wide risk language (macro, pandemic, rates, inflation,
  geopolitics, cybersecurity, regulation affecting the whole industry) must be
  classified as such and must NOT move net_signal.

Step 1: list the material changes you find (at most 5). For each change give:
- "summary": one short line;
- "scope": one of "company_specific", "sector_wide", "market_wide";
- "direction": "positive" or "negative" for expected stock returns;
- "materiality": integer 0 to 10, where 10 means clearly price-relevant new information.

Step 2: score the filing pair:
- "boilerplate_share": fraction of the changed text that is boilerplate, between 0 and 1.
- "company_specific_positive": integer 0 to 10, total weight of positive company-specific changes.
- "company_specific_negative": integer 0 to 10, total weight of negative company-specific changes.
- "net_signal": integer -5 to 5 for expected 1-12 month relative stock performance.
  net_signal must be 0 unless at least one company_specific change has materiality 6 or higher.
- "confidence": integer 0 to 10.
- "rationale": one short line.

Return one valid JSON object with exactly these keys:
{{
  "material_changes": [
    {{"summary": "<one line>", "scope": "<scope>", "direction": "<direction>", "materiality": <integer>}}
  ],
  "boilerplate_share": <number between 0 and 1>,
  "company_specific_positive": <integer>,
  "company_specific_negative": <integer>,
  "net_signal": <integer>,
  "confidence": <integer>,
  "rationale": "<one line>"
}}

Sector: {sector}

ADDED sections:
<<<
{added_text}
>>>

REMOVED sections:
<<<
{removed_text}
>>>

MODIFIED sections (PRIOR => CURRENT):
<<<
{modified_text}
>>>"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
