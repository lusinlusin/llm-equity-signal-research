from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.analysis.comparison import compare_strategy_summaries, summarize_annual_stability
from src.backtest.cross_sectional import (
    calculate_information_coefficients,
    run_long_short_backtest,
)
from src.backtest.metrics import summarize_performance
from src.data.prices import (
    DEFAULT_TICKERS,
    compute_monthly_returns,
    compute_forward_returns,
    download_adjusted_close,
    make_synthetic_prices,
    to_monthly_prices,
)
from src.data.texts import load_text_dataset
from src.features.placeholder import make_random_signal
from src.features.text_signals import build_point_in_time_text_signal_matrix, score_text_records


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEXT_DATA_PATH = PROJECT_ROOT / "data/raw/sec_10k_risk_factors.csv"


def _prepare_price_data(
    tickers: tuple[str, ...],
    start: str,
    end: str | None,
    synthetic: bool,
) -> dict[str, pd.DataFrame]:
    if synthetic:
        prices = make_synthetic_prices(tickers=tickers, start=start)
    else:
        prices = download_adjusted_close(tickers=tickers, start=start, end=end)

    monthly_prices = to_monthly_prices(prices)
    monthly_returns = compute_monthly_returns(monthly_prices)
    forward_returns = compute_forward_returns(monthly_prices)
    return {
        "prices": prices,
        "monthly_prices": monthly_prices,
        "monthly_returns": monthly_returns,
        "forward_returns": forward_returns,
    }


def _run_backtest_for_signal(
    signal: pd.DataFrame,
    forward_returns: pd.DataFrame,
) -> dict[str, pd.DataFrame | pd.Series]:
    portfolio_returns = run_long_short_backtest(signal, forward_returns)
    if portfolio_returns.empty:
        raise ValueError(
            "Backtest produced no returns. Check that signal dates and tickers overlap with price data."
        )

    ic = calculate_information_coefficients(signal, forward_returns)
    metrics = summarize_performance(portfolio_returns["long_short_return"], ic=ic)
    return {
        "signal": signal,
        "portfolio_returns": portfolio_returns,
        "ic": ic,
        "metrics": metrics,
    }


def run_pipeline(
    tickers: tuple[str, ...] = DEFAULT_TICKERS,
    start: str = "2018-01-01",
    end: str | None = None,
    signal_seed: int = 42,
    synthetic: bool = False,
    signal_source: str = "text",
    text_data_path: str | Path = DEFAULT_TEXT_DATA_PATH,
    text_signal_column: str = "text_signal",
) -> dict[str, pd.DataFrame | pd.Series]:
    """Run prices through a text-derived or placeholder-signal backtest."""
    results: dict[str, pd.DataFrame | pd.Series] = _prepare_price_data(
        tickers=tickers,
        start=start,
        end=end,
        synthetic=synthetic,
    )
    forward_returns = results["forward_returns"]

    if signal_source == "random":
        signal = make_random_signal(
            index=forward_returns.index,
            columns=forward_returns.columns,
            seed=signal_seed,
        )
    elif signal_source == "text":
        text_records = load_text_dataset(text_data_path)
        text_features = score_text_records(text_records)
        signal = build_point_in_time_text_signal_matrix(
            text_features,
            monthly_index=forward_returns.index,
            tickers=forward_returns.columns,
            signal_column=text_signal_column,
        )
        results["text_records"] = text_records
        results["text_features"] = text_features
    else:
        raise ValueError("signal_source must be 'text' or 'random'")

    results.update(_run_backtest_for_signal(signal, forward_returns))
    return results


