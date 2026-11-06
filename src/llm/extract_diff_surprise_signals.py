from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

import pandas as pd

from src.features.risk_section_diff import RiskSectionDiff, diff_risk_sections
from src.llm.deepseek_client import DeepSeekConfig
from src.llm.deepseek_diff_surprise_client import DeepSeekDiffSurpriseExtractor
from src.llm.diff_surprise_schema import validate_diff_surprise_payload
from src.llm.extract_yoy_relative_signals import (
    _date_keys,
    _filter_pairs_by_sample_keys,
    _format_row_dates,
    _load_yoy_pairs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data/raw/sec_10k_risk_factors.csv"
DEFAULT_METADATA = PROJECT_ROOT / "data/raw/ticker_metadata.csv"
DEFAULT_PRIOR_CONTEXT = PROJECT_ROOT / "data/raw/sec_10k_risk_factors_prior_context.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/processed/llm_diff_surprise_features_deepseek.csv"


def _diff_stats(diff: RiskSectionDiff) -> dict[str, float]:
    return {
        "diff_similarity": float(diff.similarity),
        "diff_n_added": float(len(diff.added)),
        "diff_n_removed": float(len(diff.removed)),
        "diff_n_modified": float(len(diff.modified)),
        "diff_added_chars": float(diff.added_chars),
        "diff_removed_chars": float(diff.removed_chars),
        "diff_modified_chars": float(diff.modified_chars),
    }


def _prefixed_diff_fields(
    payload: dict[str, float | str],
    provider: str,
    model: str,
) -> dict[str, float | str]:
    return {
        "diff_material_changes": payload["material_changes"],
        "diff_n_material_changes": payload["n_material_changes"],
        "diff_n_company_specific_changes": payload["n_company_specific_changes"],
        "diff_boilerplate_share": payload["boilerplate_share"],
        "diff_company_specific_positive": payload["company_specific_positive"],
        "diff_company_specific_negative": payload["company_specific_negative"],
        "diff_net_signal": payload["net_signal"],
        "diff_confidence": payload["confidence"],
        "diff_gate_violation": payload["gate_violation"],
        "diff_rationale": payload["rationale"],
        "llm_diff_surprise_signal": payload["llm_diff_surprise_signal"],
        "llm_provider": provider,
        "llm_model": model,
    }


def mock_extract_diff_surprise_signal(diff: RiskSectionDiff) -> dict[str, float | str]:
    """Deterministic diff-shaped payload for local dry-run tests without an API key."""
    novelty = min(10, int(round((1.0 - diff.similarity) * 10)) + len(diff.added) // 4)
    negative = min(10, novelty)
    positive = min(10, len(diff.removed) // 3)
    net = 0
    changes = []
    if novelty >= 6:
        net = -1 if negative >= positive else 1
        changes.append(
            {
                "summary": "Mock material change derived from diff statistics.",
                "scope": "company_specific",
                "direction": "negative" if net < 0 else "positive",
                "materiality": novelty,
            }
        )
    payload = {
        "material_changes": changes,
        "boilerplate_share": round(diff.similarity, 2),
        "company_specific_positive": positive,
        "company_specific_negative": negative,
        "net_signal": net,
        "confidence": 5,
        "rationale": "Mock diff-surprise payload derived from deterministic diff statistics.",
    }
    return validate_diff_surprise_payload(payload)


def extract_diff_surprise_features(
    input_path: str | Path,
    metadata_path: str | Path,
    output_path: str | Path,
    prior_context_path: str | Path | None = None,
    sample_keys_path: str | Path | None = None,
    limit: int | None = None,
    model: str | None = None,
    resume: bool = False,
    mock: bool = False,
    sleep_seconds: float = 0.0,
) -> pd.DataFrame:
    pairs = _load_yoy_pairs(input_path, metadata_path, prior_context_path=prior_context_path)
    if sample_keys_path is not None:
        pairs = _filter_pairs_by_sample_keys(pairs, sample_keys_path)
    if limit is not None:
        pairs = pairs.head(limit)

    output = Path(output_path)
    existing = pd.DataFrame()
    if resume and output.exists():
        existing = pd.read_csv(output)
        done_keys = set(
            zip(
                existing["ticker"].astype(str),
                _date_keys(existing["date"]),
                _date_keys(existing["prior_date"]),
            )
        )
        pair_keys = list(
            zip(
                pairs["ticker"].astype(str),
                _date_keys(pairs["date"]),
                _date_keys(pairs["prior_date"]),
            )
        )
        pairs = pairs[[key not in done_keys for key in pair_keys]]

    config = DeepSeekConfig.from_env(model=model)
    extractor = None if mock else DeepSeekDiffSurpriseExtractor(config)
    output_model = "mock" if mock else (extractor.config.model if extractor else config.model)
    provider = "mock" if mock else "deepseek"

    rows = []
    total = len(existing) + len(pairs)
    for row_number, (_, record) in enumerate(pairs.iterrows(), start=len(existing) + 1):
        filing_date = str(record["date"].date())
        prior_date = str(pd.to_datetime(record["prior_date"]).date())
        diff = diff_risk_sections(str(record["text"]), str(record["prior_text"]))
        if mock:
            payload = mock_extract_diff_surprise_signal(diff)
        else:
            payload = extractor.extract_signal(sector=record["sector"], diff=diff)

        # Drop the full Item 1A text from the feature file: it is huge and unused
        # downstream, and a smaller file makes the per-row checkpoint write fast.
        row = _format_row_dates(record.drop(labels=["prior_text", "text"], errors="ignore").to_dict())
        row.update(_diff_stats(diff))
        row.update(_prefixed_diff_fields(payload, provider=provider, model=output_model))
        rows.append(row)

        combined = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Atomic checkpoint: write to a temp file then rename, so a mid-write kill
        # leaves the previous complete file intact instead of a truncated CSV.
        tmp_output = output.with_suffix(output.suffix + ".tmp")
        combined.to_csv(tmp_output, index=False)
        os.replace(tmp_output, output)
        print(
            f"Processed {row_number}/{total}: {record['ticker']} {filing_date} vs {prior_date} "
            f"(similarity={diff.similarity:.2f}, net_signal={payload['net_signal']:+.0f})",
            flush=True,
        )
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    features = pd.DataFrame(rows)
    if not existing.empty:
        features = pd.concat([existing, features], ignore_index=True)
    elif pairs.empty:
        features = existing
    return features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract diff-based investable-surprise LLM signals.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input SEC filing text CSV.")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA), help="Ticker metadata CSV.")
    parser.add_argument("--prior-context", default=str(DEFAULT_PRIOR_CONTEXT), help="Prior SEC filing CSV used only for YoY context.")
    parser.add_argument("--sample-keys", default=None, help="Optional CSV with ticker/date/prior_date keys to extract.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV for diff-surprise LLM features.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of current/prior pairs.")
    parser.add_argument("--model", default=None, help="Optional DeepSeek model override.")
    parser.add_argument("--resume", action="store_true", help="Skip ticker/current/prior rows already in output.")
    parser.add_argument("--mock", action="store_true", help="Use the deterministic mock payload instead of the API.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional seconds to sleep after each row.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features = extract_diff_surprise_features(
        input_path=args.input,
        metadata_path=args.metadata,
        output_path=args.output,
        prior_context_path=args.prior_context,
        sample_keys_path=args.sample_keys,
        limit=args.limit,
        model=args.model,
        resume=args.resume,
        mock=args.mock,
        sleep_seconds=args.sleep,
    )
    print(f"Wrote {len(features)} diff-surprise feature rows to {args.output}")


if __name__ == "__main__":
    main()
