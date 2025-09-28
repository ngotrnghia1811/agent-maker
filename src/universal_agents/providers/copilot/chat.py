"""Copilot CLI chat agent — subprocess wrapper for GitHub Copilot."""

import logging

from ...cli.base_cli_agent import BaseCLIAgent
from .config import CopilotConfig

logger = logging.getLogger(__name__)


class CopilotChatAgent(BaseCLIAgent):
    """GitHub Copilot CLI agent.

    Usage:
        async with CopilotChatAgent() as agent:
            response = await agent.chat("Explain this error: ...")
            print(response)
    """

    def __init__(self, config: CopilotConfig | None = None):
        super().__init__(config or CopilotConfig())
        self._copilot_config = self.cli_config  # type: CopilotConfig

    def _build_command(self, **kwargs) -> list[str]:
        """Build the copilot CLI command with tool flags."""
        cmd = ["copilot", "-I"]
        cfg = self._copilot_config
        if cfg.allow_all_tools:  # type: ignore[attr-defined]
            cmd.append("--allow-all-tools")
        return cmd

    def _build_prompt(self, message: str) -> str:
        """Build prompt with optional system prompt and conversation context."""
        parts: list[str] = []
        cfg = self._copilot_config

        if cfg.system_prompt:  # type: ignore[attr-defined]
            parts.append(f"[System Instructions]: {cfg.system_prompt}")  # type: ignore[attr-defined]

        recent = self.history.get_messages_for_context()
        if recent:
            parts.append("\n[Recent Conversation]:")
            for msg in recent:
                parts.append(f"{msg['role'].upper()}: {msg['content'][:500]}")

        parts.append(f"\n[Current Query]: {message}")
        return "\n".join(parts)
