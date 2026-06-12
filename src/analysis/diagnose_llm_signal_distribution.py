from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


YOY_ANCHORS = {
    "yoy_risk_change_score": -0.40,
    "yoy_new_material_risk_score": 0.60,
    "yoy_risk_mitigation_score": 0.20,
    "yoy_peer_relative_risk_score": -0.30,
    "yoy_direction_score": -1.00,
    "yoy_confidence": 0.70,
}

YOY_NUMERIC_FIELDS = tuple(YOY_ANCHORS) + ("llm_yoy_relative_signal",)


def _format_pct(value: float) -> str:
    if pd.isna(value):
        return "nan"
    return f"{value:.2%}"


def summarize_distribution(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in YOY_NUMERIC_FIELDS:
        if column not in features.columns:
            continue
        values = pd.to_numeric(features[column], errors="coerce").dropna()
        if values.empty:
            continue

        counts = values.value_counts()
        top_value = counts.index[0]
        top_count = int(counts.iloc[0])
        row = {
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
            "top_value": float(top_value),
            "top_count": top_count,
            "top_share": top_count / values.shape[0],
            "old_anchor": YOY_ANCHORS.get(column),
            "old_anchor_count": pd.NA,
            "old_anchor_share": pd.NA,
        }
        if column in YOY_ANCHORS:
            anchor_count = int((values == YOY_ANCHORS[column]).sum())
            row["old_anchor_count"] = anchor_count
            row["old_anchor_share"] = anchor_count / values.shape[0]
        rows.append(row)

    return pd.DataFrame(rows).set_index("field")


def build_decision(summary: pd.DataFrame) -> tuple[str, list[str]]:
    reasons = []
    score_fields = [field for field in YOY_ANCHORS if field in summary.index and field != "yoy_direction_score"]
    high_anchor_fields = [
        field for field in score_fields
        if pd.notna(summary.loc[field, "old_anchor_share"]) and summary.loc[field, "old_anchor_share"] > 0.35
    ]
    high_top_fields = [
        field for field in score_fields
        if summary.loc[field, "top_share"] > 0.45
    ]

    signal_unique = summary.loc["llm_yoy_relative_signal", "unique"] if "llm_yoy_relative_signal" in summary.index else 0
    signal_std = summary.loc["llm_yoy_relative_signal", "std"] if "llm_yoy_relative_signal" in summary.index else 0.0
    n = summary.loc["llm_yoy_relative_signal", "n"] if "llm_yoy_relative_signal" in summary.index else 0

    if high_anchor_fields:
        reasons.append(f"Old-anchor share is still high for: {', '.join(high_anchor_fields)}.")
    if high_top_fields:
        reasons.append(f"Top-value concentration is high for: {', '.join(high_top_fields)}.")
    if n and signal_unique < min(15, n * 0.50):
        reasons.append(f"Signal has low uniqueness: {signal_unique:.0f} unique values out of {n:.0f} rows.")
    if signal_std < 0.50:
        reasons.append(f"Signal dispersion is low: std={signal_std:.3f}.")

    if reasons:
        return "do_not_full_run_yet", reasons
    return "pass_for_full_run", ["Anchor concentration and signal dispersion pass the pilot thresholds."]


def write_markdown_report(
    summary: pd.DataFrame,
    features: pd.DataFrame,
    output_path: str | Path,
    decision: str,
    reasons: list[str],
) -> None:
    display = summary.copy()
    for column in ("top_share", "old_anchor_share"):
        if column in display.columns:
            display[column] = display[column].map(lambda value: _format_pct(value) if pd.notna(value) else "")
    if "yoy_impact_label" in features.columns:
        label_counts = features["yoy_impact_label"].value_counts(dropna=False).to_frame("count")
    else:
        label_counts = pd.DataFrame()

    lines = [
        "# Round 6 Pilot Distribution Diagnostic",
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
    if not label_counts.empty:
        lines.extend(
            [
                "## Impact Label Distribution",
                "",
                label_counts.to_markdown(),
                "",
            ]
        )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose YoY LLM output distribution and anchoring.")
    parser.add_argument("--input", required=True, help="YoY LLM feature CSV to diagnose.")
    parser.add_argument("--output-dir", default="reports/round6", help="Output directory for diagnostic files.")
    parser.add_argument("--prefix", default="round6_pilot", help="Output file prefix.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    features = pd.read_csv(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = summarize_distribution(features)
    decision, reasons = build_decision(summary)
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
