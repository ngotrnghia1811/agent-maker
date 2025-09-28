"""Copilot-specific configuration."""

from dataclasses import dataclass, field

from ...core.config import CLIConfig


@dataclass
class CopilotConfig(CLIConfig):
    """Configuration for GitHub Copilot CLI agents."""

    provider_name: str = "copilot"
    command: str = "copilot"
    timeout: int = 60
    max_history_turns: int = 10
    system_prompt: str = ""
    allow_all_tools: bool = False
    allowed_tools: list[str] = field(default_factory=list)
    denied_tools: list[str] = field(default_factory=list)
