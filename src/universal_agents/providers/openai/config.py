"""OpenAI-specific configuration."""

import os
from dataclasses import dataclass, field

from ...core.config import APIConfig


@dataclass
class OpenAIConfig(APIConfig):
    """Configuration for OpenAI API agents."""

    provider_name: str = "openai"
    api_key: str = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", ""),
        repr=False,
    )
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.4-mini-2026-03-17"
    max_completion_tokens: int | None = None  # Preferred over max_tokens for newer models


@dataclass
class OpenAIDataConfig(OpenAIConfig):
    """Configuration for OpenAI data agents (reasoning, structured output)."""

    timeout: int = 600
    max_tokens: int = 16384
    max_completion_tokens: int | None = None
    reasoning_effort: str | None = None  # none, minimal, low, medium, high, xhigh
    response_format: dict | None = None  # e.g. {"type": "json_object"}
