from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.analysis.comparison import compare_strategy_summaries, summarize_annual_stability
from src.analysis.monte_carlo import compare_to_random_distribution, run_random_baseline_trials
from src.analysis.plots import plot_multi_cumulative_returns
from src.data.metadata import load_ticker_metadata
from src.data.prices import DEFAULT_TICKERS
from src.data.texts import load_text_dataset
from src.features.neutralization import neutralize_signal
from src.features.placeholder import make_random_signal
from src.features.text_signals import build_point_in_time_text_signal_matrix, score_text_records
from src.pipeline import DEFAULT_TEXT_DATA_PATH, _prepare_price_data, _run_backtest_for_signal


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = PROJECT_ROOT / "data/raw/ticker_metadata.csv"
DEFAULT_ABSOLUTE_LLM_FEATURES = PROJECT_ROOT / "data/processed/llm_text_features_deepseek.csv"
DEFAULT_YOY_LLM_FEATURES = PROJECT_ROOT / "data/processed/llm_yoy_relative_features_deepseek.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports"


def _format_pct(value: float) -> str:
    if pd.isna(value):
        return "nan"
    return f"{value:.2%}"


def _final_cumulative_return(portfolio_returns: pd.DataFrame) -> float:
    return float((1.0 + portfolio_returns["long_short_return"]).prod() - 1.0)


def _common_signal_coverage(signals: dict[str, pd.DataFrame], forward_returns: pd.DataFrame) -> dict[str, pd.DataFrame]:
    common_index = forward_returns.index
    common_columns = forward_returns.columns
    for signal in signals.values():
        common_index = common_index.intersection(signal.index)
        common_columns = common_columns.intersection(signal.columns)

    aligned = {
        name: signal.reindex(index=common_index, columns=common_columns)
        for name, signal in signals.items()
    }
    common_mask = None
    for signal in aligned.values():
        common_mask = signal.notna() if common_mask is None else common_mask & signal.notna()

    covered = {
        name: signal.where(common_mask).dropna(axis=0, how="all").dropna(axis=1, how="all")
        for name, signal in aligned.items()
    }
    final_index = next(iter(covered.values())).index
    final_columns = next(iter(covered.values())).columns
    return {
        name: signal.reindex(index=final_index, columns=final_columns)
        for name, signal in covered.items()
    }


