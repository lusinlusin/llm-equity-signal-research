from __future__ import annotations

import re

import pandas as pd


POSITIVE_TERMS = (
    "accelerated",
    "confidence",
    "confident",
    "discipline",
    "disciplined",
    "growth",
    "healthy",
    "improved",
    "improving",
    "momentum",
    "positive",
    "recovery",
    "resilient",
    "stable",
    "strong",
    "stronger",
    "supported",
)

NEGATIVE_TERMS = (
    "cautious",
    "competition",
    "decline",
    "declining",
    "drag",
    "headwinds",
    "lower",
    "pressured",
    "reduced",
    "risk",
    "risks",
    "slowdown",
    "softened",
    "uncertainty",
    "weak",
    "weakened",
)

UNCERTAINTY_TERMS = (
    "cautious",
    "limited visibility",
    "macro",
    "risk",
    "risks",
    "uncertainty",
    "unclear",
    "volatility",
)

GROWTH_TERMS = (
    "accelerated",
    "adoption",
    "demand",
    "growth",
    "guidance",
    "improved outlook",
    "momentum",
    "orders",
    "recovery",
    "revenue",
    "sales",
    "strong outlook",
)

MARGIN_PRESSURE_TERMS = (
    "cost pressure",
    "discounting",
    "fulfillment cost",
    "input cost",
    "inflation",
    "lower gross margins",
    "margin pressure",
    "mix pressure",
    "price competition",
    "price reductions",
    "pressured margins",
    "wage",
)

FINANCIAL_NEGATIVE_TERMS = (
    "adverse",
    "bankruptcy",
    "breach",
    "challenging",
    "default",
    "deterioration",
    "disruption",
    "impairment",
    "investigation",
    "lawsuit",
    "liability",
    "litigation",
    "loss",
    "material adverse",
    "penalty",
    "recession",
    "restructuring",
    "shortage",
    "weakness",
)

FINANCIAL_POSITIVE_TERMS = (
    "benefit",
    "efficient",
    "favorable",
    "gain",
    "innovation",
    "opportunity",
    "profitability",
    "robust",
    "strength",
    "successful",
)

RISK_INTENSITY_TERMS = (
    "cybersecurity",
    "geopolitical",
    "legal proceedings",
    "material adverse",
    "regulatory",
    "significant risk",
    "substantial risk",
    "supply chain",
    "tax risk",
)


def _count_terms(text: str, terms: tuple[str, ...]) -> int:
    normalized = text.lower()
    hits = 0
    for term in terms:
        if " " in term:
            hits += normalized.count(term)
        else:
            hits += len(re.findall(rf"\b{re.escape(term)}\b", normalized))
    return hits


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[a-zA-Z]+\b", text))


def _rate_per_1000_words(hits: int, word_count: int) -> float:
    if word_count <= 0:
        return 0.0
    return hits / word_count * 1_000.0


