from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from src.llm.prompts import build_signal_extraction_messages
from src.llm.schema import LLMSignalValidationError, validate_llm_signal_payload


class DeepSeekAPIKeyMissing(RuntimeError):
    """Raised when DeepSeek extraction is requested without an API key."""


class DeepSeekResponseError(RuntimeError):
    """Raised when DeepSeek returns an empty or unparsable response."""


def _load_local_env() -> dict[str, str]:
    project_root = Path(__file__).resolve().parents[2]
    values: dict[str, str] = {}
    for filename in (".env.local", ".env"):
        path = project_root / filename
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str | None = None
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    temperature: float = 0.0
    max_tokens: int = 800
    timeout: float = 60.0
    max_input_chars: int = 12_000
    max_retries: int = 3
    retry_sleep_seconds: float = 2.0

    @classmethod
    def from_env(cls, model: str | None = None) -> "DeepSeekConfig":
        local_env = _load_local_env()
        return cls(
            api_key=os.environ.get("DEEPSEEK_API_KEY") or local_env.get("DEEPSEEK_API_KEY"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL") or local_env.get("DEEPSEEK_BASE_URL", cls.base_url),
            model=model or os.environ.get("DEEPSEEK_MODEL") or local_env.get("DEEPSEEK_MODEL", cls.model),
        )


class DeepSeekSignalExtractor:
    """Small OpenAI-compatible client for DeepSeek JSON signal extraction."""

    def __init__(self, config: DeepSeekConfig | None = None) -> None:
        self.config = config or DeepSeekConfig.from_env()

    def extract_signal(
        self,
        ticker: str,
        filing_date: str,
        text: str,
    ) -> dict[str, float | str]:
        if not self.config.api_key:
            raise DeepSeekAPIKeyMissing(
                "DEEPSEEK_API_KEY is required for real DeepSeek extraction. "
                "Use --mock to run the local dry-run path without an API key."
            )

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
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.config.model,
                    messages=build_signal_extraction_messages(
                        ticker=ticker,
                        filing_date=filing_date,
                        text=text,
                        max_chars=self.config.max_input_chars,
                    ),
                    response_format={"type": "json_object"},
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )

                content = response.choices[0].message.content
                if not content:
                    raise DeepSeekResponseError("DeepSeek returned an empty response.")

                try:
                    payload = json.loads(content)
                except json.JSONDecodeError as exc:
                    raise DeepSeekResponseError("DeepSeek response was not valid JSON.") from exc

                return validate_llm_signal_payload(payload)
            except (DeepSeekResponseError, LLMSignalValidationError) as exc:
                last_error = exc
                if attempt == self.config.max_retries:
                    break
                time.sleep(self.config.retry_sleep_seconds * attempt)

        raise DeepSeekResponseError(f"DeepSeek extraction failed after retries: {last_error}")
