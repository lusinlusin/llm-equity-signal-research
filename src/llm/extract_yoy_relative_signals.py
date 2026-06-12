from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from src.llm.deepseek_client import DeepSeekConfig
from src.llm.deepseek_yoy_relative_client import DeepSeekYOYRelativeExtractor


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_ROOT / "data/raw/sec_10k_risk_factors.csv"
DEFAULT_METADATA = PROJECT_ROOT / "data/raw/ticker_metadata.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/processed/llm_yoy_relative_features_deepseek.csv"


def _record_keys(records: pd.DataFrame) -> pd.Series:
    return (
        records["ticker"].astype(str).str.upper().str.strip()
        + "|"
        + _date_keys(records["date"])
        + "|"
        + records["accession_number"].astype(str)
    )


def _load_yoy_pairs(
    input_path: str | Path,
    metadata_path: str | Path,
    prior_context_path: str | Path | None = None,
) -> pd.DataFrame:
    records = pd.read_csv(input_path)
    records = records.copy()
    records["ticker"] = records["ticker"].astype(str).str.upper().str.strip()
    records["date"] = pd.to_datetime(records["date"], format="mixed")
    records["_current_record_key"] = _record_keys(records)

    if prior_context_path is not None:
        prior_context = pd.read_csv(prior_context_path)
        prior_context = prior_context.copy()
        prior_context["ticker"] = prior_context["ticker"].astype(str).str.upper().str.strip()
        prior_context["date"] = pd.to_datetime(prior_context["date"], format="mixed")
        prior_context["_current_record_key"] = ""
        lookup_records = pd.concat([prior_context, records], ignore_index=True)
    else:
        lookup_records = records.copy()

    current_keys = set(records["_current_record_key"])
    lookup_records = (
        lookup_records.drop_duplicates(subset=["ticker", "date", "accession_number"], keep="last")
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )

    metadata = pd.read_csv(metadata_path)
    metadata = metadata.copy()
    metadata["ticker"] = metadata["ticker"].astype(str).str.upper().str.strip()
    metadata = metadata.set_index("ticker")

    prior = lookup_records.groupby("ticker").shift(1)
    is_current_record = lookup_records["_current_record_key"].isin(current_keys)
    pairs = lookup_records.loc[is_current_record & prior["text"].notna()].copy()
    prior = prior.loc[prior["text"].notna()].copy()
    prior = prior.loc[pairs.index].copy()

    pairs["prior_date"] = prior["date"].dt.strftime("%Y-%m-%d").values
    pairs["prior_filing_date"] = prior.get("filing_date", prior["date"]).values
    pairs["prior_report_date"] = prior.get("report_date", pd.Series(index=prior.index, dtype=object)).values
    pairs["prior_accession_number"] = prior.get(
        "accession_number",
        pd.Series(index=prior.index, dtype=object),
    ).values
    pairs["prior_document_url"] = prior.get("document_url", pd.Series(index=prior.index, dtype=object)).values
    pairs["prior_text"] = prior["text"].values

    pairs["sector"] = pairs["ticker"].map(metadata["sector"]).fillna("Unknown")
    if "company_name" not in pairs.columns:
        pairs["company_name"] = pairs["ticker"]

    return pairs.drop(columns=["_current_record_key"], errors="ignore").reset_index(drop=True)


def _filter_pairs_by_sample_keys(pairs: pd.DataFrame, sample_keys_path: str | Path) -> pd.DataFrame:
    sample_keys = pd.read_csv(sample_keys_path)
    sample_keys = sample_keys.copy()
    required = {"ticker", "date"}
    missing = required.difference(sample_keys.columns)
    if missing:
        raise ValueError(f"Sample keys file is missing required columns: {', '.join(sorted(missing))}")

    sample_keys["ticker"] = sample_keys["ticker"].astype(str).str.upper().str.strip()
    if "prior_date" in sample_keys.columns:
        wanted = set(
            zip(
                sample_keys["ticker"],
                _date_keys(sample_keys["date"]),
                _date_keys(sample_keys["prior_date"]),
            )
        )
        pair_keys = list(
            zip(
                pairs["ticker"].astype(str).str.upper().str.strip(),
                _date_keys(pairs["date"]),
                _date_keys(pairs["prior_date"]),
            )
        )
    else:
        wanted = set(zip(sample_keys["ticker"], _date_keys(sample_keys["date"])))
        pair_keys = list(
            zip(
                pairs["ticker"].astype(str).str.upper().str.strip(),
                _date_keys(pairs["date"]),
            )
        )

    return pairs[[key in wanted for key in pair_keys]].reset_index(drop=True)


