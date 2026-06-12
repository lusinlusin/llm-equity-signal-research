from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.data.metadata import save_ticker_metadata
from src.data.prices import DEFAULT_TICKERS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download current ticker metadata from yfinance.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=list(DEFAULT_TICKERS),
        help="Tickers to fetch.",
    )
    parser.add_argument(
        "--output",
        default="data/raw/ticker_metadata.csv",
        help="Output CSV path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = save_ticker_metadata(args.output, args.tickers)
    print(f"Saved {len(metadata)} ticker metadata rows to {args.output}")
    print(metadata.groupby("sector")["ticker"].count().sort_values(ascending=False).to_string())


if __name__ == "__main__":
    main()
