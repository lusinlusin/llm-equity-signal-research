from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.data.sec_filings import (
    DEFAULT_USER_AGENT,
    _sec_get,
    extract_item_1a_risk_factors,
    get_recent_10k_filings,
    load_sec_ticker_map,
)
from src.features.risk_section_diff import shingle_similarity


def fetch_document(url: str, cache_dir: Path, user_agent: str) -> str:
    cache_name = hashlib.sha1(url.encode()).hexdigest()[:16] + "_" + url.rsplit("/", 1)[-1]
    cache_path = cache_dir / cache_name
    if cache_path.exists():
        return cache_path.read_bytes().decode("utf-8", errors="replace")
    raw = _sec_get(url, user_agent=user_agent)
    cache_path.write_bytes(raw)
    return raw.decode("utf-8", errors="replace")


def reextract_frame(frame: pd.DataFrame, cache_dir: Path, user_agent: str, label: str) -> pd.DataFrame:
    """Re-extract Item 1A for every row; returns a row-level audit frame."""
    audit_rows = []
    for index, row in frame.iterrows():
        url = row["document_url"]
        html = fetch_document(url, cache_dir, user_agent)
        new_text = extract_item_1a_risk_factors(html)
        old_text = str(row["text"])
        changed = bool(new_text) and new_text != old_text
        if changed:
            frame.at[index, "text"] = new_text
        audit_rows.append(
            {
                "file": label,
                "ticker": row["ticker"],
                "filing_date": row["filing_date"],
                "accession_number": row["accession_number"],
                "document_url": url,
                "old_len": len(old_text),
                "new_len": len(new_text),
                "changed": changed,
                "extraction_empty": not bool(new_text),
                "old_head": old_text[:90],
                "new_head": new_text[:90],
            }
        )
        print(
            f"{label} {row['ticker']:>6} {row['filing_date']} "
            f"{len(old_text):>7} -> {len(new_text):>7} {'CHANGED' if changed else ''}"
            f"{' EMPTY-KEPT-OLD' if not new_text else ''}",
            flush=True,
        )
    return pd.DataFrame(audit_rows)


def fetch_missing_orcl_fy2019(cache_dir: Path, user_agent: str) -> dict | None:
    """ORCL's FY2019 prior is absent (old parser extracted nothing); retry with the fix."""
    ticker_map = load_sec_ticker_map(user_agent=user_agent)
    cik, company_name = ticker_map["ORCL"]
    filings = get_recent_10k_filings(
        ticker="ORCL",
        cik=cik,
        company_name=company_name,
        start_year=2019,
        end_year=2019,
        user_agent=user_agent,
        include_older=True,
    )
    if not filings:
        return None
    filing = filings[0]
    html = fetch_document(filing.document_url, cache_dir, user_agent)
    text = extract_item_1a_risk_factors(html)
    if not text:
        return None
    return {
        "date": filing.filing_date,
        "ticker": filing.ticker,
        "source_type": "sec_10k_item_1a_prior_context",
        "cik": filing.cik,
        "company_name": filing.company_name,
        "accession_number": filing.accession_number,
        "filing_date": filing.filing_date,
        "report_date": filing.report_date,
        "document_url": filing.document_url,
        "text": text,
    }


def build_pairs(current: pd.DataFrame, prior: pd.DataFrame) -> pd.DataFrame:
    """Replicate the per-ticker shift(1) pairing used by the YoY/diff workflows."""
    current = current.copy()
    prior = prior.copy()
    current["_is_current"] = True
    prior["_is_current"] = False
    both = pd.concat([prior, current], ignore_index=True)
    both["date"] = pd.to_datetime(both["date"], format="mixed")
    both = (
        both.drop_duplicates(subset=["ticker", "date", "accession_number"], keep="last")
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )
    shifted = both.groupby("ticker").shift(1)
    mask = both["_is_current"] & shifted["text"].notna()
    pairs = both.loc[mask, ["ticker", "date", "accession_number", "text"]].copy()
    pairs["prior_accession_number"] = shifted.loc[mask, "accession_number"]
    pairs["prior_text"] = shifted.loc[mask, "text"]
    pairs["similarity"] = [
        shingle_similarity(cur_text, pri_text)
        for cur_text, pri_text in zip(pairs["text"], pairs["prior_text"])
    ]
    return pairs.drop(columns=["text", "prior_text"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-extract Item 1A text with the fixed parser.")
    parser.add_argument("--current", default="data/raw/sec_10k_risk_factors.csv")
    parser.add_argument("--prior", default="data/raw/sec_10k_risk_factors_prior_context.csv")
    parser.add_argument("--cache-dir", default="/tmp/sec10k_html_cache")
    parser.add_argument("--report", default="reports/item1a_repair_report.csv")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    current = pd.read_csv(args.current)
    prior = pd.read_csv(args.prior)

    pairs_before = build_pairs(current, prior)

    audit_current = reextract_frame(current, cache_dir, args.user_agent, "current")
    audit_prior = reextract_frame(prior, cache_dir, args.user_agent, "prior")

    orcl_row = fetch_missing_orcl_fy2019(cache_dir, args.user_agent)
    if orcl_row is not None:
        prior = pd.concat([prior, pd.DataFrame([orcl_row])], ignore_index=True)
        prior = prior.sort_values(["date", "ticker"]).reset_index(drop=True)
        print(f"Added missing ORCL prior row {orcl_row['filing_date']} ({len(orcl_row['text'])} chars)")
    else:
        print("ORCL FY2019 prior still not extractable")

    current.to_csv(args.current, index=False)
    prior.to_csv(args.prior, index=False)

    audit = pd.concat([audit_current, audit_prior], ignore_index=True)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(report_path, index=False)

    pairs_after = build_pairs(current, prior)
    comparison = pairs_before.merge(
        pairs_after,
        on=["ticker", "date", "accession_number"],
        how="outer",
        suffixes=("_before", "_after"),
    )
    comparison.to_csv(report_path.with_name("item1a_repair_pair_similarity.csv"), index=False)

    print(f"\nRows changed: {int(audit['changed'].sum())} of {len(audit)}")
    print(f"Empty new extractions (old text kept): {int(audit['extraction_empty'].sum())}")
    moved = comparison[
        (comparison["similarity_before"] - comparison["similarity_after"]).abs() > 0.01
    ]
    print(f"Pairs with similarity moved >0.01: {len(moved)} of {len(comparison)}")
    print(f"Audit written to {report_path}")


if __name__ == "__main__":
    main()
