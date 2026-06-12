from __future__ import annotations

import numpy as np
import pandas as pd


def _build_design_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    sector_dummies = pd.get_dummies(frame["sector"], prefix="sector", drop_first=True, dtype=float)
    size = frame["log_market_cap"].astype(float)
    size = (size - size.mean()) / size.std(ddof=0) if size.std(ddof=0) > 0 else size * 0.0

    design = pd.concat(
        [
            pd.Series(1.0, index=frame.index, name="intercept"),
            sector_dummies,
            size.rename("log_market_cap"),
        ],
        axis=1,
    )
    return design.astype(float)


def neutralize_signal(
    signal: pd.DataFrame,
    metadata: pd.DataFrame,
    min_observations: int = 8,
) -> pd.DataFrame:
    """Neutralize each monthly signal cross-section to sector and log market cap."""
    metadata = metadata.copy()
    metadata.index = metadata.index.astype(str).str.upper()
    neutralized = pd.DataFrame(index=signal.index, columns=signal.columns, dtype=float)

    for date in signal.index:
        values = signal.loc[date].dropna()
        overlap = [ticker for ticker in values.index if ticker in metadata.index]
        if len(overlap) < min_observations:
            continue

        frame = pd.DataFrame({"signal": values.loc[overlap]}).join(
            metadata[["sector", "log_market_cap"]],
            how="inner",
        )
        frame = frame.dropna(subset=["signal", "sector", "log_market_cap"])
        if len(frame) < min_observations:
            continue

        design = _build_design_matrix(frame)
        if design.shape[0] <= design.shape[1]:
            demeaned = frame["signal"] - frame.groupby("sector")["signal"].transform("mean")
            neutralized.loc[date, demeaned.index] = demeaned
            continue

        beta, *_ = np.linalg.lstsq(design.to_numpy(), frame["signal"].to_numpy(), rcond=None)
        fitted = design.to_numpy() @ beta
        residual = frame["signal"].to_numpy() - fitted
        neutralized.loc[date, frame.index] = residual

    return neutralized.dropna(axis=0, how="all").dropna(axis=1, how="all")


def summarize_neutralization(
    raw_signal: pd.DataFrame,
    neutralized_signal: pd.DataFrame,
    metadata: pd.DataFrame,
) -> pd.Series:
    """Summarize size correlation and sector mean dispersion before and after neutralization."""
    metadata = metadata.copy()
    metadata.index = metadata.index.astype(str).str.upper()

    rows = []
    for label, signal in (("raw", raw_signal), ("neutralized", neutralized_signal)):
        for date in signal.index:
            values = signal.loc[date].dropna()
            overlap = [ticker for ticker in values.index if ticker in metadata.index]
            if len(overlap) < 3:
                continue

            frame = pd.DataFrame({"signal": values.loc[overlap]}).join(
                metadata[["sector", "log_market_cap"]],
                how="inner",
            )
            frame = frame.dropna()
            if len(frame) < 3:
                continue

            size_corr = frame["signal"].corr(frame["log_market_cap"])
            sector_dispersion = frame.groupby("sector")["signal"].mean().std(ddof=0)
            rows.append(
                {
                    "version": label,
                    "abs_size_corr": abs(size_corr) if pd.notna(size_corr) else np.nan,
                    "sector_mean_dispersion": sector_dispersion,
                }
            )

    summary = pd.DataFrame(rows)
    if summary.empty:
        return pd.Series(dtype=float)

    return summary.groupby("version").mean().stack()
