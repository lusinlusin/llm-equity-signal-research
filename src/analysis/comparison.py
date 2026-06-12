from __future__ import annotations

import pandas as pd


def summarize_strategy_stability(
    portfolio_returns: pd.DataFrame,
    ic: pd.DataFrame,
    metrics: pd.Series,
) -> pd.Series:
    """Combine performance metrics with simple month-to-month stability diagnostics."""
    long_short = portfolio_returns["long_short_return"].dropna()
    ic_values = ic["ic"].dropna() if "ic" in ic else pd.Series(dtype=float)
    rank_ic_values = ic["rank_ic"].dropna() if "rank_ic" in ic else pd.Series(dtype=float)

    summary = metrics.copy()
    summary["mean_monthly_long_short_return"] = long_short.mean()
    summary["long_short_return_std"] = long_short.std(ddof=1)
    summary["long_short_positive_rate"] = (long_short > 0).mean()
    summary["ic_std"] = ic_values.std(ddof=1)
    summary["ic_positive_rate"] = (ic_values > 0).mean()
    summary["rank_ic_std"] = rank_ic_values.std(ddof=1)
    summary["rank_ic_positive_rate"] = (rank_ic_values > 0).mean()
    return summary


def compare_strategy_summaries(
    strategy_results: dict[str, dict[str, pd.DataFrame | pd.Series]],
) -> pd.DataFrame:
    """Create a metrics table across comparable signal variants."""
    rows = {}
    for name, results in strategy_results.items():
        rows[name] = summarize_strategy_stability(
            portfolio_returns=results["portfolio_returns"],
            ic=results["ic"],
            metrics=results["metrics"],
        )
    return pd.DataFrame(rows).T


def summarize_annual_stability(
    portfolio_returns: pd.DataFrame,
    ic: pd.DataFrame,
) -> pd.DataFrame:
    """Summarize long-short returns, IC, and rank IC by calendar year."""
    combined = portfolio_returns[["long_short_return"]].join(ic[["ic", "rank_ic"]], how="inner")
    if combined.empty:
        return pd.DataFrame(
            columns=[
                "n_months",
                "mean_monthly_long_short_return",
                "long_short_positive_rate",
                "mean_ic",
                "ic_positive_rate",
                "mean_rank_ic",
                "rank_ic_positive_rate",
            ]
        )

    combined = combined.copy()
    combined["year"] = combined.index.year
    return combined.groupby("year").agg(
        n_months=("long_short_return", "count"),
        mean_monthly_long_short_return=("long_short_return", "mean"),
        long_short_positive_rate=("long_short_return", lambda series: (series > 0).mean()),
        mean_ic=("ic", "mean"),
        ic_positive_rate=("ic", lambda series: (series > 0).mean()),
        mean_rank_ic=("rank_ic", "mean"),
        rank_ic_positive_rate=("rank_ic", lambda series: (series > 0).mean()),
    )
