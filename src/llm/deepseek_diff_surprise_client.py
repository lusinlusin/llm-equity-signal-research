from __future__ import annotations

import dataclasses
import json
import time

from src.features.risk_section_diff import RiskSectionDiff, format_diff_for_prompt
from src.llm.deepseek_client import DeepSeekConfig, DeepSeekResponseError
from src.llm.diff_surprise_prompts import build_diff_surprise_messages
from src.llm.diff_surprise_schema import (
    DiffSurpriseSignalValidationError,
    validate_diff_surprise_payload,
)


# The evidence list plus scores needs more room than the flat-score prompts.
DIFF_SURPRISE_MAX_TOKENS = 1_600


class DeepSeekDiffSurpriseExtractor:
    """OpenAI-compatible DeepSeek client for diff-based investable-surprise extraction."""

    def __init__(self, config: DeepSeekConfig | None = None) -> None:
        config = config or DeepSeekConfig.from_env()
        if config.max_tokens < DIFF_SURPRISE_MAX_TOKENS:
            config = dataclasses.replace(config, max_tokens=DIFF_SURPRISE_MAX_TOKENS)
        self.config = config

    def extract_signal(self, sector: str, diff: RiskSectionDiff) -> dict[str, float | str]:
        if not self.config.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for diff-surprise DeepSeek extraction.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("Install dependencies with: python3 -m pip install -r requirements.txt") from exc

        client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

        sections = format_diff_for_prompt(diff, max_total_chars=self.config.max_input_chars)
        last_error: Exception | None = None
        max_attempts = max(self.config.max_retries, 6)
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=build_diff_surprise_messages(
                        sector=sector,
                        added_text=sections["added"],
                        removed_text=sections["removed"],
                        modified_text=sections["modified"],
                        similarity=diff.similarity,
                        n_added=len(diff.added),
                        n_removed=len(diff.removed),
                        n_modified=len(diff.modified),
                    ),
                    response_format={"type": "json_object"},
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )

                content = response.choices[0].message.content
                if not content:
                    raise DeepSeekResponseError("DeepSeek returned an empty diff-surprise response.")

                try:
                    payload = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise DeepSeekResponseError("DeepSeek diff-surprise response was not valid JSON.") from exc

                return validate_diff_surprise_payload(payload)
            except (DeepSeekResponseError, DiffSurpriseSignalValidationError) as exc:
                last_error = exc
                if attempt == max_attempts:
                    break
                time.sleep(self.config.retry_sleep_seconds * attempt)

        raise DeepSeekResponseError(f"DeepSeek diff-surprise extraction failed after retries: {last_error}")
