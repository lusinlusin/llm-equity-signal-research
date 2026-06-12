from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_max_drawdown(returns: pd.Series) -> float:
    """Calculate max drawdown from a simple return series."""
    returns = returns.dropna()
    if returns.empty:
        return float("nan")

    wealth = (1.0 + returns).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min())


def summarize_performance(
    returns: pd.Series,
    ic: pd.DataFrame | None = None,
    periods_per_year: int = 12,
) -> pd.Series:
    """Summarize monthly long-short returns and optional IC results."""
    returns = returns.dropna()

    if returns.empty:
        metrics = {
            "annualized_return": float("nan"),
            "annualized_volatility": float("nan"),
            "sharpe_ratio": float("nan"),
            "max_drawdown": float("nan"),
            "n_periods": 0,
        }
    else:
        avg_return = returns.mean()
        volatility = returns.std(ddof=1)
        annualized_volatility = volatility * np.sqrt(periods_per_year)
        sharpe = np.nan
        if volatility > 0:
            sharpe = avg_return / volatility * np.sqrt(periods_per_year)

        metrics = {
            "annualized_return": float((1.0 + returns).prod() ** (periods_per_year / len(returns)) - 1.0),
            "annualized_volatility": float(annualized_volatility),
            "sharpe_ratio": float(sharpe),
            "max_drawdown": calculate_max_drawdown(returns),
            "n_periods": int(len(returns)),
        }

    if ic is not None and not ic.empty:
        metrics["mean_ic"] = float(ic["ic"].mean())
        metrics["mean_rank_ic"] = float(ic["rank_ic"].mean())
    else:
        metrics["mean_ic"] = float("nan")
        metrics["mean_rank_ic"] = float("nan")

    return pd.Series(metrics)
