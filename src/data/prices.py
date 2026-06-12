from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import yfinance as yf


DEFAULT_TICKERS: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "GOOG",
    "BRK-B",
    "LLY",
    "AVGO",
    "JPM",
    "TSLA",
    "UNH",
    "V",
    "XOM",
    "MA",
    "PG",
    "COST",
    "HD",
    "JNJ",
    "ABBV",
    "WMT",
    "MRK",
    "BAC",
    "NFLX",
    "KO",
    "PEP",
    "CRM",
    "ADBE",
    "CSCO",
    "AMD",
    "ORCL",
    "MCD",
    "IBM",
    "GE",
    "CAT",
    "GS",
    "RTX",
    "SPGI",
    "INTU",
    "NOW",
    "QCOM",
    "TXN",
    "AMGN",
    "HON",
    "NEE",
    "LOW",
    "UPS",
    "TMO",
    "ISRG",
    "BKNG",
)


def download_adjusted_close(
    tickers: Sequence[str] = DEFAULT_TICKERS,
    start: str = "2018-01-01",
    end: str | None = None,
) -> pd.DataFrame:
    """Download split/dividend-adjusted close prices from yfinance."""
    raw = yf.download(
        list(tickers),
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    if raw.empty:
        raise ValueError("yfinance returned no price data")

    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            raise ValueError("yfinance response does not include adjusted close prices")
        prices = raw["Close"]
    else:
        if "Close" not in raw.columns:
            raise ValueError("yfinance response does not include adjusted close prices")
        prices = raw[["Close"]].copy()
        prices.columns = [tickers[0]]

    prices = prices.sort_index()
    prices.index = pd.to_datetime(prices.index)
    return prices.dropna(axis=1, how="all")


def make_synthetic_prices(
    tickers: Sequence[str] = DEFAULT_TICKERS,
    start: str = "2018-01-01",
    periods: int = 252 * 6,
    seed: int = 7,
) -> pd.DataFrame:
    """Create deterministic synthetic daily prices for offline verification."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=periods)
    ticker_list = list(tickers)

    daily_returns = rng.normal(loc=0.0003, scale=0.018, size=(len(dates), len(ticker_list)))
    prices = 100.0 * np.exp(np.cumsum(daily_returns, axis=0))
    return pd.DataFrame(prices, index=dates, columns=ticker_list)


def to_monthly_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Convert daily prices to month-end prices."""
    monthly = prices.resample("ME").last()
    return monthly.dropna(axis=0, how="all").dropna(axis=1, how="all")


def compute_monthly_returns(monthly_prices: pd.DataFrame) -> pd.DataFrame:
    """Compute same-month simple returns from month-end prices."""
    return monthly_prices.pct_change(fill_method=None)


def compute_forward_returns(monthly_prices: pd.DataFrame) -> pd.DataFrame:
    """Compute 1-month forward returns aligned to the signal date."""
    monthly_returns = compute_monthly_returns(monthly_prices)
    return monthly_returns.shift(-1)
