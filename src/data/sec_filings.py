from __future__ import annotations

import gzip
import json
import re
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pandas as pd
from bs4 import BeautifulSoup


SEC_DATA_BASE = "https://data.sec.gov"
SEC_FILES_BASE = "https://www.sec.gov/files"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives"
DEFAULT_USER_AGENT = "llm-equity-signal-research/0.1 (contact: wulinw2wdl@gmail.com)"
DEFAULT_SEC_TICKERS: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
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


@dataclass(frozen=True)
class FilingRecord:
    ticker: str
    cik: int
    company_name: str
    accession_number: str
    filing_date: str
    report_date: str
    primary_document: str

    @property
    def document_url(self) -> str:
        cik_no_leading_zero = str(self.cik)
        accession_no_dashes = self.accession_number.replace("-", "")
        return (
            f"{SEC_ARCHIVES_BASE}/edgar/data/"
            f"{cik_no_leading_zero}/{accession_no_dashes}/{self.primary_document}"
        )


def _sec_get(url: str, user_agent: str = DEFAULT_USER_AGENT, sleep_seconds: float = 0.12) -> bytes:
    """Fetch SEC content with a required descriptive user agent."""
    parsed = urlparse(url)
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip",
            "Host": parsed.netloc,
        },
    )
    with urlopen(request, timeout=45) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    time.sleep(sleep_seconds)
    return raw


def _sec_get_json(url: str, user_agent: str = DEFAULT_USER_AGENT) -> dict:
    return json.loads(_sec_get(url, user_agent=user_agent).decode("utf-8"))


def load_sec_ticker_map(user_agent: str = DEFAULT_USER_AGENT) -> dict[str, tuple[int, str]]:
    """Return ticker -> (CIK, company name) from the SEC company ticker file."""
    payload = _sec_get_json(f"{SEC_FILES_BASE}/company_tickers.json", user_agent=user_agent)
    ticker_map = {}
    for company in payload.values():
        ticker = company["ticker"].upper()
        ticker_map[ticker] = (int(company["cik_str"]), company["title"])
    return ticker_map


def _filing_records_from_arrays(
    ticker: str,
    cik: int,
    company_name: str,
    filings: dict,
    start_year: int,
    end_year: int,
) -> list[FilingRecord]:
    columns = (
        filings["form"],
        filings["accessionNumber"],
        filings["filingDate"],
        filings["reportDate"],
        filings["primaryDocument"],
    )
    if len({len(column) for column in columns}) != 1:
        raise ValueError("SEC submissions arrays have mismatched lengths")
    rows = zip(*columns)

    records = []
    for form, accession, filing_date, report_date, primary_document in rows:
        if not filing_date:
            continue
        filing_year = int(filing_date[:4])
        if form == "10-K" and start_year <= filing_year <= end_year:
            records.append(
                FilingRecord(
                    ticker=ticker,
                    cik=cik,
                    company_name=company_name,
                    accession_number=accession,
                    filing_date=filing_date,
                    report_date=report_date,
                    primary_document=primary_document,
                )
            )
    return records


def get_recent_10k_filings(
    ticker: str,
    cik: int,
    company_name: str,
    start_year: int,
    end_year: int,
    user_agent: str = DEFAULT_USER_AGENT,
    include_older: bool = False,
) -> list[FilingRecord]:
    """Fetch recent 10-K filing metadata for one company."""
    submissions = _sec_get_json(
        f"{SEC_DATA_BASE}/submissions/CIK{cik:010d}.json",
        user_agent=user_agent,
    )
    recent = submissions["filings"]["recent"]
    filings = _filing_records_from_arrays(
        ticker=ticker,
        cik=cik,
        company_name=company_name,
        filings=recent,
        start_year=start_year,
        end_year=end_year,
    )

    if include_older:
        for file_info in submissions["filings"].get("files", []):
            older = _sec_get_json(
                f"{SEC_DATA_BASE}/submissions/{file_info['name']}",
                user_agent=user_agent,
            )
            filings.extend(
                _filing_records_from_arrays(
                    ticker=ticker,
                    cik=cik,
                    company_name=company_name,
                    filings=older,
                    start_year=start_year,
                    end_year=end_year,
                )
            )

    unique = {(filing.accession_number, filing.primary_document): filing for filing in filings}
    return sorted(unique.values(), key=lambda filing: filing.filing_date)


