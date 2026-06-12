from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def calculate_cumulative_returns(returns: pd.Series) -> pd.Series:
    """Convert simple period returns into cumulative returns with an initial zero point."""
    clean_returns = returns.dropna()
    cumulative = (1.0 + clean_returns).cumprod() - 1.0
    if cumulative.empty:
        return cumulative

    index = cumulative.index
    if isinstance(index, pd.DatetimeIndex):
        initial_index = index[0] - pd.offsets.MonthEnd(1)
    elif isinstance(index, pd.PeriodIndex):
        initial_index = index[0] - 1
    elif pd.api.types.is_numeric_dtype(index):
        initial_index = index[0] - 1
    else:
        initial_index = "__start__"

    initial = pd.Series([0.0], index=pd.Index([initial_index]), name=cumulative.name)
    initial.index.name = index.name
    return pd.concat([initial, cumulative])


def plot_cumulative_return_comparison(
    text_portfolio_returns: pd.DataFrame,
    random_portfolio_returns: pd.DataFrame,
    output_path: str | Path,
    csv_output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Plot cumulative long-short returns for text signal vs random no-text baseline."""
    cumulative = pd.DataFrame(
        {
            "text_signal": calculate_cumulative_returns(
                text_portfolio_returns["long_short_return"]
            ),
            "random_no_text": calculate_cumulative_returns(
                random_portfolio_returns["long_short_return"]
            ),
        }
    ).dropna(how="all")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if csv_output_path is not None:
        csv_output = Path(csv_output_path)
        csv_output.parent.mkdir(parents=True, exist_ok=True)
        cumulative.to_csv(csv_output)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(cumulative.index, cumulative["text_signal"], label="Text signal", linewidth=2.2)
    ax.plot(
        cumulative.index,
        cumulative["random_no_text"],
        label="Random no-text baseline",
        linewidth=2.0,
        linestyle="--",
    )
    ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.6)
    ax.set_title("Cumulative Long-Short Return: Text Signal vs No-Text Baseline")
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative return")
    ax.legend()
    ax.margins(x=0.01)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)

    return cumulative


def plot_random_baseline_distribution(
    random_trials: pd.DataFrame,
    strategy_metrics: pd.Series,
    output_path: str | Path,
    metric: str = "sharpe_ratio",
) -> None:
    """Plot a random baseline metric distribution with the strategy value marked."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    values = random_trials[metric].dropna()
    strategy_value = strategy_metrics[metric]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(values, bins=40, alpha=0.75, label="Random no-text trials")
    ax.axvline(strategy_value, color="crimson", linewidth=2.2, label="Text strategy")
    ax.set_title(f"Monte Carlo Random Baseline Distribution: {metric}")
    ax.set_xlabel(metric)
    ax.set_ylabel("Trial count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_multi_cumulative_returns(
    portfolio_returns: dict[str, pd.DataFrame],
    output_path: str | Path,
    csv_output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Plot cumulative long-short returns for multiple strategies."""
    cumulative = pd.DataFrame(
        {
            name: calculate_cumulative_returns(frame["long_short_return"])
            for name, frame in portfolio_returns.items()
        }
    ).dropna(how="all")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    if csv_output_path is not None:
        csv_output = Path(csv_output_path)
        csv_output.parent.mkdir(parents=True, exist_ok=True)
        cumulative.to_csv(csv_output)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for name in cumulative.columns:
        ax.plot(cumulative.index, cumulative[name], linewidth=2.0, label=name)
    ax.axhline(0.0, color="black", linewidth=0.8, alpha=0.6)
    ax.set_title("Cumulative Long-Short Return: Before vs After")
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative return")
    ax.legend()
    ax.margins(x=0.01)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)

    return cumulative