def _date_keys(values: pd.Series) -> pd.Series:
    try:
        dates = pd.to_datetime(values, format="mixed", errors="coerce")
    except TypeError:
        dates = pd.to_datetime(values, errors="coerce")
    if dates.isna().any():
        raise ValueError("Could not parse all date keys for YoY resume matching.")
    return dates.dt.strftime("%Y-%m-%d")


def _format_date_value(value: object) -> object:
    if pd.isna(value):
        return value
    return pd.to_datetime(value).date().isoformat()


def _format_row_dates(row: dict[str, object]) -> dict[str, object]:
    for column in ("date", "filing_date", "report_date", "prior_date", "prior_filing_date", "prior_report_date"):
        if column in row:
            row[column] = _format_date_value(row[column])
    return row


def _prefixed_yoy_fields(
    payload: dict[str, float | str],
    provider: str,
    model: str,
) -> dict[str, float | str]:
    return {
        "yoy_risk_change_score": payload["risk_change_score"],
        "yoy_new_material_risk_score": payload["new_material_risk_score"],
        "yoy_risk_mitigation_score": payload["risk_mitigation_score"],
        "yoy_peer_relative_risk_score": payload["peer_relative_risk_score"],
        "yoy_direction_score": payload["direction_score"],
        "yoy_impact_label": payload["impact_label"],
        "yoy_confidence": payload["confidence"],
        "yoy_rationale": payload["rationale"],
        "llm_yoy_relative_signal": payload["llm_yoy_relative_signal"],
        "llm_provider": provider,
        "llm_model": model,
    }


def extract_yoy_relative_features(
    input_path: str | Path,
    metadata_path: str | Path,
    output_path: str | Path,
    prior_context_path: str | Path | None = None,
    sample_keys_path: str | Path | None = None,
    limit: int | None = None,
    model: str | None = None,
    resume: bool = False,
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
    extractor = DeepSeekYOYRelativeExtractor(config)
    output_model = config.model

    rows = []
    total = len(existing) + len(pairs)
    for row_number, (_, record) in enumerate(pairs.iterrows(), start=len(existing) + 1):
        filing_date = str(record["date"].date())
        prior_date = str(pd.to_datetime(record["prior_date"]).date())
        payload = extractor.extract_signal(
            ticker=record["ticker"],
            company_name=record["company_name"],
            sector=record["sector"],
            current_filing_date=filing_date,
            prior_filing_date=prior_date,
            current_text=record["text"],
            prior_text=record["prior_text"],
        )

        row = _format_row_dates(record.drop(labels=["prior_text"]).to_dict())
        row.update(_prefixed_yoy_fields(payload, provider="deepseek", model=output_model))
        rows.append(row)

        combined = pd.concat([existing, pd.DataFrame(rows)], ignore_index=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(output, index=False)
        print(
            f"Processed {row_number}/{total}: {record['ticker']} {filing_date} vs {prior_date}",
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
    parser = argparse.ArgumentParser(description="Extract YoY relative LLM signals from SEC filings.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input SEC filing text CSV.")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA), help="Ticker metadata CSV.")
    parser.add_argument("--prior-context", default=None, help="Optional prior SEC filing CSV used only for YoY context.")
    parser.add_argument("--sample-keys", default=None, help="Optional CSV with ticker/date/prior_date keys to extract.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output CSV for YoY LLM features.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of current/prior pairs.")
    parser.add_argument("--model", default=None, help="Optional DeepSeek model override.")
    parser.add_argument("--resume", action="store_true", help="Skip ticker/current/prior rows already in output.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional seconds to sleep after each row.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features = extract_yoy_relative_features(
        input_path=args.input,
        metadata_path=args.metadata,
        output_path=args.output,
        prior_context_path=args.prior_context,
        sample_keys_path=args.sample_keys,
        limit=args.limit,
        model=args.model,
        resume=args.resume,
        sleep_seconds=args.sleep,
    )
    print(f"Wrote {len(features)} YoY relative DeepSeek feature rows to {args.output}")


if __name__ == "__main__":
    main()
