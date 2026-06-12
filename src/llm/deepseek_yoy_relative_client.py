from __future__ import annotations

import json
import time

from src.llm.deepseek_client import DeepSeekConfig, DeepSeekResponseError
from src.llm.yoy_relative_prompts import build_yoy_relative_messages
from src.llm.yoy_relative_schema import (
    YOYRelativeSignalValidationError,
    validate_yoy_relative_payload,
)


class DeepSeekYOYRelativeExtractor:
    """OpenAI-compatible DeepSeek client for current-vs-prior filing signal extraction."""

    def __init__(self, config: DeepSeekConfig | None = None) -> None:
        self.config = config or DeepSeekConfig.from_env()

    def extract_signal(
        self,
        ticker: str,
        company_name: str,
        sector: str,
        current_filing_date: str,
        prior_filing_date: str,
        current_text: str,
        prior_text: str,
    ) -> dict[str, float | str]:
        if not self.config.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is required for YoY relative DeepSeek extraction.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("Install dependencies with: python3 -m pip install -r requirements.txt") from exc

        client = OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
        )

        last_error: Exception | None = None
        max_attempts = max(self.config.max_retries, 6)
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=build_yoy_relative_messages(
                        ticker=ticker,
                        company_name=company_name,
                        sector=sector,
                        current_filing_date=current_filing_date,
                        prior_filing_date=prior_filing_date,
                        current_text=current_text,
                        prior_text=prior_text,
                        max_chars_per_filing=self.config.max_input_chars,
                    ),
                    response_format={"type": "json_object"},
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )

                content = response.choices[0].message.content
                if not content:
                    raise DeepSeekResponseError("DeepSeek returned an empty YoY relative response.")

                try:
                    payload = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise DeepSeekResponseError("DeepSeek YoY relative response was not valid JSON.") from exc

                return validate_yoy_relative_payload(payload)
            except (DeepSeekResponseError, YOYRelativeSignalValidationError) as exc:
                last_error = exc
                if attempt == max_attempts:
                    break
                time.sleep(self.config.retry_sleep_seconds * attempt)

        raise DeepSeekResponseError(f"DeepSeek YoY relative extraction failed after retries: {last_error}")
