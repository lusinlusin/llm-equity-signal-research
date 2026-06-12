from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.analysis.plots import plot_cumulative_return_comparison


def read_portfolio_returns(path: str | Path) -> pd.DataFrame:
    returns = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    if "long_short_return" not in returns.columns:
        raise ValueError(f"Missing long_short_return column: {path}")
    return returns


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot cumulative long-short return comparison.")
    parser.add_argument(
        "--input-dir",
        default="data/processed",
        help="Directory containing strategy portfolio return CSV files.",
    )
    parser.add_argument(
        "--output",
        default="reports/cumulative_return_comparison.png",
        help="Output PNG path.",
    )
    parser.add_argument(
        "--csv-output",
        default="reports/cumulative_return_comparison.csv",
        help="Output cumulative return CSV path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    text_returns = read_portfolio_returns(input_dir / "text_portfolio_returns.csv")
    random_returns = read_portfolio_returns(input_dir / "random_no_text_portfolio_returns.csv")

    cumulative = plot_cumulative_return_comparison(
        text_portfolio_returns=text_returns,
        random_portfolio_returns=random_returns,
        output_path=args.output,
        csv_output_path=args.csv_output,
    )
    print(f"Saved cumulative return chart to {args.output}")
    print(f"Saved cumulative return data to {args.csv_output}")
    print(cumulative.tail().round(4).to_string())


if __name__ == "__main__":
    main()