_RISK_WORD = r"r\s*i\s*s\s*k"
_FACTORS_WORD = r"f\s*a\s*c\s*t\s*o\s*r\s*s"
_ITEM_1A_START_PATTERN = re.compile(
    rf"\bitem\s+1a[.:]?\s*[-—–]?\s*{_RISK_WORD}\s+{_FACTORS_WORD}\b",
    re.IGNORECASE,
)
_ITEM_1A_END_PATTERN = re.compile(
    r"\bitem\s+(1b|1c|2)[.:]?\s*[-—–]?\s*"
    r"(unresolved\s+staff\s+comments|cybersecurity|properties)?\b",
    re.IGNORECASE,
)
_CROSS_REFERENCE_FOLLOWERS = {'"', "'", "”", "’", ",", ";", ")", "]"}


def _at_line_start(text: str, position: int) -> bool:
    index = position - 1
    while index >= 0 and text[index] == " ":
        index -= 1
    return index < 0 or text[index] == "\n"


def _document_plain_text(document_html: str) -> str:
    soup = BeautifulSoup(document_html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text("\n")
    text = re.sub(r"\xa0", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _collapse_section(section: str) -> str:
    section = re.sub(r"\n+", " ", section)
    section = re.sub(r"\s+", " ", section)
    return section.strip()


def _legacy_extract_item_1a(text: str) -> str:
    """Pre-fix extraction: any-position headings, longest candidate wins.

    Kept only as a last resort for documents where no heading sits at a line
    start; mid-sentence cross-references make it grab wrong sections.
    """
    candidates: list[str] = []
    for start_match in _ITEM_1A_START_PATTERN.finditer(text):
        after_heading = text[start_match.end(): start_match.end() + 40].lstrip()
        if after_heading[:1] in _CROSS_REFERENCE_FOLLOWERS:
            continue
        start = start_match.start()
        end_match = _ITEM_1A_END_PATTERN.search(text, start_match.end())
        end = end_match.start() if end_match else min(len(text), start + 200_000)
        candidate = text[start:end].strip()
        if len(candidate) >= 1_000:
            candidates.append(candidate)

    if not candidates:
        return ""
    return _collapse_section(max(candidates, key=len))


def extract_item_1a_risk_factors(document_html: str) -> str:
    """Extract the Item 1A Risk Factors section from a 10-K document.

    Both the section start and the section end must be headings at the start
    of a line: mid-sentence mentions like "see Item 1A. Risk Factors of this
    Annual Report" are cross-references, not headings, and matching them used
    to return MD&A or reserves text instead of risk factors. Candidates that
    end at a real Item 1B/1C/2 heading are preferred over the open-ended
    200k-char fallback for the same reason.
    """
    text = _document_plain_text(document_html)

    bounded: list[str] = []
    unbounded: list[str] = []
    for start_match in _ITEM_1A_START_PATTERN.finditer(text):
        if not _at_line_start(text, start_match.start()):
            continue
        after_heading = text[start_match.end(): start_match.end() + 40].lstrip()
        if after_heading[:1] in _CROSS_REFERENCE_FOLLOWERS:
            continue

        start = start_match.start()
        end_match = next(
            (
                match
                for match in _ITEM_1A_END_PATTERN.finditer(text, start_match.end())
                if _at_line_start(text, match.start())
            ),
            None,
        )
        if end_match is not None:
            candidate = text[start:end_match.start()].strip()
            bucket = bounded
        else:
            candidate = text[start: min(len(text), start + 200_000)].strip()
            bucket = unbounded
        if len(candidate) >= 1_000:
            bucket.append(candidate)

    candidates = bounded or unbounded
    if not candidates:
        return _legacy_extract_item_1a(text)
    return _collapse_section(max(candidates, key=len))


def download_10k_risk_factor_records(
    tickers: tuple[str, ...] = DEFAULT_SEC_TICKERS,
    start_year: int = 2020,
    end_year: int | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
) -> pd.DataFrame:
    """Download real 10-K Item 1A text records with filing-date point-in-time metadata."""
    if end_year is None:
        end_year = date.today().year

    ticker_map = load_sec_ticker_map(user_agent=user_agent)
    records: list[dict[str, str | int]] = []
    for ticker in tickers:
        normalized_ticker = ticker.upper()
        if normalized_ticker not in ticker_map:
            print(f"Skipping ticker not found in SEC ticker map: {ticker}")
            continue

        cik, company_name = ticker_map[normalized_ticker]
        filings = get_recent_10k_filings(
            ticker=normalized_ticker,
            cik=cik,
            company_name=company_name,
            start_year=start_year,
            end_year=end_year,
            user_agent=user_agent,
        )

        for filing in filings:
            raw_html = _sec_get(filing.document_url, user_agent=user_agent).decode("utf-8", errors="replace")
            risk_factors = extract_item_1a_risk_factors(raw_html)
            if not risk_factors:
                continue

            records.append(
                {
                    "date": filing.filing_date,
                    "ticker": filing.ticker,
                    "source_type": "sec_10k_item_1a",
                    "cik": filing.cik,
                    "company_name": filing.company_name,
                    "accession_number": filing.accession_number,
                    "filing_date": filing.filing_date,
                    "report_date": filing.report_date,
                    "document_url": filing.document_url,
                    "text": risk_factors,
                }
            )

    return pd.DataFrame(records).sort_values(["date", "ticker"]).reset_index(drop=True)


def save_sec_10k_risk_factors(
    output_path: str | Path,
    tickers: tuple[str, ...] = DEFAULT_SEC_TICKERS,
    start_year: int = 2020,
    end_year: int | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
) -> pd.DataFrame:
    records = download_10k_risk_factor_records(
        tickers=tickers,
        start_year=start_year,
        end_year=end_year,
        user_agent=user_agent,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    records.to_csv(output, index=False)
    return records


def _load_current_earliest(input_path: str | Path, tickers: list[str] | None = None) -> pd.DataFrame:
    current = pd.read_csv(input_path)
    current = current.copy()
    current["ticker"] = current["ticker"].astype(str).str.upper().str.strip()
    current["date"] = pd.to_datetime(current["date"], format="mixed")
    if tickers:
        ticker_set = {ticker.upper().strip() for ticker in tickers}
        current = current.loc[current["ticker"].isin(ticker_set)]
    return current.groupby("ticker", as_index=False)["date"].min().rename(columns={"date": "earliest_current_date"})


def download_prior_context_records(
    input_path: str | Path,
    output_path: str | Path,
    years_back: int = 2,
    max_prior_per_ticker: int = 2,
    tickers: list[str] | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
) -> pd.DataFrame:
    """Download prior 10-K Item 1A records before each ticker's first current filing."""
    earliest = _load_current_earliest(input_path, tickers=tickers)
    ticker_map = load_sec_ticker_map(user_agent=user_agent)

    output = Path(output_path)
    existing = pd.DataFrame()
    existing_accessions: set[str] = set()
    if output.exists():
        existing = pd.read_csv(output)
        if "accession_number" in existing.columns:
            existing_accessions = set(existing["accession_number"].astype(str))

    records: list[dict[str, str | int]] = []
    for row in earliest.itertuples(index=False):
        ticker = str(row.ticker).upper().strip()
        earliest_date = pd.Timestamp(row.earliest_current_date)
        if ticker not in ticker_map:
            print(f"Skipping ticker not found in SEC ticker map: {ticker}", flush=True)
            continue

        cik, company_name = ticker_map[ticker]
        filings = get_recent_10k_filings(
            ticker=ticker,
            cik=cik,
            company_name=company_name,
            start_year=earliest_date.year - years_back,
            end_year=earliest_date.year,
            user_agent=user_agent,
            include_older=True,
        )
        prior_filings = [
            filing for filing in filings
            if pd.Timestamp(filing.filing_date) < earliest_date
        ]
        prior_filings = sorted(prior_filings, key=lambda filing: filing.filing_date, reverse=True)[
            :max_prior_per_ticker
        ]

        if not prior_filings:
            print(f"No prior 10-K found for {ticker} before {earliest_date.date()}", flush=True)
            continue

        for filing in prior_filings:
            if filing.accession_number in existing_accessions:
                print(f"Already downloaded {ticker} {filing.filing_date}", flush=True)
                continue

            raw_html = _sec_get(filing.document_url, user_agent=user_agent).decode("utf-8", errors="replace")
            risk_factors = extract_item_1a_risk_factors(raw_html)
            if not risk_factors:
                print(f"No Item 1A extracted for {ticker} {filing.filing_date}", flush=True)
                continue

            records.append(
                {
                    "date": filing.filing_date,
                    "ticker": filing.ticker,
                    "source_type": "sec_10k_item_1a_prior_context",
                    "cik": filing.cik,
                    "company_name": filing.company_name,
                    "accession_number": filing.accession_number,
                    "filing_date": filing.filing_date,
                    "report_date": filing.report_date,
                    "document_url": filing.document_url,
                    "text": risk_factors,
                }
            )
            print(f"Downloaded prior context {ticker} {filing.filing_date}", flush=True)

    combined = pd.concat([existing, pd.DataFrame(records)], ignore_index=True)
    if not combined.empty:
        combined = (
            combined.drop_duplicates(subset=["ticker", "date", "accession_number"], keep="last")
            .sort_values(["date", "ticker"])
            .reset_index(drop=True)
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output, index=False)
    return combined