def _write_report(
    metrics: pd.DataFrame,
    coverage: pd.Series,
    significance: pd.DataFrame,
    output_path: Path,
    cumulative_png: Path,
) -> None:
    display = metrics[
        [
            "annualized_return",
            "sharpe_ratio",
            "max_drawdown",
            "mean_ic",
            "mean_rank_ic",
            "final_cumulative_return",
            "n_periods",
        ]
    ].copy()
    for column in (
        "annualized_return",
        "max_drawdown",
        "mean_ic",
        "mean_rank_ic",
        "final_cumulative_return",
    ):
        display[column] = display[column].map(_format_pct)
    display["sharpe_ratio"] = display["sharpe_ratio"].map(lambda value: f"{value:.2f}")
    display["n_periods"] = display["n_periods"].astype(int)

    sig_display = significance[
        ["strategy_value", "random_mean", "random_p50", "random_p95", "strategy_percentile"]
    ].copy()
    for column in ("strategy_value", "random_mean", "random_p50", "random_p95", "strategy_percentile"):
        sig_display[column] = sig_display[column].map(_format_pct)

    lines = [
        "# YoY Relative DeepSeek Signal: All-Signal Comparison",
        "",
        "The YoY relative signal is first built on the old 72-month / 42-ticker signal universe. "
        "The strategy table uses the strict common date/ticker coverage where every listed signal is available.",
        "",
        "## Coverage",
        "",
        coverage.to_frame("value").to_markdown(),
        "",
        "## Metrics",
        "",
        display.to_markdown(),
        "",
        "## YoY Relative Signal vs 500 Random No-Text Trials",
        "",
        sig_display.to_markdown(),
        "",
        f"Cumulative return plot: `{cumulative_png.name}`",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_yoy_relative_all_signal_comparison(
    yoy_features_path: str | Path = DEFAULT_YOY_LLM_FEATURES,
    absolute_llm_features_path: str | Path = DEFAULT_ABSOLUTE_LLM_FEATURES,
    text_data_path: str | Path = DEFAULT_TEXT_DATA_PATH,
    metadata_path: str | Path = DEFAULT_METADATA,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    start: str = "2020-01-01",
    end: str | None = "2026-01-01",
    seed: int = 42,
    n_trials: int = 500,
    synthetic: bool = False,
) -> dict[str, pd.DataFrame | pd.Series]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    price_results = _prepare_price_data(
        tickers=DEFAULT_TICKERS,
        start=start,
        end=end,
        synthetic=synthetic,
    )
    forward_returns = price_results["forward_returns"]

    text_features = score_text_records(load_text_dataset(text_data_path))
    absolute_llm_features = load_text_dataset(absolute_llm_features_path)
    yoy_features = load_text_dataset(yoy_features_path)
    metadata = load_ticker_metadata(metadata_path)

    before_text_signal = build_point_in_time_text_signal_matrix(
        text_features,
        monthly_index=forward_returns.index,
        tickers=forward_returns.columns,
        signal_column="text_signal",
    )
    enhanced_text_signal = build_point_in_time_text_signal_matrix(
        text_features,
        monthly_index=forward_returns.index,
        tickers=forward_returns.columns,
        signal_column="enhanced_text_signal",
    )
    enhanced_sector_size_neutral = neutralize_signal(enhanced_text_signal, metadata)
    absolute_llm_signal = build_point_in_time_text_signal_matrix(
        absolute_llm_features,
        monthly_index=forward_returns.index,
        tickers=forward_returns.columns,
        signal_column="llm_text_signal",
    )
    yoy_relative_signal = build_point_in_time_text_signal_matrix(
        yoy_features,
        monthly_index=forward_returns.index,
        tickers=forward_returns.columns,
        signal_column="llm_yoy_relative_signal",
    )

    yoy_available_signal = (
        yoy_relative_signal.dropna(axis=0, how="all").dropna(axis=1, how="all")
    )

    signals = _common_signal_coverage(
        {
            "before_text_signal": before_text_signal,
            "enhanced_text_signal": enhanced_text_signal,
            "enhanced_sector_size_neutral": enhanced_sector_size_neutral,
            "deepseek_absolute_llm_text_signal": absolute_llm_signal,
            "deepseek_yoy_relative_signal": yoy_relative_signal,
        },
        forward_returns,
    )
    random_signal = make_random_signal(
        index=next(iter(signals.values())).index,
        columns=next(iter(signals.values())).columns,
        seed=seed,
    ).where(next(iter(signals.values())).notna())
    signals["random_no_text"] = random_signal

    strategy_results = {
        name: _run_backtest_for_signal(signal, forward_returns)
        for name, signal in signals.items()
    }
    metrics = compare_strategy_summaries(strategy_results)
    for name, result in strategy_results.items():
        metrics.loc[name, "final_cumulative_return"] = _final_cumulative_return(result["portfolio_returns"])

    portfolio_returns = {
        name: result["portfolio_returns"] for name, result in strategy_results.items()
    }
    cumulative = plot_multi_cumulative_returns(
        portfolio_returns,
        output / "llm_yoy_relative_all_signals_cumulative_returns.png",
        csv_output_path=output / "llm_yoy_relative_all_signals_cumulative_returns.csv",
    )

    coverage_signal = signals["deepseek_yoy_relative_signal"]
    coverage = pd.Series(
        {
            "yoy_feature_rows": int(yoy_features.shape[0]),
            "yoy_feature_tickers": int(yoy_features["ticker"].nunique()),
            "yoy_signal_months_before_all_signal_filter": int(yoy_available_signal.shape[0]),
            "yoy_signal_tickers_before_all_signal_filter": int(yoy_available_signal.shape[1]),
            "common_signal_months": int(coverage_signal.shape[0]),
            "common_signal_tickers": int(coverage_signal.shape[1]),
            "backtest_periods": int(metrics.loc["deepseek_yoy_relative_signal", "n_periods"]),
            "random_trials": int(n_trials),
        }
    )

    random_trials = run_random_baseline_trials(
        target_signal=signals["deepseek_yoy_relative_signal"],
        forward_returns=forward_returns,
        n_trials=n_trials,
        seed_start=20_000,
    )
    yoy_metrics = metrics.loc["deepseek_yoy_relative_signal"].copy()
    significance = compare_to_random_distribution(yoy_metrics, random_trials)

    metrics.to_csv(output / "llm_yoy_relative_all_signals_metrics.csv")
    coverage.to_frame("value").to_csv(output / "llm_yoy_relative_all_signals_coverage.csv")
    random_trials.to_csv(output / "llm_yoy_relative_random_baseline_trials.csv")
    significance.to_csv(output / "llm_yoy_relative_random_significance.csv")
    for name, signal in signals.items():
        signal.to_csv(output / f"llm_yoy_relative_{name}.csv")
        strategy_results[name]["portfolio_returns"].to_csv(
            output / f"llm_yoy_relative_{name}_portfolio_returns.csv"
        )
        strategy_results[name]["ic"].to_csv(output / f"llm_yoy_relative_{name}_ic.csv")
        summarize_annual_stability(
            strategy_results[name]["portfolio_returns"],
            strategy_results[name]["ic"],
        ).to_csv(output / f"llm_yoy_relative_{name}_annual_stability.csv")

    _write_report(
        metrics=metrics,
        coverage=coverage,
        significance=significance,
        output_path=output / "llm_yoy_relative_all_signals_comparison.md",
        cumulative_png=output / "llm_yoy_relative_all_signals_cumulative_returns.png",
    )

    return {
        "metrics": metrics,
        "coverage": coverage,
        "significance": significance,
        "cumulative": cumulative,
        **strategy_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare YoY relative DeepSeek signal against all baselines.")
    parser.add_argument("--yoy-features", default=str(DEFAULT_YOY_LLM_FEATURES), help="CSV with llm_yoy_relative_signal.")
    parser.add_argument("--absolute-llm-features", default=str(DEFAULT_ABSOLUTE_LLM_FEATURES), help="CSV with old llm_text_signal.")
    parser.add_argument("--text-data", default=str(DEFAULT_TEXT_DATA_PATH), help="Raw text CSV for dictionary signals.")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA), help="Ticker metadata CSV.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for comparison artifacts.")
    parser.add_argument("--start", default="2020-01-01", help="Start date for prices.")
    parser.add_argument("--end", default="2026-01-01", help="Optional end date for prices.")
    parser.add_argument("--seed", type=int, default=42, help="Single random baseline seed.")
    parser.add_argument("--n-trials", type=int, default=500, help="Monte Carlo random baseline trials.")
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic prices for offline checks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_yoy_relative_all_signal_comparison(
        yoy_features_path=args.yoy_features,
        absolute_llm_features_path=args.absolute_llm_features,
        text_data_path=args.text_data,
        metadata_path=args.metadata,
        output_dir=args.output_dir,
        start=args.start,
        end=args.end,
        seed=args.seed,
        n_trials=args.n_trials,
        synthetic=args.synthetic,
    )
    print("YoY relative all-signal comparison complete")
    print(results["coverage"].to_string())
    print(results["metrics"].round(4).to_string())
    print(results["significance"].round(4).to_string())


if __name__ == "__main__":
    main()
