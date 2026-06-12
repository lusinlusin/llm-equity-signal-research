from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DIFF_NUMERIC_FIELDS = (
    "diff_boilerplate_share",
    "diff_company_specific_positive",
    "diff_company_specific_negative",
    "diff_net_signal",
    "diff_confidence",
    "llm_diff_surprise_signal",
)


def _format_pct(value: float) -> str:
    if pd.isna(value):
        return "nan"
    return f"{value:.2%}"


def summarize_distribution(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in DIFF_NUMERIC_FIELDS:
        if column not in features.columns:
            continue
        values = pd.to_numeric(features[column], errors="coerce").dropna()
        if values.empty:
            continue

        counts = values.value_counts()
        rows.append(
            {
                "field": column,
                "n": int(values.shape[0]),
                "unique": int(values.nunique()),
                "mean": float(values.mean()),
                "std": float(values.std(ddof=1)) if values.shape[0] > 1 else 0.0,
                "min": float(values.min()),
                "p25": float(values.quantile(0.25)),
                "p50": float(values.quantile(0.50)),
                "p75": float(values.quantile(0.75)),
                "max": float(values.max()),
                "top_value": float(counts.index[0]),
                "top_count": int(counts.iloc[0]),
                "top_share": int(counts.iloc[0]) / values.shape[0],
            }
        )

    return pd.DataFrame(rows).set_index("field")


def build_decision(summary: pd.DataFrame, features: pd.DataFrame) -> tuple[str, list[str]]:
    """Gate the full run on dispersion, direction balance, and calibration-rule compliance.

    Unlike the de-anchored gate, a heavy zero bucket in `diff_net_signal` is the
    intended base rate, so concentration is only penalized on the combined signal.
    """
    reasons: list[str] = []

    net = pd.to_numeric(features.get("diff_net_signal"), errors="coerce").dropna()
    signal = pd.to_numeric(features.get("llm_diff_surprise_signal"), errors="coerce").dropna()
    gate_violation = pd.to_numeric(features.get("diff_gate_violation"), errors="coerce").dropna()

    if net.empty or signal.empty:
        return "do_not_full_run_yet", ["Missing diff_net_signal or llm_diff_surprise_signal values."]

    zero_share = float((net == 0).mean())
    nonzero = net[net != 0]
    negative_share = float((nonzero < 0).mean()) if not nonzero.empty else float("nan")
    nonzero_signal = signal[net.reindex(signal.index) != 0].dropna()
    nonzero_unique = int(nonzero_signal.nunique())
    signal_std = float(signal.std(ddof=1)) if signal.shape[0] > 1 else 0.0

    if zero_share < 0.20:
        reasons.append(
            f"Base-rate calibration ignored: only {zero_share:.0%} of net_signal values are 0, "
            "so the model is still scoring almost every filing."
        )
    if zero_share > 0.90:
        reasons.append(
            f"Model never commits: {zero_share:.0%} of net_signal values are 0, "
            "so the signal carries almost no information."
        )
    if not nonzero.empty and negative_share > 0.80:
        reasons.append(
            f"Negativity bias persists: {negative_share:.0%} of nonzero net_signal values are negative."
        )
    if not nonzero_signal.empty and nonzero_unique < max(3, int(len(nonzero_signal) * 0.50)):
        reasons.append(
            f"Nonzero signal has low uniqueness: {nonzero_unique} unique values out of "
            f"{len(nonzero_signal)} nonzero rows. A large zero bucket is the intended base "
            "rate, so uniqueness is only required among committed scores."
        )
    if signal_std < 0.40:
        reasons.append(f"Signal dispersion is low: std={signal_std:.3f}.")
    if not gate_violation.empty and float(gate_violation.mean()) > 0.20:
        reasons.append(
            f"Materiality gate ignored: {float(gate_violation.mean()):.0%} of rows set a nonzero "
            "net_signal without a qualifying company-specific change."
        )

    if reasons:
        return "do_not_full_run_yet", reasons
    return "pass_for_full_run", [
        "Dispersion, direction balance, and calibration-rule compliance pass the pilot thresholds."
    ]


def _per_year_summary(features: pd.DataFrame) -> pd.DataFrame:
    if "filing_date" not in features.columns or "llm_diff_surprise_signal" not in features.columns:
        return pd.DataFrame()
    frame = features.copy()
    frame["filing_year"] = pd.to_datetime(frame["filing_date"], format="mixed").dt.year
    frame["llm_diff_surprise_signal"] = pd.to_numeric(
        frame["llm_diff_surprise_signal"], errors="coerce"
    )
    grouped = frame.groupby("filing_year")["llm_diff_surprise_signal"]
    return pd.DataFrame(
        {
            "n": grouped.size(),
            "mean": grouped.mean(),
            "std": grouped.std(ddof=1),
        }
    )


def write_markdown_report(
    summary: pd.DataFrame,
    features: pd.DataFrame,
    output_path: str | Path,
    decision: str,
    reasons: list[str],
    title: str = "Round 6 Diff-Surprise Pilot Distribution Diagnostic",
) -> None:
    display = summary.copy()
    if "top_share" in display.columns:
        display["top_share"] = display["top_share"].map(
            lambda value: _format_pct(value) if pd.notna(value) else ""
        )

    lines = [
        f"# {title}",
        "",
        f"Decision: `{decision}`",
        "",
        "## Reasons",
        "",
        *[f"- {reason}" for reason in reasons],
        "",
        "## Numeric Distribution",
        "",
        display.to_markdown(),
        "",
    ]

    per_year = _per_year_summary(features)
    if not per_year.empty:
        lines.extend(
            [
                "## Signal Mean by Filing Year",
                "",
                per_year.round(3).to_markdown(),
                "",
            ]
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose diff-surprise LLM output distribution.")
    parser.add_argument("--input", required=True, help="Diff-surprise LLM feature CSV to diagnose.")
    parser.add_argument("--output-dir", default="reports/round6", help="Output directory for diagnostic files.")
    parser.add_argument("--prefix", default="round6_diff_surprise_pilot", help="Output file prefix.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features = pd.read_csv(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize_distribution(features)
    decision, reasons = build_decision(summary, features)
    summary.to_csv(output_dir / f"{args.prefix}_distribution_summary.csv")
    write_markdown_report(
        summary=summary,
        features=features,
        output_path=output_dir / f"{args.prefix}_distribution_diagnostic.md",
        decision=decision,
        reasons=reasons,
    )
    print(f"Decision: {decision}")
    for reason in reasons:
        print(f"- {reason}")


if __name__ == "__main__":
    main()
