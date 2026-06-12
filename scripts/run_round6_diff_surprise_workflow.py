from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.analysis.compare_round5_soundness import run_round5_soundness_comparison
from src.analysis.diagnose_diff_surprise_distribution import (
    build_decision,
    summarize_distribution,
    write_markdown_report,
)
from src.llm.deepseek_client import DeepSeekConfig
from src.llm.extract_diff_surprise_signals import extract_diff_surprise_features


DIFF_SURPRISE_CHANGE_NOTES = (
    "- The LLM no longer reads two clipped raw filings; a deterministic block diff is computed first and only changed sections are scored.",
    "- The prompt asks for company-specific investable surprise with an explicit base-rate rule: most filings should score 0.",
    "- Market-wide and sector-wide changes are classified as diagnostics and may not move the score.",
    "- Scores use integer scales with no numeric example anchors; ticker, company name, and dates are withheld from the prompt.",
    "- Evaluation reuses the Round 5 framework: fractional boundary ties and a persistent sector/size-neutralized random baseline.",
)


def _diagnose(input_path: Path, output_dir: Path, prefix: str, title: str) -> tuple[str, list[str]]:
    import pandas as pd

    features = pd.read_csv(input_path)
    summary = summarize_distribution(features)
    decision, reasons = build_decision(summary, features)
    summary.to_csv(output_dir / f"{prefix}_distribution_summary.csv")
    write_markdown_report(
        summary=summary,
        features=features,
        output_path=output_dir / f"{prefix}_distribution_diagnostic.md",
        decision=decision,
        reasons=reasons,
        title=title,
    )
    return decision, reasons


