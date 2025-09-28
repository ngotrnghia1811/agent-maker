"""Claude-specific configuration."""

import os
from dataclasses import dataclass, field

from ...core.config import BrowserConfig


@dataclass
class ClaudeConfig(BrowserConfig):
    """Configuration for Claude browser agents."""

    provider_name: str = "claude"
    base_url: str = "https://claude.ai/new"
    storage_state: str = field(
        default_factory=lambda: os.getenv("CLAUDE_STORAGE_STATE", "")
    )
    extract_thinking: bool = True


@dataclass
class ClaudeDataConfig(ClaudeConfig):
    """Configuration for Claude data generation agents (longer timeout)."""

    timeout: int = 300
    extract_thinking: bool = True


@dataclass
class ClaudeTranslatorConfig(ClaudeDataConfig):
    """Configuration for Claude translator agents."""

    timeout: int = 600
    max_turns_per_conversation: int = 20
    source_language: str = "ja"
    target_language: str = "en"
    translation_mode: str = "book"  # "book" or "transcript"
    chunk_size: int = 2000
    overlap_chars: int = 100
