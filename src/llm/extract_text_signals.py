from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from src.data.texts import load_text_dataset
from src.llm.deepseek_client import DeepSeekConfig, DeepSeekSignalExtractor
from src.llm.mock import mock_extract_signal


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data/raw/sec_10k_risk_factors.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/processed/llm_text_features.csv"


def _prefixed_llm_fields(
    payload: dict[str, float | str],
    provider: str,
    model: str,
) -> dict[str, float | str]:
    return {
        "llm_sentiment_score": payload["sentiment_score"],
        "llm_uncertainty_score": payload["uncertainty_score"],
        "llm_growth_outlook_score": payload["growth_outlook_score"],
        "llm_margin_pressure_score": payload["margin_pressure_score"],
        "llm_risk_severity_score": payload["risk_severity_score"],
        "llm_confidence": payload["confidence"],
        "llm_rationale": payload["rationale"],
        "llm_text_signal": payload["llm_text_signal"],
        "llm_provider": provider,
        "llm_model": model,
    }


def extract_llm_features(
    input_path: str | Path,
    output_path: str | Path,
    limit: int | None = None,
    mock: bool = False,
    model: str | None = None,
    resume: bool = False,
    sleep_seconds: float = 0.0,
) -> pd.DataFrame:
    records = load_text_dataset(input_path)
    if limit is not None:
        records = records.head(limit)

    output = Path(output_path)
    existing = pd.DataFrame()
    if resume and output.exists():
        existing = pd.read_csv(output)
        done_keys = set(
            zip(
                existing["ticker"].astype(str),
                pd.to_datetime(existing["date"]).dt.strftime("%Y-%m-%d"),
            )
        )
        record_keys = list(
            zip(
                records["ticker"].astype(str),
                pd.to_datetime(records["date"]).dt.strftime("%Y-%m-%d"),
            )
        )
        records = records[[key not in done_keys for key in record_keys]]

    config = DeepSeekConfig.from_env(model=model)
    extractor = None if mock else DeepSeekSignalExtractor(config)
    provider = "mock" if mock else "deepseek"
    output_model = "mock-lexical" if mock else config.model

    rows = []
    total = len(records) + len(existing)
    for row_number, (_, record) in enumerate(records.iterrows(), start=len(existing) + 1):
        filing_date = str(record["date"].date())
        if mock:
            payload = mock_extract_signal(record["ticker"], filing_date, record["text"])
        else:
            payload = extractor.extract_signal(record["ticker"], filing_date, record["text"])

        rows.append(
            {
                **record.to_dict(),
                **_prefixed_llm_fields(payload, provider=provider, model=output_model),
            }
        )
        combined = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(output, index=False)
        print(f"Processed {row_number}/{total}: {record['ticker']} {filing_date}", flush=True)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    features = pd.DataFrame(rows)
    if not existing.empty:
        features = pd.concat([existing, features], ignore_index=True)
    elif records.empty:
        features = existing
    return features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract LLM text signals from SEC filing text.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input CSV with date, ticker, text.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV for LLM feature rows.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of rows to process.")
    parser.add_argument("--mock", action="store_true", help="Use local deterministic mock extraction.")
    parser.add_argument("--model", default=None, help="Optional DeepSeek model override.")
    parser.add_argument("--resume", action="store_true", help="Skip ticker/date rows already in output.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional seconds to sleep after each row.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features = extract_llm_features(
        input_path=args.input,
        output_path=args.output,
        limit=args.limit,
        mock=args.mock,
        model=args.model,
        resume=args.resume,
        sleep_seconds=args.sleep,
    )
    mode = "mock" if args.mock else "deepseek"
    print(f"Wrote {len(features)} {mode} LLM feature rows to {args.output}")


if __name__ == "__main__":
    main()
