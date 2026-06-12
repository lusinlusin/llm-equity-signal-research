from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_TEXT_COLUMNS = {"date", "ticker", "text"}


def load_text_dataset(path: str | Path) -> pd.DataFrame:
    """Load company text records and align each record to its month-end signal date."""
    text_path = Path(path)
    if not text_path.exists():
        raise FileNotFoundError(f"Text dataset not found: {text_path}")

    records = pd.read_csv(text_path)
    missing_columns = REQUIRED_TEXT_COLUMNS.difference(records.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Text dataset is missing required columns: {missing}")

    records = records.copy()
    records["date"] = pd.to_datetime(records["date"])
    records["signal_date"] = records["date"] + pd.offsets.MonthEnd(0)
    records["ticker"] = records["ticker"].astype(str).str.upper().str.strip()
    records["text"] = records["text"].fillna("").astype(str).str.strip()

    if "source_type" not in records.columns:
        records["source_type"] = "unknown"

    records = records.loc[records["text"] != ""]
    return records.sort_values(["signal_date", "ticker"]).reset_index(drop=True)
