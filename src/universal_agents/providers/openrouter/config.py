"""OpenRouter-specific configuration."""

import os
from dataclasses import dataclass, field

from ...core.config import APIConfig


@dataclass
class OpenRouterConfig(APIConfig):
    """Configuration for OpenRouter API agents."""

    provider_name: str = "openrouter"
    api_key: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""),
        repr=False,
    )
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "anthropic/claude-3-5-sonnet"
    fallback_models: list[str] = field(
        default_factory=lambda: [
            "nvidia/nemotron-3-super-120b-a12b:free",
            "deepseek/deepseek-chat-v3.1:free",
        ]
    )
    site_url: str = "http://localhost"
    site_name: str = "Universal Agents"


@dataclass
class OpenRouterDataConfig(OpenRouterConfig):
    """Configuration for OpenRouter data agents (extended thinking, longer timeout)."""

    timeout: int = 600
    max_tokens: int = 16384
    enable_thinking: bool = True
    thinking_budget: int = 10000
    fallback_models: list[str] = field(
        default_factory=lambda: [
            "deepseek/deepseek-chat-v3.0324:free",
            "google/gemma-2-9b-it:free",
            "anthropic/claude-3.5-sonnet",
        ]
    )
