from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.data.sec_filings import DEFAULT_SEC_TICKERS, save_sec_10k_risk_factors
from src.data.sec_filings import DEFAULT_USER_AGENT, download_prior_context_records


def print_ticker_summary(records, date_column: str = "filing_date") -> None:
    if records.empty:
        return
    print(
        records.groupby("ticker")[date_column]
        .agg(["min", "max", "count"])
        .sort_index()
        .to_string()
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download SEC 10-K Item 1A Risk Factors text.")
    parser.add_argument(
        "--mode",
        choices=("current", "prior", "both"),
        default="current",
        help="Download current filings, prior context filings, or both.",
    )
    parser.add_argument(
        "--output",
        default="data/raw/sec_10k_risk_factors.csv",
        help="Output CSV path for current filings.",
    )
    parser.add_argument(
        "--prior-input",
        default=None,
        help="Current SEC filing CSV used to identify prior-context windows. Defaults to --output.",
    )
    parser.add_argument(
        "--prior-output",
        default="data/raw/sec_10k_risk_factors_prior_context.csv",
        help="Output CSV path for prior context records.",
    )
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--years-back", type=int, default=2, help="Lookback window for prior context mode.")
    parser.add_argument(
        "--max-prior-per-ticker",
        type=int,
        default=2,
        help="Maximum prior 10-K records to save per ticker.",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Optional ticker universe. Current mode defaults to DEFAULT_SEC_TICKERS; prior mode defaults to all tickers in --prior-input.",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="SEC requires a descriptive User-Agent with contact information.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode in {"current", "both"}:
        current_tickers = tuple(args.tickers) if args.tickers else DEFAULT_SEC_TICKERS
        records = save_sec_10k_risk_factors(
            output_path=args.output,
            tickers=current_tickers,
            start_year=args.start_year,
            end_year=args.end_year,
            user_agent=args.user_agent,
        )
        print(f"Saved {len(records)} current SEC 10-K Item 1A records to {args.output}")
        print_ticker_summary(records)

    if args.mode in {"prior", "both"}:
        prior_input = args.prior_input or args.output
        records = download_prior_context_records(
            input_path=prior_input,
            output_path=args.prior_output,
            years_back=args.years_back,
            max_prior_per_ticker=args.max_prior_per_ticker,
            tickers=args.tickers,
            user_agent=args.user_agent,
        )
        print(f"Saved {len(records)} prior SEC 10-K Item 1A records to {args.prior_output}")
        print_ticker_summary(records)


if __name__ == "__main__":
    main()
