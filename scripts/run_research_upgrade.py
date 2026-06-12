from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.analysis.comparison import summarize_annual_stability
from src.analysis.monte_carlo import compare_to_random_distribution, run_random_baseline_trials
from src.analysis.plots import plot_multi_cumulative_returns, plot_random_baseline_distribution
from src.backtest.cross_sectional import calculate_information_coefficients, run_long_short_backtest
from src.backtest.metrics import summarize_performance
from src.data.metadata import load_ticker_metadata
from src.data.texts import load_text_dataset
from src.features.neutralization import neutralize_signal, summarize_neutralization
from src.features.text_signals import build_point_in_time_text_signal_matrix, score_text_records
from src.pipeline import DEFAULT_TEXT_DATA_PATH, _prepare_price_data


def run_strategy(signal: pd.DataFrame, forward_returns: pd.DataFrame) -> dict[str, pd.DataFrame | pd.Series]:
    portfolio_returns = run_long_short_backtest(signal, forward_returns)
    ic = calculate_information_coefficients(signal, forward_returns)
    metrics = summarize_performance(portfolio_returns["long_short_return"], ic=ic)
    metrics["final_cumulative_return"] = float((1.0 + portfolio_returns["long_short_return"]).prod() - 1.0)
    return {
        "signal": signal,
        "portfolio_returns": portfolio_returns,
        "ic": ic,
        "metrics": metrics,
        "annual_stability": summarize_annual_stability(portfolio_returns, ic),
    }