def _write_status(output_dir: Path, lines: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "round6_diff_surprise_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Round 6 diff-surprise prompt pilot and optional full run.")
    parser.add_argument("--input", default="data/raw/sec_10k_risk_factors.csv", help="Current SEC filing CSV.")
    parser.add_argument("--metadata", default="data/raw/ticker_metadata.csv", help="Ticker metadata CSV.")
    parser.add_argument("--prior-context", default="data/raw/sec_10k_risk_factors_prior_context.csv", help="Prior SEC filing CSV.")
    parser.add_argument("--sample-keys", default="reports/round6/round6_pilot_sample_keys.csv", help="Pilot sample key CSV.")
    parser.add_argument("--pilot-output", default="data/processed/llm_diff_surprise_features_pilot.csv", help="Pilot LLM output CSV.")
    parser.add_argument("--full-output", default="data/processed/llm_diff_surprise_features_deepseek.csv", help="Full LLM output CSV.")
    parser.add_argument("--output-dir", default="reports/round6", help="Round 6 report directory.")
    parser.add_argument("--model", default=None, help="Optional DeepSeek model override.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep after each LLM row.")
    parser.add_argument("--start", default="2020-01-01", help="Backtest start date.")
    parser.add_argument("--end", default="2026-01-01", help="Backtest end date.")
    parser.add_argument("--n-trials", type=int, default=500, help="Random baseline trial count.")
    parser.add_argument("--force-full", action="store_true", help="Run full extraction even if pilot diagnostic fails.")
    parser.add_argument("--skip-pilot", action="store_true", help="Skip the pilot and go straight to the full run.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = DeepSeekConfig.from_env(model=args.model)
    if not config.api_key:
        _write_status(
            output_dir,
            [
                "# Round 6 Diff-Surprise Status",
                "",
                "Current status: prepared but not run, because the current environment does not have `DEEPSEEK_API_KEY`.",
                "",
                "Create `.env.local` at the project root with:",
                "",
                "```text",
                "DEEPSEEK_API_KEY=your_key_here",
                "DEEPSEEK_MODEL=deepseek-v4-flash",
                "```",
                "",
                "Then rerun:",
                "",
                "```bash",
                "python3 scripts/run_round6_diff_surprise_workflow.py",
                "```",
            ],
        )
        raise RuntimeError("DEEPSEEK_API_KEY is required for Round 6 diff-surprise extraction.")

    pilot_decision = "skipped"
    pilot_reasons: list[str] = []
    if not args.skip_pilot:
        print("Running Round 6 diff-surprise pilot extraction...")
        extract_diff_surprise_features(
            input_path=args.input,
            metadata_path=args.metadata,
            prior_context_path=args.prior_context,
            sample_keys_path=args.sample_keys,
            output_path=args.pilot_output,
            model=args.model,
            resume=True,
            sleep_seconds=args.sleep,
        )

        print("Diagnosing Round 6 diff-surprise pilot distribution...")
        pilot_decision, pilot_reasons = _diagnose(
            input_path=Path(args.pilot_output),
            output_dir=output_dir,
            prefix="round6_diff_surprise_pilot",
            title="Round 6 Diff-Surprise Pilot Distribution Diagnostic",
        )
        print(f"Pilot decision: {pilot_decision}")
        for reason in pilot_reasons:
            print(f"- {reason}")

        if pilot_decision != "pass_for_full_run" and not args.force_full:
            _write_status(
                output_dir,
                [
                    "# Round 6 Diff-Surprise Status",
                    "",
                    "Current status: pilot completed, but full run was not started.",
                    "",
                    f"Pilot decision: `{pilot_decision}`",
                    "",
                    "Reasons:",
                    "",
                    *[f"- {reason}" for reason in pilot_reasons],
                ],
            )
            return

    print("Running full Round 6 diff-surprise extraction...")
    extract_diff_surprise_features(
        input_path=args.input,
        metadata_path=args.metadata,
        prior_context_path=args.prior_context,
        output_path=args.full_output,
        model=args.model,
        resume=True,
        sleep_seconds=args.sleep,
    )

    print("Diagnosing full Round 6 diff-surprise distribution...")
    full_decision, full_reasons = _diagnose(
        input_path=Path(args.full_output),
        output_dir=output_dir,
        prefix="round6_diff_surprise_full",
        title=(
            "Round 6 Diff-Surprise Full-Output Distribution Diagnostic "
            "(quality warning only; the full run is complete and is not invalidated)"
        ),
    )

    print("Running Round 6 diff-surprise backtest comparison...")
    results = run_round5_soundness_comparison(
        yoy_features_path=args.full_output,
        output_dir=args.output_dir,
        start=args.start,
        end=args.end,
        n_trials=args.n_trials,
        artifact_prefix="round6_diff_surprise",
        signal_prefix="round6_diff",
        report_title="Round 6 Diff-Surprise YoY Prompt Comparison",
        extraction_note=(
            "This round extracts new DeepSeek features from deterministic year-over-year "
            "Item 1A diffs using the investable-surprise prompt. "
            f"Full-output distribution diagnostic: `{full_decision}` — this is a quality "
            "warning about coarse committed-score buckets, not a run invalidation; the "
            "backtest below uses the complete 211-row output."
        ),
        yoy_signal_column="llm_diff_surprise_signal",
        yoy_signal_label="deepseek_diff_surprise_signal",
        yoy_neutral_label="deepseek_diff_surprise_sector_size_neutral",
        change_notes=DIFF_SURPRISE_CHANGE_NOTES,
        llm_api_rerun="yes (diff-surprise DeepSeek extraction)",
    )

    _write_status(
        output_dir,
        [
            "# Round 6 Diff-Surprise Status",
            "",
            "Current status: full Round 6 diff-surprise run completed.",
            "",
            f"Pilot decision: `{pilot_decision}`",
            f"Full-output diagnostic decision: `{full_decision}`",
            "",
            "Full-output diagnostic reasons:",
            "",
            *[f"- {reason}" for reason in full_reasons],
            "",
            "Key output files:",
            "",
            "- `data/processed/llm_diff_surprise_features_deepseek.csv`",
            "- `reports/round6/round6_diff_surprise_metrics.csv`",
            "- `reports/round6/round6_diff_surprise_comparison.md`",
        ],
    )

    print(results["coverage"].to_string())
    print(results["metrics"].round(4).to_string())
    print(results["significance"].round(4).to_string())


if __name__ == "__main__":
    main()
