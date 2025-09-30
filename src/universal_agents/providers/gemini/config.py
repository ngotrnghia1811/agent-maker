"""Gemini-specific configuration."""

import os
from dataclasses import dataclass, field

from ...core.config import BrowserConfig


@dataclass
class GeminiConfig(BrowserConfig):
    """Configuration for Gemini browser agents."""

    provider_name: str = "gemini"
    base_url: str = "https://gemini.google.com"
    storage_state: str = field(
        default_factory=lambda: os.getenv("GEMINI_STORAGE_STATE", "")
    )
    extract_thinking: bool = True
    required_model: str | None = None  # e.g. "pro", "flash", "thinking"


@dataclass
class GeminiDataConfig(GeminiConfig):
    """Configuration for Gemini data generation agents (longer timeout)."""

    timeout: int = 300
    extract_thinking: bool = True


@dataclass
class GeminiTranslatorConfig(GeminiDataConfig):
    """Configuration for Gemini translator agents."""

    timeout: int = 600
    max_turns_per_conversation: int = 20
    source_language: str = "ja"
    target_language: str = "en"
    translation_mode: str = "book"  # "book" or "transcript"
    chunk_size: int = 2000
    overlap_chars: int = 100
