"""GPT-specific configuration."""

import os
from dataclasses import dataclass, field

from ...core.config import BrowserConfig


@dataclass
class GPTConfig(BrowserConfig):
    """Configuration for GPT browser agents."""

    provider_name: str = "gpt"
    base_url: str = "https://chatgpt.com"
    storage_state: str = field(
        default_factory=lambda: os.getenv("GPT_STORAGE_STATE", "")
    )
