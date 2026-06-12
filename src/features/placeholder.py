from __future__ import annotations

import numpy as np
import pandas as pd


def make_random_signal(
    index: pd.Index,
    columns: pd.Index | list[str],
    seed: int = 42,
) -> pd.DataFrame:
    """Create a deterministic random signal for pipeline testing."""
    rng = np.random.default_rng(seed)
    values = rng.standard_normal((len(index), len(columns)))
    return pd.DataFrame(values, index=index, columns=columns)


def make_persistent_random_signal_like(target_signal: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """Create random scores that persist through each target signal spell."""
    rng = np.random.default_rng(seed)
    random_signal = pd.DataFrame(index=target_signal.index, columns=target_signal.columns, dtype=float)

    for column in target_signal.columns:
        values = target_signal[column]
        valid = values.notna()
        if not valid.any():
            continue

        previous_valid = valid.shift(fill_value=False)
        starts = valid & (~previous_valid | values.ne(values.shift()))
        group_ids = starts.cumsum().where(valid)

        for group_id in pd.unique(group_ids.dropna()):
            mask = group_ids == group_id
            random_signal.loc[mask, column] = rng.standard_normal()

    return random_signal
