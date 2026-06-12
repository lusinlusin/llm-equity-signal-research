from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.analysis.compare_round6_deanchored import run_round6_deanchored_comparison
from src.analysis.diagnose_llm_signal_distribution import (
    build_decision,
    summarize_distribution,
    write_markdown_report,
)
from src.llm.deepseek_client import DeepSeekConfig
from src.llm.extract_yoy_relative_signals import extract_yoy_relative_features


def _diagnose(input_path: Path, output_dir: Path, prefix: str) -> tuple[str, list[str]]:
    import pandas as pd

    features = pd.read_csv(input_path)
    summary = summarize_distribution(features)
    decision, reasons = build_decision(summary)
    summary.to_csv(output_dir / f"{prefix}_distribution_summary.csv")
    write_markdown_report(
        summary=summary,
        features=features,
        output_path=output_dir / f"{prefix}_distribution_diagnostic.md",
        decision=decision,
        reasons=reasons,
    )
    return decision, reasons


def _write_status(output_dir: Path, lines: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "round6_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Round 6 de-anchored prompt pilot and optional full run.")
    parser.add_argument("--input", default="data/raw/sec_10k_risk_factors.csv", help="Current SEC filing CSV.")
    parser.add_argument("--metadata", default="data/raw/ticker_metadata.csv", help="Ticker metadata CSV.")
    parser.add_argument("--prior-context", default="data/raw/sec_10k_risk_factors_prior_context.csv", help="Prior SEC filing CSV.")
    parser.add_argument("--sample-keys", default="reports/round6/round6_pilot_sample_keys.csv", help="Pilot sample key CSV.")
    parser.add_argument("--pilot-output", default="data/processed/llm_yoy_relative_features_deanchored_pilot.csv", help="Pilot LLM output CSV.")
    parser.add_argument("--full-output", default="data/processed/llm_yoy_relative_features_deanchored_deepseek.csv", help="Full LLM output CSV.")
    parser.add_argument("--output-dir", default="reports/round6", help="Round 6 report directory.")
    parser.add_argument("--model", default=None, help="Optional DeepSeek model override.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep after each LLM row.")
    parser.add_argument("--start", default="2020-01-01", help="Backtest start date.")
    parser.add_argument("--end", default="2026-01-01", help="Backtest end date.")
    parser.add_argument("--n-trials", type=int, default=500, help="Random baseline trial count.")
    parser.add_argument("--force-full", action="store_true", help="Run full extraction even if pilot diagnostic fails.")
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
                "# Round 6 Status",
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
                "python3 scripts/run_round6_deanchored_workflow.py",
                "```",
            ],
        )
        raise RuntimeError("DEEPSEEK_API_KEY is required for Round 6 extraction.")

    print("Running Round 6 pilot extraction...")
    extract_yoy_relative_features(
        input_path=args.input,
        metadata_path=args.metadata,
        prior_context_path=args.prior_context,
        sample_keys_path=args.sample_keys,
        output_path=args.pilot_output,
        model=args.model,
        resume=True,
        sleep_seconds=args.sleep,
    )

    print("Diagnosing Round 6 pilot distribution...")
    pilot_decision, pilot_reasons = _diagnose(
        input_path=Path(args.pilot_output),
        output_dir=output_dir,
        prefix="round6_deanchored_pilot",
    )
    print(f"Pilot decision: {pilot_decision}")
    for reason in pilot_reasons:
        print(f"- {reason}")

    if pilot_decision != "pass_for_full_run" and not args.force_full:
        _write_status(
            output_dir,
            [
                "# Round 6 Status",
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

    print("Running full Round 6 de-anchored extraction...")
    extract_yoy_relative_features(
        input_path=args.input,
        metadata_path=args.metadata,
        prior_context_path=args.prior_context,
        output_path=args.full_output,
        model=args.model,
        resume=True,
        sleep_seconds=args.sleep,
    )

    print("Diagnosing full Round 6 de-anchored distribution...")
    full_decision, full_reasons = _diagnose(
        input_path=Path(args.full_output),
        output_dir=output_dir,
        prefix="round6_deanchored_full",
    )

    print("Running Round 6 backtest comparison...")
    results = run_round6_deanchored_comparison(
        yoy_features_path=args.full_output,
        metadata_path=args.metadata,
        output_dir=args.output_dir,
        start=args.start,
        end=args.end,
        n_trials=args.n_trials,
    )

    _write_status(
        output_dir,
        [
            "# Round 6 Status",
            "",
            "Current status: full Round 6 completed.",
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
            "- `data/processed/llm_yoy_relative_features_deanchored_deepseek.csv`",
            "- `reports/round6/round6_deanchored_metrics.csv`",
            "- `reports/round6/round6_deanchored_comparison.md`",
        ],
    )

    print(results["coverage"].to_string())
    print(results["metrics"].round(4).to_string())
    print(results["significance"].round(4).to_string())


if __name__ == "__main__":
    main()
