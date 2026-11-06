from __future__ import annotations

import gzip
import io
import json
import re
import shutil
import subprocess
import tempfile
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
SEC_RISK_FACTOR_COLUMNS = [
    "date",
    "ticker",
    "source_type",
    "cik",
    "company_name",
    "accession_number",
    "filing_date",
    "report_date",
    "document_url",
    "text",
]
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
    forms: tuple[str, ...] = ("10-K",),
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
    form_set = {form.upper() for form in forms}

    records = []
    for form, accession, filing_date, report_date, primary_document in rows:
        if not filing_date:
            continue
        filing_year = int(filing_date[:4])
        if form.upper() in form_set and start_year <= filing_year <= end_year:
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


def get_recent_filings_by_form(
    ticker: str,
    cik: int,
    company_name: str,
    start_year: int,
    end_year: int,
    forms: tuple[str, ...],
    user_agent: str = DEFAULT_USER_AGENT,
    include_older: bool = False,
) -> list[FilingRecord]:
    """Fetch recent filing metadata for one company and one or more forms."""
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
        forms=forms,
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
                    forms=forms,
                )
            )

    unique = {(filing.accession_number, filing.primary_document): filing for filing in filings}
    return sorted(unique.values(), key=lambda filing: filing.filing_date)


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
    return get_recent_filings_by_form(
        ticker=ticker,
        cik=cik,
        company_name=company_name,
        start_year=start_year,
        end_year=end_year,
        forms=("10-K",),
        user_agent=user_agent,
        include_older=include_older,
    )


_LETTER_GAP = r"[\s|]*"
_ITEM_WORD = rf"i{_LETTER_GAP}t{_LETTER_GAP}e{_LETTER_GAP}m"
_RISK_WORD = rf"r{_LETTER_GAP}i{_LETTER_GAP}s{_LETTER_GAP}k"
_FACTORS_WORD = rf"f{_LETTER_GAP}a{_LETTER_GAP}c{_LETTER_GAP}t{_LETTER_GAP}o{_LETTER_GAP}r{_LETTER_GAP}s"
_ITEM_1A_MARKER = r"1[\s|.]*a"
_ITEM_END_MARKER = r"(1[\s|.]*b|1[\s|.]*c|2|3|4|5|6|7[\s|.]*a|7|8)"
_ITEM_HEADING_SEPARATOR = r"(?:[\s.:|/\-—–]*)"
_ITEM_1A_START_PATTERN = re.compile(
    rf"\b{_ITEM_WORD}\b{_ITEM_HEADING_SEPARATOR}{_ITEM_1A_MARKER}\b"
    rf"{_ITEM_HEADING_SEPARATOR}{_RISK_WORD}\s+{_FACTORS_WORD}\b",
    re.IGNORECASE,
)
_ITEM_1A_END_PATTERN = re.compile(
    rf"\b{_ITEM_WORD}\b{_ITEM_HEADING_SEPARATOR}{_ITEM_END_MARKER}\b{_ITEM_HEADING_SEPARATOR}",
    re.IGNORECASE,
)
_TABLE_OF_CONTENTS_NEXT_ITEMS = {"1b", "1c", "2", "3", "4"}
_ANNUAL_RISK_FACTORS_START_PATTERN = re.compile(
    rf"^\s*{_RISK_WORD}\s+{_FACTORS_WORD}\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_ANNUAL_RISK_FACTORS_END_PATTERN = re.compile(
    r"^\s*("
    r"net\s+zero\s+and\s+sustainability\s*$|"
    r"sustainability\s*$|"
    r"human\s+capital\s+resources(?:\s+and\s+management)?\s*$|"
    r"managing\s+global\s+risk.*$|"
    r"significant\s+accounting\s+policies.*$|"
    r"recent\s+accounting\s+developments\s*$|"
    r"forward-looking\s+statements\s*$|"
    r"unresolved\s+staff\s+comments.*$|"
    r"cybersecurity\s*$|"
    r"properties(?:\s+and\s+legal\s+proceedings)?\s*$|"
    r"legal\s+proceedings\s*$|"
    r"market\s+for\s+registrant.*$|"
    r"financial\s+statements\s+and\s+supplementary\s+data.*$|"
    r"directors,\s+executive\s+officers.*$|"
    r"exhibits\s*$|"
    r"form\s+10-k\s+cross\s+reference\s+index\s*$|"
    r"signatures\s*$"
    r")",
    re.IGNORECASE | re.MULTILINE,
)
_CROSS_REFERENCE_FOLLOWERS = {'"', "'", "”", "’", ",", ";", ")", "]"}
_CROSS_REFERENCE_PREFIX_PATTERN = re.compile(
    r"(refer\s+to|included\s+in|under|see|see\s+also|discussed\s+in|"
    r"described\s+in|set\s+forth\s+in|section\s+titled|and|or)\s*"
    r"[\"'“‘]?$",
    re.IGNORECASE,
)


