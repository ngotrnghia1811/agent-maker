"""Abstract base class for CLI subprocess agents."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from ..core.base_agent import BaseChatAgent
from ..core.config import CLIConfig
from ..core.exceptions import CLIError
from ..core.types import Message

logger = logging.getLogger(__name__)


class BaseCLIAgent(BaseChatAgent):
    """Shared logic for CLI subprocess chat agents.

    Subclasses must set:
      - _build_command(): returns the command argument list
      - _build_prompt(): transforms the message into CLI input

    Subclasses may override:
      - _parse_output(): post-process raw CLI output
    """

    def __init__(self, config: CLIConfig):
        super().__init__(config)
        self.cli_config = config

    def _build_command(self, **kwargs) -> list[str]:
        """Build the CLI command. Override in subclasses."""
        if not self.cli_config.command:
            raise CLIError("No command configured")
        return self.cli_config.command.split()

    def _build_prompt(self, message: str) -> str:
        """Build the full prompt to send via stdin, including history context."""
        parts: list[str] = []

        # Recent conversation context
        recent = self.history.get_messages_for_context()
        if recent:
            parts.append("[Recent Conversation]:")
            for msg in recent:
                parts.append(f"{msg['role'].upper()}: {msg['content'][:500]}")

        parts.append(f"\n[Current Query]: {message}")
        return "\n".join(parts)

    def _parse_output(self, raw_output: str) -> str:
        """Post-process CLI output. Override for custom parsing."""
        return raw_output.strip()

    async def chat(self, message: str, **kwargs) -> str:
        """Send a message via CLI subprocess and return the response."""
        start = time.monotonic()

        cmd = self._build_command(**kwargs)
        prompt = self._build_prompt(message)
        cwd = self.cli_config.working_dir or None

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=self.cli_config.timeout,
            )
        except asyncio.TimeoutError:
            raise CLIError(f"CLI command timed out after {self.cli_config.timeout}s")
        except FileNotFoundError:
            raise CLIError(f"CLI command not found: {cmd[0]}")

        if proc.returncode != 0:
            error_msg = stderr.decode().strip() or stdout.decode().strip() or "Unknown error"
            raise CLIError(f"CLI exited with code {proc.returncode}: {error_msg}")

        raw = stdout.decode()
        response = self._parse_output(raw)

        if not response:
            raise CLIError("CLI returned empty response")

        elapsed_ms = (time.monotonic() - start) * 1000
        now = datetime.now()
        user_msg = Message(role="user", content=message, timestamp=now)
        assistant_msg = Message(role="assistant", content=response, timestamp=now)
        self.history.add_turn(
            user_message=user_msg,
            assistant_message=assistant_msg,
            processing_time_ms=elapsed_ms,
        )

        logger.info(
            "Turn %d completed in %.0fms (%d chars)",
            self.history.turn_count,
            elapsed_ms,
            len(response),
        )
        return response

    async def close(self) -> None:
        """No resources to clean up for CLI agents."""