def write_report(
    output_path: Path,
    coverage: pd.Series,
    strategy_metrics: pd.DataFrame,
    monte_carlo_significance: pd.DataFrame,
    neutralization_summary: pd.Series,
    n_trials: int,
) -> None:
    before = strategy_metrics.loc["before_text_signal"]
    after = strategy_metrics.loc["enhanced_sector_size_neutral"]
    sharpe_percentile = monte_carlo_significance.loc["sharpe_ratio", "strategy_percentile"]
    ic_percentile = monte_carlo_significance.loc["mean_ic", "strategy_percentile"]

    report = f"""# Robustness Upgrade Results

## Data Coverage

- SEC filing records: {int(coverage["records"])}
- Tickers with extracted text: {int(coverage["tickers"])}
- Filing date range: {coverage["filing_min"]} to {coverage["filing_max"]}
- Backtest months: {int(coverage["months"])}
- Average monthly stock count: {coverage["avg_n_stocks"]:.1f}

## Before vs After

| strategy | annualized return | Sharpe | max drawdown | mean IC | mean rank IC | final cumulative return |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| before text signal | {before["annualized_return"]:.2%} | {before["sharpe_ratio"]:.2f} | {before["max_drawdown"]:.2%} | {before["mean_ic"]:.3f} | {before["mean_rank_ic"]:.3f} | {before["final_cumulative_return"]:.2%} |
| enhanced sector/size neutral | {after["annualized_return"]:.2%} | {after["sharpe_ratio"]:.2f} | {after["max_drawdown"]:.2%} | {after["mean_ic"]:.3f} | {after["mean_rank_ic"]:.3f} | {after["final_cumulative_return"]:.2%} |

## Monte Carlo Random Baseline

- Trials: {n_trials}
- Target strategy: enhanced text signal after sector/size neutralization.
- Sharpe percentile vs random no-text trials: {sharpe_percentile:.1%}
- Mean IC percentile vs random no-text trials: {ic_percentile:.1%}

See `robustness_monte_carlo_significance.csv` and `random_baseline_trials.csv` for the full distribution.

## Neutralization Check

```
{neutralization_summary.round(4).to_string()}
```

## Charts

![Robust cumulative returns](robustness_cumulative_returns.png)

![Random Sharpe distribution](random_baseline_sharpe_distribution.png)

## Caveats

- Sector and size metadata are current static yfinance metadata, not point-in-time metadata.
- The improved text signal is still deterministic lexicon scoring, not an LLM or fine-tuned NLP model.
- SEC Item 1A extraction coverage is broader than before, but not perfect across all tickers and years.
- No transaction costs, sector-neutral portfolio construction, or beta neutrality are included yet.
"""
    output_path.write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run robustness upgrade research.")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2026-01-01")
    parser.add_argument("--text-data", default=str(DEFAULT_TEXT_DATA_PATH))
    parser.add_argument("--metadata", default="data/raw/ticker_metadata.csv")
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--n-trials", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    text_records = load_text_dataset(args.text_data)
    text_features = score_text_records(text_records)
    tickers = tuple(sorted(text_records["ticker"].unique()))
    metadata = load_ticker_metadata(args.metadata)
    price_data = _prepare_price_data(tickers=tickers, start=args.start, end=args.end, synthetic=False)
    forward_returns = price_data["forward_returns"]

    before_signal = build_point_in_time_text_signal_matrix(
        text_features,
        monthly_index=forward_returns.index,
        tickers=forward_returns.columns,
        signal_column="text_signal",
    )
    enhanced_signal = build_point_in_time_text_signal_matrix(
        text_features,
        monthly_index=forward_returns.index,
        tickers=forward_returns.columns,
        signal_column="enhanced_text_signal",
    )
    enhanced_neutral_signal = neutralize_signal(enhanced_signal, metadata)

    text_features.drop(columns=["text"], errors="ignore").to_csv(
        output_dir / "enhanced_text_features.csv",
        index=False,
    )
    before_signal.to_csv(output_dir / "before_text_signal.csv")
    enhanced_signal.to_csv(output_dir / "enhanced_text_signal.csv")
    enhanced_neutral_signal.to_csv(output_dir / "enhanced_sector_size_neutral_signal.csv")

    strategies = {
        "before_text_signal": run_strategy(before_signal, forward_returns),
        "enhanced_text_signal": run_strategy(enhanced_signal, forward_returns),
        "enhanced_sector_size_neutral": run_strategy(enhanced_neutral_signal, forward_returns),
    }

    strategy_metrics = pd.DataFrame({name: result["metrics"] for name, result in strategies.items()}).T
    strategy_metrics.to_csv(output_dir / "robustness_strategy_metrics.csv")

    for name, result in strategies.items():
        result["portfolio_returns"].to_csv(output_dir / f"{name}_portfolio_returns.csv")
        result["ic"].to_csv(output_dir / f"{name}_ic.csv")
        result["annual_stability"].to_csv(output_dir / f"{name}_annual_stability.csv")

    neutralization_summary = summarize_neutralization(enhanced_signal, enhanced_neutral_signal, metadata)
    neutralization_summary.to_frame("value").to_csv(output_dir / "neutralization_summary.csv")

    random_trials = run_random_baseline_trials(
        target_signal=enhanced_neutral_signal,
        forward_returns=forward_returns,
        n_trials=args.n_trials,
        metadata=metadata,
        neutralize_random=True,
    )
    random_trials.to_csv(output_dir / "random_baseline_trials.csv")

    monte_carlo_significance = compare_to_random_distribution(
        strategies["enhanced_sector_size_neutral"]["metrics"],
        random_trials,
    )
    monte_carlo_significance.to_csv(output_dir / "robustness_monte_carlo_significance.csv")

    plot_multi_cumulative_returns(
        {
            "before_text_signal": strategies["before_text_signal"]["portfolio_returns"],
            "enhanced_text_signal": strategies["enhanced_text_signal"]["portfolio_returns"],
            "enhanced_sector_size_neutral": strategies["enhanced_sector_size_neutral"]["portfolio_returns"],
        },
        output_path=output_dir / "robustness_cumulative_returns.png",
        csv_output_path=output_dir / "robustness_cumulative_returns.csv",
    )
    plot_random_baseline_distribution(
        random_trials,
        strategies["enhanced_sector_size_neutral"]["metrics"],
        output_path=output_dir / "random_baseline_sharpe_distribution.png",
        metric="sharpe_ratio",
    )

    coverage = pd.Series(
        {
            "records": len(text_records),
            "tickers": text_records["ticker"].nunique(),
            "filing_min": text_records["filing_date"].min(),
            "filing_max": text_records["filing_date"].max(),
            "months": len(strategies["enhanced_sector_size_neutral"]["portfolio_returns"]),
            "avg_n_stocks": strategies["enhanced_sector_size_neutral"]["portfolio_returns"]["n_stocks"].mean(),
        }
    )
    coverage.to_frame("value").to_csv(output_dir / "robustness_coverage.csv")

    write_report(
        output_path=output_dir / "robustness_upgrade_report.md",
        coverage=coverage,
        strategy_metrics=strategy_metrics,
        monte_carlo_significance=monte_carlo_significance,
        neutralization_summary=neutralization_summary,
        n_trials=args.n_trials,
    )

    print("Robustness upgrade complete")
    print(strategy_metrics[["annualized_return", "sharpe_ratio", "max_drawdown", "mean_ic", "mean_rank_ic", "final_cumulative_return"]].round(4).to_string())
    print()
    print(monte_carlo_significance.round(4).to_string())


if __name__ == "__main__":
    main()
