from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.analysis.compare_round5_soundness import (
    DEFAULT_ABSOLUTE_LLM_FEATURES,
    DEFAULT_METADATA,
    run_round5_soundness_comparison,
)
from src.pipeline import DEFAULT_TEXT_DATA_PATH


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEANCHORED_YOY_FEATURES = PROJECT_ROOT / "data/processed/llm_yoy_relative_features_deanchored_deepseek.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports/round6"


def run_round6_deanchored_comparison(
    yoy_features_path: str | Path = DEFAULT_DEANCHORED_YOY_FEATURES,
    absolute_llm_features_path: str | Path = DEFAULT_ABSOLUTE_LLM_FEATURES,
    text_data_path: str | Path = DEFAULT_TEXT_DATA_PATH,
    metadata_path: str | Path = DEFAULT_METADATA,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    start: str = "2020-01-01",
    end: str | None = "2026-01-01",
    seed: int = 42,
    n_trials: int = 500,
    synthetic: bool = False,
) -> dict[str, pd.DataFrame | pd.Series]:
    return run_round5_soundness_comparison(
        yoy_features_path=yoy_features_path,
        absolute_llm_features_path=absolute_llm_features_path,
        text_data_path=text_data_path,
        metadata_path=metadata_path,
        output_dir=output_dir,
        start=start,
        end=end,
        seed=seed,
        n_trials=n_trials,
        synthetic=synthetic,
        artifact_prefix="round6_deanchored",
        signal_prefix="round6",
        report_title="Round 6 De-Anchored YoY Prompt Comparison",
        extraction_note=(
            "This round uses newly extracted de-anchored YoY DeepSeek features "
            "after the pilot distribution diagnostic passes."
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Round 6 de-anchored YoY prompt comparison.")
    parser.add_argument("--yoy-features", default=str(DEFAULT_DEANCHORED_YOY_FEATURES), help="CSV with new de-anchored llm_yoy_relative_signal.")
    parser.add_argument("--absolute-llm-features", default=str(DEFAULT_ABSOLUTE_LLM_FEATURES), help="CSV with old absolute llm_text_signal.")
    parser.add_argument("--text-data", default=str(DEFAULT_TEXT_DATA_PATH), help="Raw text CSV for dictionary signals.")
    parser.add_argument("--metadata", default=str(DEFAULT_METADATA), help="Ticker metadata CSV.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for comparison artifacts.")
    parser.add_argument("--start", default="2020-01-01", help="Start date for prices.")
    parser.add_argument("--end", default="2026-01-01", help="Optional end date for prices.")
    parser.add_argument("--seed", type=int, default=42, help="Single persistent random baseline seed.")
    parser.add_argument("--n-trials", type=int, default=500, help="Monte Carlo random baseline trials.")
    parser.add_argument("--synthetic", action="store_true", help="Use synthetic prices for offline checks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = run_round6_deanchored_comparison(
        yoy_features_path=args.yoy_features,
        absolute_llm_features_path=args.absolute_llm_features,
        text_data_path=args.text_data,
        metadata_path=args.metadata,
        output_dir=args.output_dir,
        start=args.start,
        end=args.end,
        seed=args.seed,
        n_trials=args.n_trials,
        synthetic=args.synthetic,
    )
    print("Round 6 de-anchored comparison complete")
    print(results["coverage"].to_string())
    print(results["metrics"].round(4).to_string())
    print(results["significance"].round(4).to_string())


if __name__ == "__main__":
    main()
