from __future__ import annotations

import pandas as pd


def _fractional_extreme_inclusion(
    signal: pd.Series,
    quantile: float,
    largest: bool,
) -> pd.Series:
    """Select an extreme quantile without using ticker order to break ties."""
    inclusion = pd.Series(0.0, index=signal.index)
    target_count = len(signal) * quantile
    remaining = target_count

    for value in sorted(signal.unique(), reverse=largest):
        tied = signal.index[signal == value]
        if remaining >= len(tied):
            inclusion.loc[tied] = 1.0
            remaining -= len(tied)
        else:
            if remaining > 0:
                inclusion.loc[tied] = remaining / len(tied)
            break

    return inclusion


def run_long_short_backtest(
    signal: pd.DataFrame,
    forward_returns: pd.DataFrame,
    top_quantile: float = 0.20,
    bottom_quantile: float = 0.20,
) -> pd.DataFrame:
    """Rank stocks by signal each month and return top-minus-bottom performance."""
    if not 0 < top_quantile < 1:
        raise ValueError("top_quantile must be between 0 and 1")
    if not 0 < bottom_quantile < 1:
        raise ValueError("bottom_quantile must be between 0 and 1")

    signal, forward_returns = signal.align(forward_returns, join="inner", axis=None)
    rows: list[dict[str, float | pd.Timestamp | int]] = []

    for date in signal.index:
        frame = pd.DataFrame(
            {
                "signal": signal.loc[date],
                "forward_return": forward_returns.loc[date],
            }
        ).dropna()

        if frame.empty:
            continue

        long_inclusion = _fractional_extreme_inclusion(frame["signal"], top_quantile, largest=True)
        short_inclusion = _fractional_extreme_inclusion(frame["signal"], bottom_quantile, largest=False)

        if long_inclusion.sum() <= 0 or short_inclusion.sum() <= 0:
            continue

        long_weights = long_inclusion / long_inclusion.sum()
        short_weights = short_inclusion / short_inclusion.sum()
        long_return = float((frame["forward_return"] * long_weights).sum())
        short_return = float((frame["forward_return"] * short_weights).sum())

        rows.append(
            {
                "date": date,
                "long_return": long_return,
                "short_return": short_return,
                "long_short_return": long_return - short_return,
                "n_long": int((long_inclusion > 0).sum()),
                "n_short": int((short_inclusion > 0).sum()),
                "effective_n_long": float(long_inclusion.sum()),
                "effective_n_short": float(short_inclusion.sum()),
                "n_stocks": int(frame.shape[0]),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "long_return",
                "short_return",
                "long_short_return",
                "n_long",
                "n_short",
                "effective_n_long",
                "effective_n_short",
                "n_stocks",
            ]
        )

    return pd.DataFrame(rows).set_index("date").sort_index()


def calculate_information_coefficients(
    signal: pd.DataFrame,
    forward_returns: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate monthly Pearson IC and Spearman rank IC."""
    signal, forward_returns = signal.align(forward_returns, join="inner", axis=None)
    rows: list[dict[str, float | pd.Timestamp | int]] = []

    for date in signal.index:
        frame = pd.DataFrame(
            {
                "signal": signal.loc[date],
                "forward_return": forward_returns.loc[date],
            }
        ).dropna()

        if frame.shape[0] < 3:
            continue

        rows.append(
            {
                "date": date,
                "ic": float(frame["signal"].corr(frame["forward_return"], method="pearson")),
                "rank_ic": float(frame["signal"].corr(frame["forward_return"], method="spearman")),
                "n_stocks": int(frame.shape[0]),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["ic", "rank_ic", "n_stocks"])

    return pd.DataFrame(rows).set_index("date").sort_index()