def score_text(text: str) -> dict[str, float]:
    """Convert one text record into transparent structured signal scores."""
    positive_hits = _count_terms(text, POSITIVE_TERMS)
    negative_hits = _count_terms(text, NEGATIVE_TERMS)
    uncertainty_hits = _count_terms(text, UNCERTAINTY_TERMS)
    growth_hits = _count_terms(text, GROWTH_TERMS)
    margin_hits = _count_terms(text, MARGIN_PRESSURE_TERMS)
    financial_positive_hits = _count_terms(text, FINANCIAL_POSITIVE_TERMS)
    financial_negative_hits = _count_terms(text, FINANCIAL_NEGATIVE_TERMS)
    risk_intensity_hits = _count_terms(text, RISK_INTENSITY_TERMS)
    words = _word_count(text)

    sentiment_score = (positive_hits - negative_hits) / (positive_hits + negative_hits + 1.0)
    uncertainty_score = uncertainty_hits / (uncertainty_hits + positive_hits + negative_hits + 1.0)
    growth_outlook_score = growth_hits / (growth_hits + negative_hits + 1.0)
    margin_pressure_score = margin_hits / (margin_hits + positive_hits + 1.0)
    text_signal = (
        sentiment_score
        + 0.50 * growth_outlook_score
        - 0.50 * uncertainty_score
        - 0.75 * margin_pressure_score
    )
    financial_sentiment_score = (
        (positive_hits + financial_positive_hits) - (negative_hits + financial_negative_hits)
    ) / (positive_hits + financial_positive_hits + negative_hits + financial_negative_hits + 1.0)
    uncertainty_rate = _rate_per_1000_words(uncertainty_hits, words)
    risk_intensity_rate = _rate_per_1000_words(risk_intensity_hits + financial_negative_hits, words)
    growth_rate = _rate_per_1000_words(growth_hits + financial_positive_hits, words)
    margin_pressure_rate = _rate_per_1000_words(margin_hits, words)
    enhanced_text_signal = (
        financial_sentiment_score
        + 0.08 * growth_rate
        - 0.10 * uncertainty_rate
        - 0.10 * risk_intensity_rate
        - 0.08 * margin_pressure_rate
    )
    total_hits = (
        positive_hits
        + negative_hits
        + uncertainty_hits
        + growth_hits
        + margin_hits
        + financial_positive_hits
        + financial_negative_hits
        + risk_intensity_hits
    )

    return {
        "word_count": float(words),
        "positive_hits": float(positive_hits),
        "negative_hits": float(negative_hits),
        "uncertainty_hits": float(uncertainty_hits),
        "growth_hits": float(growth_hits),
        "margin_pressure_hits": float(margin_hits),
        "financial_positive_hits": float(financial_positive_hits),
        "financial_negative_hits": float(financial_negative_hits),
        "risk_intensity_hits": float(risk_intensity_hits),
        "sentiment_score": float(sentiment_score),
        "uncertainty_score": float(uncertainty_score),
        "growth_outlook_score": float(growth_outlook_score),
        "margin_pressure_score": float(margin_pressure_score),
        "financial_sentiment_score": float(financial_sentiment_score),
        "uncertainty_rate": float(uncertainty_rate),
        "risk_intensity_rate": float(risk_intensity_rate),
        "growth_rate": float(growth_rate),
        "margin_pressure_rate": float(margin_pressure_rate),
        "confidence": float(min(1.0, total_hits / 6.0)),
        "text_signal": float(text_signal),
        "enhanced_text_signal": float(enhanced_text_signal),
    }


def score_text_records(records: pd.DataFrame) -> pd.DataFrame:
    """Score every text record and keep the original text metadata."""
    score_rows = [score_text(text) for text in records["text"]]
    scores = pd.DataFrame(score_rows, index=records.index)
    return pd.concat([records.reset_index(drop=True), scores.reset_index(drop=True)], axis=1)


def build_text_signal_matrix(
    text_features: pd.DataFrame,
    signal_column: str = "text_signal",
) -> pd.DataFrame:
    """Aggregate scored text records into a month-end ticker signal matrix."""
    required_columns = {"signal_date", "ticker", signal_column}
    missing_columns = required_columns.difference(text_features.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Text features are missing required columns: {missing}")

    monthly_signal = (
        text_features.groupby(["signal_date", "ticker"])[signal_column]
        .mean()
        .unstack("ticker")
        .sort_index()
    )
    return monthly_signal.dropna(axis=0, how="all").dropna(axis=1, how="all")


def build_point_in_time_text_signal_matrix(
    text_features: pd.DataFrame,
    monthly_index: pd.Index,
    tickers: pd.Index | list[str],
    signal_column: str = "text_signal",
) -> pd.DataFrame:
    """Forward-fill each ticker's latest published text signal onto month-end dates."""
    event_signal = build_text_signal_matrix(text_features, signal_column=signal_column)
    month_ends = pd.DatetimeIndex(monthly_index)
    ticker_list = [str(ticker).upper() for ticker in tickers]

    event_signal = event_signal.reindex(columns=ticker_list)
    full_index = event_signal.index.union(month_ends).sort_values()
    point_in_time_signal = event_signal.reindex(full_index).ffill().loc[month_ends]
    return point_in_time_signal.dropna(axis=0, how="all").dropna(axis=1, how="all")
