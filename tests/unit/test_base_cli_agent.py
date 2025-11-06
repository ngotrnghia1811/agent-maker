"""Unit tests for base CLI agent."""

import asyncio

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from universal_agents.cli.base_cli_agent import BaseCLIAgent
from universal_agents.core.config import CLIConfig
from universal_agents.core.exceptions import CLIError


class ConcreteCLIAgent(BaseCLIAgent):
    """Concrete implementation for testing."""

    def _build_command(self, **kwargs) -> list[str]:
        return ["echo"]


class TestBaseCLIAgent:
    def make_agent(self, **kwargs) -> ConcreteCLIAgent:
        config = CLIConfig(
            provider_name="test-cli",
            command="echo",
            timeout=5,
            **kwargs,
        )
        return ConcreteCLIAgent(config)

    def test_build_prompt_no_history(self):
        agent = self.make_agent()
        prompt = agent._build_prompt("hello")
        assert "[Current Query]: hello" in prompt

    def test_build_prompt_with_history(self):
        agent = self.make_agent()
        from universal_agents.core.types import Message
        agent.history.add_turn(
            Message(role="user", content="prev question"),
            Message(role="assistant", content="prev answer"),
        )
        prompt = agent._build_prompt("new question")
        assert "USER: prev question" in prompt
        assert "ASSISTANT: prev answer" in prompt
        assert "[Current Query]: new question" in prompt

    def test_parse_output_strips(self):
        agent = self.make_agent()
        assert agent._parse_output("  hello world  \n") == "hello world"

    @pytest.mark.asyncio
    async def test_chat_success(self):
        agent = self.make_agent()

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"response text\n", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await agent.chat("hello")

        assert result == "response text"
        assert agent.history.turn_count == 1

    @pytest.mark.asyncio
    async def test_chat_failure_nonzero_exit(self):
        agent = self.make_agent()

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"error message")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(CLIError, match="exited with code 1"):
                await agent.chat("hello")

    @pytest.mark.asyncio
    async def test_chat_empty_response(self):
        agent = self.make_agent()

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(CLIError, match="empty response"):
                await agent.chat("hello")

    @pytest.mark.asyncio
    async def test_chat_command_not_found(self):
        agent = self.make_agent()

        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(CLIError, match="not found"):
                await agent.chat("hello")

    @pytest.mark.asyncio
    async def test_chat_timeout(self):
        config = CLIConfig(provider_name="test-cli", command="echo", timeout=1)
        agent = ConcreteCLIAgent(config)

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(CLIError, match="timed out"):
                await agent.chat("hello")