def _at_line_start(text: str, position: int) -> bool:
    index = position - 1
    while index >= 0 and text[index] == " ":
        index -= 1
    return index < 0 or text[index] == "\n"


def _has_cross_reference_prefix(text: str, position: int) -> bool:
    before = re.sub(r"\s+", " ", text[max(0, position - 180): position]).strip()
    return bool(_CROSS_REFERENCE_PREFIX_PATTERN.search(before))


def _has_cross_reference_follower(text: str, position: int) -> bool:
    after = text[position: position + 40].lstrip()
    return after[:1] in _CROSS_REFERENCE_FOLLOWERS or bool(re.match(r"[.)]*\s*[\"'”’]", after))


def _document_plain_text(document_html: str) -> str:
    soup = BeautifulSoup(document_html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text("\n")
    return _normalize_plain_text(text)


def _normalize_plain_text(text: str) -> str:
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
        if _has_cross_reference_prefix(text, start_match.start()):
            continue
        if _has_cross_reference_follower(text, start_match.end()):
            continue
        start = start_match.start()
        end_match = next(
            (
                match
                for match in _ITEM_1A_END_PATTERN.finditer(text, start_match.end())
                if not _has_cross_reference_prefix(text, match.start())
            ),
            None,
        )
        end = end_match.start() if end_match else min(len(text), start + 200_000)
        candidate = text[start:end].strip()
        if len(candidate) >= 1_000:
            candidates.append(candidate)

    if not candidates:
        return ""
    return _collapse_section(max(candidates, key=len))


def _extract_item_1a_from_plain_text(text: str) -> str:
    bounded: list[str] = []
    unbounded: list[str] = []
    for start_match in _ITEM_1A_START_PATTERN.finditer(text):
        if not _at_line_start(text, start_match.start()):
            continue
        if _has_cross_reference_prefix(text, start_match.start()):
            continue
        if _has_cross_reference_follower(text, start_match.end()):
            continue

        start = start_match.start()
        skip_start = False
        for end_match in _ITEM_1A_END_PATTERN.finditer(text, start_match.end()):
            if not _at_line_start(text, end_match.start()):
                continue
            if _has_cross_reference_prefix(text, end_match.start()):
                continue
            candidate = text[start:end_match.start()].strip()
            if len(candidate) < 1_000:
                end_marker = re.sub(r"[\s|.]", "", end_match.group(1).lower())
                if end_marker in _TABLE_OF_CONTENTS_NEXT_ITEMS:
                    skip_start = True
                    break
                continue
            if len(candidate) >= 1_000:
                bounded.append(candidate)
                break
        else:
            candidate = text[start: min(len(text), start + 200_000)].strip()
            if len(candidate) >= 1_000:
                unbounded.append(candidate)
        if skip_start:
            continue

    candidates = bounded or unbounded
    if candidates:
        return _collapse_section(max(candidates, key=len))

    annual_candidates: list[str] = []
    for start_match in _ANNUAL_RISK_FACTORS_START_PATTERN.finditer(text):
        start = start_match.start()
        end_match = _ANNUAL_RISK_FACTORS_END_PATTERN.search(text, start_match.end())
        if end_match is None:
            continue
        candidate = text[start:end_match.start()].strip()
        if len(candidate) >= 1_000:
            annual_candidates.append(candidate)

    if annual_candidates:
        return _collapse_section(max(annual_candidates, key=len))

    return _legacy_extract_item_1a(text)


def extract_item_1a_risk_factors(document_html: str) -> str:
    """Extract the Item 1A Risk Factors section from a 10-K document.

    Both the section start and the section end must be headings at the start
    of a line: mid-sentence mentions like "see Item 1A. Risk Factors of this
    Annual Report" are cross-references, not headings, and matching them used
    to return MD&A or reserves text instead of risk factors. Candidates that
    end at a real Item 1B/1C/2 heading are preferred over the open-ended
    200k-char fallback for the same reason.
    """
    return _extract_item_1a_from_plain_text(_document_plain_text(document_html))


def _pdf_plain_text_with_pdftotext(raw_pdf: bytes) -> str:
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        return ""

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = Path(tmp_dir) / "filing.pdf"
        text_path = Path(tmp_dir) / "filing.txt"
        pdf_path.write_bytes(raw_pdf)
        try:
            subprocess.run(
                [pdftotext, "-layout", str(pdf_path), str(text_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except (OSError, subprocess.CalledProcessError):
            return ""
        return text_path.read_text(encoding="utf-8", errors="replace")


def _pdf_plain_text_with_pypdf(raw_pdf: bytes) -> str:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(io.BytesIO(raw_pdf))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def _extract_item_1a_from_pdf(raw_pdf: bytes) -> str:
    for text in (_pdf_plain_text_with_pdftotext(raw_pdf), _pdf_plain_text_with_pypdf(raw_pdf)):
        if not text:
            continue
        risk_factors = _extract_item_1a_from_plain_text(_normalize_plain_text(text))
        if risk_factors:
            return risk_factors
    return ""


def _related_ars_filings(filing: FilingRecord, user_agent: str, max_day_gap: int = 7) -> list[FilingRecord]:
    target_date = pd.Timestamp(filing.filing_date)
    candidates = get_recent_filings_by_form(
        ticker=filing.ticker,
        cik=filing.cik,
        company_name=filing.company_name,
        start_year=target_date.year - 1,
        end_year=target_date.year + 1,
        forms=("ARS",),
        user_agent=user_agent,
        include_older=False,
    )
    nearby = [
        candidate
        for candidate in candidates
        if abs((pd.Timestamp(candidate.filing_date) - target_date).days) <= max_day_gap
    ]
    return sorted(nearby, key=lambda candidate: abs((pd.Timestamp(candidate.filing_date) - target_date).days))


def _extract_filing_risk_factors(filing: FilingRecord, user_agent: str) -> tuple[str, str]:
    raw_html = _sec_get(filing.document_url, user_agent=user_agent).decode("utf-8", errors="replace")
    risk_factors = extract_item_1a_risk_factors(raw_html)
    if risk_factors:
        return risk_factors, filing.document_url

    for annual_report in _related_ars_filings(filing, user_agent=user_agent):
        if not annual_report.primary_document.lower().endswith(".pdf"):
            continue
        raw_pdf = _sec_get(annual_report.document_url, user_agent=user_agent)
        risk_factors = _extract_item_1a_from_pdf(raw_pdf)
        if risk_factors:
            print(
                f"Using ARS PDF fallback for {filing.ticker} {filing.filing_date}: "
                f"{annual_report.document_url}",
                flush=True,
            )
            return risk_factors, annual_report.document_url

    return "", filing.document_url


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
            risk_factors, document_url = _extract_filing_risk_factors(filing, user_agent=user_agent)
            if not risk_factors:
                print(f"No Item 1A extracted for {normalized_ticker} {filing.filing_date}", flush=True)
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
                    "document_url": document_url,
                    "text": risk_factors,
                }
            )

    records_df = pd.DataFrame(records, columns=SEC_RISK_FACTOR_COLUMNS)
    if records_df.empty:
        return records_df
    return records_df.sort_values(["date", "ticker"]).reset_index(drop=True)


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

            risk_factors, document_url = _extract_filing_risk_factors(filing, user_agent=user_agent)
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
                    "document_url": document_url,
                    "text": risk_factors,
                }
            )
            print(f"Downloaded prior context {ticker} {filing.filing_date}", flush=True)

    combined = pd.concat([existing, pd.DataFrame(records, columns=SEC_RISK_FACTOR_COLUMNS)], ignore_index=True)
    if not combined.empty:
        combined = (
            combined.drop_duplicates(subset=["ticker", "date", "accession_number"], keep="last")
            .sort_values(["date", "ticker"])
            .reset_index(drop=True)
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output, index=False)
    return combined
