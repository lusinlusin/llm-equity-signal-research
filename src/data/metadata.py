from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_METADATA_COLUMNS = {"ticker", "sector", "market_cap"}


def fetch_ticker_metadata(tickers: Sequence[str]) -> pd.DataFrame:
    """Fetch current ticker metadata from yfinance."""
    import yfinance as yf

    rows = []
    for ticker in tickers:
        normalized_ticker = str(ticker).upper().strip()
        info = yf.Ticker(normalized_ticker).get_info()
        rows.append(
            {
                "ticker": normalized_ticker,
                "sector": info.get("sector") or "Unknown",
                "industry": info.get("industry") or "Unknown",
                "market_cap": info.get("marketCap"),
                "short_name": info.get("shortName") or "",
            }
        )
    return pd.DataFrame(rows)


def save_ticker_metadata(output_path: str | Path, tickers: Sequence[str]) -> pd.DataFrame:
    """Fetch ticker metadata and save it to CSV."""
    metadata = fetch_ticker_metadata(tickers)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata.to_csv(output, index=False)
    return metadata


def load_ticker_metadata(path: str | Path) -> pd.DataFrame:
    """Load static ticker metadata used for sector and size controls."""
    metadata_path = Path(path)
    if not metadata_path.exists():
        raise FileNotFoundError(f"Ticker metadata not found: {metadata_path}")

    metadata = pd.read_csv(metadata_path)
    missing_columns = REQUIRED_METADATA_COLUMNS.difference(metadata.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Ticker metadata is missing required columns: {missing}")

    metadata = metadata.copy()
    metadata["ticker"] = metadata["ticker"].astype(str).str.upper().str.strip()
    metadata["sector"] = metadata["sector"].fillna("Unknown").astype(str).str.strip()
    metadata["market_cap"] = pd.to_numeric(metadata["market_cap"], errors="coerce")
    metadata["log_market_cap"] = np.log(metadata["market_cap"].where(metadata["market_cap"] > 0))
    return metadata.drop_duplicates("ticker").set_index("ticker")