def run_signal_comparison(
    tickers: tuple[str, ...] = DEFAULT_TICKERS,
    start: str = "2018-01-01",
    end: str | None = None,
    signal_seed: int = 42,
    synthetic: bool = False,
    text_data_path: str | Path = DEFAULT_TEXT_DATA_PATH,
    text_signal_column: str = "text_signal",
) -> dict[str, pd.DataFrame | pd.Series]:
    """Compare text signal against a random no-text baseline on identical coverage."""
    results: dict[str, pd.DataFrame | pd.Series] = _prepare_price_data(
        tickers=tickers,
        start=start,
        end=end,
        synthetic=synthetic,
    )
    forward_returns = results["forward_returns"]

    text_records = load_text_dataset(text_data_path)
    text_features = score_text_records(text_records)
    text_signal = build_point_in_time_text_signal_matrix(
        text_features,
        monthly_index=forward_returns.index,
        tickers=forward_returns.columns,
        signal_column=text_signal_column,
    )
    random_no_text_signal = make_random_signal(
        index=text_signal.index,
        columns=text_signal.columns,
        seed=signal_seed,
    ).where(text_signal.notna())

    text_results = _run_backtest_for_signal(text_signal, forward_returns)
    random_results = _run_backtest_for_signal(random_no_text_signal, forward_returns)
    comparison_metrics = compare_strategy_summaries(
        {
            "text_signal": text_results,
            "random_no_text": random_results,
        }
    )

    results["text_records"] = text_records
    results["text_features"] = text_features
    results["text_signal"] = text_signal
    results["random_no_text_signal"] = random_no_text_signal
    results["text_portfolio_returns"] = text_results["portfolio_returns"]
    results["random_no_text_portfolio_returns"] = random_results["portfolio_returns"]
    results["text_ic"] = text_results["ic"]
    results["random_no_text_ic"] = random_results["ic"]
    results["comparison_metrics"] = comparison_metrics
    results["text_annual_stability"] = summarize_annual_stability(
        text_results["portfolio_returns"],
        text_results["ic"],
    )
    results["random_no_text_annual_stability"] = summarize_annual_stability(
        random_results["portfolio_returns"],
        random_results["ic"],
    )
    return results


def save_outputs(results: dict[str, pd.DataFrame | pd.Series], output_dir: Path) -> None:
    """Write core first-milestone outputs to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    output_names = (
        "monthly_prices",
        "monthly_returns",
        "forward_returns",
        "text_records",
        "text_features",
        "signal",
        "portfolio_returns",
        "ic",
        "text_signal",
        "random_no_text_signal",
        "text_portfolio_returns",
        "random_no_text_portfolio_returns",
        "text_ic",
        "random_no_text_ic",
        "comparison_metrics",
        "text_annual_stability",
        "random_no_text_annual_stability",
    )
    for name in output_names:
        value = results.get(name)
        if isinstance(value, pd.DataFrame):
            value.to_csv(output_dir / f"{name}.csv")

    metrics = results.get("metrics")
    if isinstance(metrics, pd.Series):
        metrics.to_frame("value").to_csv(output_dir / "metrics.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the equity signal backtest pipeline.")
    parser.add_argument("--start", default="2018-01-01", help="Start date for prices.")
    parser.add_argument("--end", default=None, help="Optional end date for prices.")
    parser.add_argument("--seed", type=int, default=42, help="Random signal seed.")
    parser.add_argument(
        "--signal-source",
        choices=("text", "random"),
        default="text",
        help="Use structured text-derived signals or a random placeholder baseline.",
    )
    parser.add_argument(
        "--text-data",
        default=str(DEFAULT_TEXT_DATA_PATH),
        help="CSV file containing date, ticker, and text columns.",
    )
    parser.add_argument(
        "--text-signal-column",
        default="text_signal",
        help="Scored text feature to use as the backtest signal.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare text signal against a random no-text baseline on identical coverage.",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Use deterministic synthetic prices instead of yfinance.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory for CSV outputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.compare:
        results = run_signal_comparison(
            start=args.start,
            end=args.end,
            signal_seed=args.seed,
            synthetic=args.synthetic,
            text_data_path=args.text_data,
            text_signal_column=args.text_signal_column,
        )
    else:
        results = run_pipeline(
            start=args.start,
            end=args.end,
            signal_seed=args.seed,
            synthetic=args.synthetic,
            signal_source=args.signal_source,
            text_data_path=args.text_data,
            text_signal_column=args.text_signal_column,
        )
    save_outputs(results, Path(args.output_dir))

    if args.compare:
        print("Comparison complete: text signal vs random no-text baseline")
        print(results["comparison_metrics"].round(4).to_string())
    else:
        print(f"Pipeline complete: price data -> {args.signal_source} signal -> backtest -> metrics")
        print(results["metrics"].round(4).to_string())


if __name__ == "__main__":
    main()
