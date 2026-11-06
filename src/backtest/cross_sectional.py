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


def _centered_rank(values: pd.Series) -> pd.Series:
    clean = values.dropna()
    scores = pd.Series(0.0, index=values.index, dtype=float)
    if clean.shape[0] < 2:
        return scores

    ranks = clean.rank(method="average")
    denominator = clean.shape[0] - 1
    scores.loc[clean.index] = (ranks - ranks.mean()) / denominator
    return scores


def _rank_scores(frame: pd.DataFrame, sector_neutral: bool) -> pd.Series:
    if not sector_neutral:
        return _centered_rank(frame["signal"])

    sector_scores = pd.Series(0.0, index=frame.index, dtype=float)
    for _, group in frame.groupby("sector", sort=False):
        sector_scores.loc[group.index] = _centered_rank(group["signal"])
    return sector_scores


def run_rank_weighted_backtest(
    signal: pd.DataFrame,
    forward_returns: pd.DataFrame,
    metadata: pd.DataFrame,
    sector_neutral: bool = False,
) -> pd.DataFrame:
    """Run a rank-weighted long-short strategy, optionally with sector-level budgets."""
    signal, forward_returns = signal.align(forward_returns, join="inner", axis=None)
    metadata = metadata.copy()
    metadata.index = metadata.index.astype(str).str.upper()
    rows: list[dict[str, float | int | pd.Timestamp]] = []

    for date in signal.index:
        frame = pd.DataFrame(
            {
                "signal": signal.loc[date],
                "forward_return": forward_returns.loc[date],
            }
        ).dropna()
        frame = frame.join(metadata[["sector"]], how="inner").dropna(subset=["sector"])
        if frame.shape[0] < 3:
            continue

        scores = _rank_scores(frame, sector_neutral=sector_neutral)
        positive_scores = scores.clip(lower=0.0)
        negative_scores = (-scores).clip(lower=0.0)
        long_weights = pd.Series(0.0, index=frame.index, dtype=float)
        short_weights = pd.Series(0.0, index=frame.index, dtype=float)

        if sector_neutral:
            active_sectors: list[tuple[pd.Index, float]] = []
            for _, group in frame.groupby("sector", sort=False):
                pos_sum = positive_scores.loc[group.index].sum()
                neg_sum = negative_scores.loc[group.index].sum()
                if pos_sum > 0 and neg_sum > 0:
                    active_sectors.append((group.index, float(group.shape[0])))

            total_budget = sum(size for _, size in active_sectors)
            if total_budget <= 0:
                continue

            for sector_index, sector_size in active_sectors:
                budget = sector_size / total_budget
                long_slice = positive_scores.loc[sector_index]
                short_slice = negative_scores.loc[sector_index]
                long_weights.loc[sector_index] = budget * long_slice / long_slice.sum()
                short_weights.loc[sector_index] = budget * short_slice / short_slice.sum()
        else:
            if positive_scores.sum() <= 0 or negative_scores.sum() <= 0:
                continue
            long_weights = positive_scores / positive_scores.sum()
            short_weights = negative_scores / negative_scores.sum()

        long_return = float((frame["forward_return"] * long_weights).sum())
        short_return = float((frame["forward_return"] * short_weights).sum())
        rows.append(
            {
                "date": date,
                "long_return": long_return,
                "short_return": short_return,
                "long_short_return": long_return - short_return,
                "n_long": int((long_weights > 0).sum()),
                "n_short": int((short_weights > 0).sum()),
                "effective_n_long": float(1.0 / (long_weights[long_weights > 0] ** 2).sum()),
                "effective_n_short": float(1.0 / (short_weights[short_weights > 0] ** 2).sum()),
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
