from __future__ import annotations

import pandas as pd

from src.backtest.cross_sectional import calculate_information_coefficients, run_long_short_backtest
from src.backtest.metrics import summarize_performance
from src.features.neutralization import neutralize_signal
from src.features.placeholder import make_persistent_random_signal_like, make_random_signal


def _trial_summary(
    signal: pd.DataFrame,
    forward_returns: pd.DataFrame,
) -> pd.Series:
    portfolio_returns = run_long_short_backtest(signal, forward_returns)
    ic = calculate_information_coefficients(signal, forward_returns)
    metrics = summarize_performance(portfolio_returns["long_short_return"], ic=ic)
    final_cumulative_return = (1.0 + portfolio_returns["long_short_return"]).prod() - 1.0
    metrics["final_cumulative_return"] = float(final_cumulative_return)
    return metrics


def run_random_baseline_trials(
    target_signal: pd.DataFrame,
    forward_returns: pd.DataFrame,
    n_trials: int = 500,
    seed_start: int = 1_000,
    metadata: pd.DataFrame | None = None,
    neutralize_random: bool = False,
    persistent: bool = False,
) -> pd.DataFrame:
    """Run repeated random no-text baselines on the same coverage as a target signal."""
    rows = []
    for trial in range(n_trials):
        seed = seed_start + trial
        if persistent:
            random_signal = make_persistent_random_signal_like(target_signal, seed=seed)
        else:
            random_signal = make_random_signal(
                index=target_signal.index,
                columns=target_signal.columns,
                seed=seed,
            ).where(target_signal.notna())

        if neutralize_random:
            if metadata is None:
                raise ValueError("metadata is required when neutralize_random=True")
            random_signal = neutralize_signal(random_signal, metadata)

        metrics = _trial_summary(random_signal, forward_returns)
        metrics["trial"] = trial
        metrics["seed"] = seed
        rows.append(metrics)

    return pd.DataFrame(rows).set_index("trial")


def compare_to_random_distribution(
    strategy_metrics: pd.Series,
    random_trials: pd.DataFrame,
) -> pd.DataFrame:
    """Compare one strategy's metrics against repeated random baseline trials."""
    rows = []
    for metric in (
        "annualized_return",
        "annualized_volatility",
        "sharpe_ratio",
        "max_drawdown",
        "mean_ic",
        "mean_rank_ic",
        "final_cumulative_return",
    ):
        if metric not in strategy_metrics.index or metric not in random_trials.columns:
            continue

        strategy_value = strategy_metrics[metric]
        random_values = random_trials[metric].dropna()
        if random_values.empty:
            continue

        higher_is_better = metric != "max_drawdown"
        if higher_is_better:
            percentile = (random_values < strategy_value).mean()
            empirical_p_value = (random_values >= strategy_value).mean()
        else:
            percentile = (random_values > strategy_value).mean()
            empirical_p_value = (random_values <= strategy_value).mean()

        rows.append(
            {
                "metric": metric,
                "strategy_value": strategy_value,
                "random_mean": random_values.mean(),
                "random_std": random_values.std(ddof=1),
                "random_p05": random_values.quantile(0.05),
                "random_p50": random_values.quantile(0.50),
                "random_p95": random_values.quantile(0.95),
                "strategy_percentile": percentile,
                "empirical_p_value": empirical_p_value,
            }
        )

    return pd.DataFrame(rows).set_index("metric")
