from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.analysis.comparison import compare_strategy_summaries, summarize_annual_stability
from src.analysis.plots import plot_multi_cumulative_returns
from src.data.prices import DEFAULT_TICKERS
from src.data.texts import load_text_dataset
from src.features.placeholder import make_random_signal
from src.features.text_signals import build_point_in_time_text_signal_matrix, score_text_records
from src.pipeline import DEFAULT_TEXT_DATA_PATH, _prepare_price_data, _run_backtest_for_signal


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LLM_FEATURES = PROJECT_ROOT / "data/processed/llm_text_features.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports"


def _format_pct(value: float) -> str:
    if pd.isna(value):
        return "nan"
    return f"{value:.2%}"


def _write_report(
    metrics: pd.DataFrame,
    coverage: pd.Series,
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
            "n_periods",
        ]
    ].copy()
    for column in ("annualized_return", "max_drawdown", "mean_ic", "mean_rank_ic"):
        display[column] = display[column].map(_format_pct)
    display["sharpe_ratio"] = display["sharpe_ratio"].map(lambda value: f"{value:.2f}")
    display["n_periods"] = display["n_periods"].astype(int)

    lines = [
        "# DeepSeek LLM Signal Comparison",
        "",
        "All strategies are evaluated on the same date/ticker coverage.",
        "",
        "## Coverage",
        "",
        coverage.to_frame("value").to_markdown(),
        "",
        "## Metrics",
        "",
        display.to_markdown(),
        "",
        f"Cumulative return plot: `{cumulative_png.name}`",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_llm_comparison(
    llm_features_path: str | Path,
    text_data_path: str | Path = DEFAULT_TEXT_DATA_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    start: str = "2020-01-01",
    end: str | None = "2026-01-01",
    seed: int = 42,
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
    llm_features = load_text_dataset(llm_features_path)

    text_signal = build_point_in_time_text_signal_matrix(
        text_features,
        monthly_index=forward_returns.index,
        tickers=forward_returns.columns,
        signal_column="text_signal",
    )
    llm_signal = build_point_in_time_text_signal_matrix(
        llm_features,
        monthly_index=forward_returns.index,
        tickers=forward_returns.columns,
        signal_column="llm_text_signal",
    )

    common_index = text_signal.index.intersection(llm_signal.index).intersection(forward_returns.index)
    common_columns = text_signal.columns.intersection(llm_signal.columns).intersection(forward_returns.columns)
    text_signal = text_signal.reindex(index=common_index, columns=common_columns)
    llm_signal = llm_signal.reindex(index=common_index, columns=common_columns)
    common_mask = text_signal.notna() & llm_signal.notna()

    text_signal = text_signal.where(common_mask).dropna(axis=0, how="all").dropna(axis=1, how="all")
    llm_signal = llm_signal.where(common_mask).reindex_like(text_signal)
    random_signal = make_random_signal(
        index=text_signal.index,
        columns=text_signal.columns,
        seed=seed,
    ).where(text_signal.notna())

    strategy_results = {
        "original_text_signal": _run_backtest_for_signal(text_signal, forward_returns),
        "deepseek_llm_text_signal": _run_backtest_for_signal(llm_signal, forward_returns),
        "random_no_text": _run_backtest_for_signal(random_signal, forward_returns),
    }
    metrics = compare_strategy_summaries(strategy_results)

    portfolio_returns = {
        name: result["portfolio_returns"] for name, result in strategy_results.items()
    }
    cumulative = plot_multi_cumulative_returns(
        portfolio_returns,
        output / "llm_deepseek_cumulative_returns.png",
        csv_output_path=output / "llm_deepseek_cumulative_returns.csv",
    )

    coverage = pd.Series(
        {
            "llm_feature_rows": int(llm_features.shape[0]),
            "llm_feature_tickers": int(llm_features["ticker"].nunique()),
            "common_signal_months": int(text_signal.shape[0]),
            "common_signal_tickers": int(text_signal.shape[1]),
            "backtest_periods": int(metrics.loc["deepseek_llm_text_signal", "n_periods"]),
        }
    )

    metrics.to_csv(output / "llm_deepseek_comparison_metrics.csv")
    coverage.to_frame("value").to_csv(output / "llm_deepseek_coverage.csv")
    text_signal.to_csv(output / "llm_deepseek_original_text_signal.csv")
    llm_signal.to_csv(output / "llm_deepseek_signal.csv")
    random_signal.to_csv(output / "llm_deepseek_random_signal.csv")
    for name, result in strategy_results.items():
        result["portfolio_returns"].to_csv(output / f"llm_deepseek_{name}_portfolio_returns.csv")
        result["ic"].to_csv(output / f"llm_deepseek_{name}_ic.csv")
        summarize_annual_stability(result["portfolio_returns"], result["ic"]).to_csv(
            output / f"llm_deepseek_{name}_annual_stability.csv"
        )

    _write_report(
        metrics=metrics,
        coverage=coverage,
        output_path=output / "llm_deepseek_comparison.md",
        cumulative_png=output / "llm_deepseek_cumulative_returns.png",
    )

    return {
        "metrics": metrics,
        "coverage": coverage,
        "cumulative": cumulative,
        **strategy_results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare DeepSeek LLM signal against baselines.")
    parser.add_argument("--llm-features", default=str(DEFAULT_LLM_FEATURES), help="CSV with llm_text_signal.")
    parser.add_argument("--text-data", default=str(DEFAULT_TEXT_DATA_PATH), help="Raw text CSV for baseline.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for report outputs.")
    parser.add_argument("--start", default="2020-01-01", help="Start date for prices.")
    parser.add_argument("--end", default="2026-01-01", help="Optional end date for prices.")
    parser.add_argument("--seed", type=int, default=42, help="Random baseline seed.")
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic prices for offline checks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_llm_comparison(
        llm_features_path=args.llm_features,
        text_data_path=args.text_data,
        output_dir=args.output_dir,
        start=args.start,
        end=args.end,
        seed=args.seed,
        synthetic=args.synthetic,
    )
    print("DeepSeek LLM comparison complete")
    print(results["coverage"].to_string())
    print(results["metrics"].round(4).to_string())


if __name__ == "__main__":
    main()
