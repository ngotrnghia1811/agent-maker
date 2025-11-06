"""Integration test for Claude chat agent.

Requires:
  - CLAUDE_STORAGE_STATE env var pointing to a valid storage state JSON
  - Playwright browsers installed

Run with: pytest tests/integration/ -m integration
"""

import pytest

from universal_agents.providers.claude.chat import ClaudeChatAgent
from universal_agents.providers.claude.config import ClaudeConfig


@pytest.mark.integration
class TestClaudeChatIntegration:
    @pytest.mark.asyncio
    async def test_single_turn(self):
        config = ClaudeConfig(headless=True)
        async with ClaudeChatAgent(config) as agent:
            response = await agent.chat("What is 2 + 2? Reply with just the number.")
            assert "4" in response
            assert agent.history.turn_count == 1

    @pytest.mark.asyncio
    async def test_multi_turn(self):
        config = ClaudeConfig(headless=True)
        async with ClaudeChatAgent(config) as agent:
            r1 = await agent.chat("My name is Alice. Remember that.")
            assert len(r1) > 0

            r2 = await agent.chat("What is my name?")
            assert "Alice" in r2
            assert agent.history.turn_count == 2

    @pytest.mark.asyncio
    async def test_thinking_extraction(self):
        config = ClaudeConfig(headless=True, extract_thinking=True)
        async with ClaudeChatAgent(config) as agent:
            await agent.chat("Explain why the sky is blue in one sentence.")
            turns = agent.get_turns()
            assert len(turns) == 1
            # Thinking may or may not be available depending on the model
            # Just verify the agent doesn't crash

    @pytest.mark.asyncio
    async def test_stats(self):
        config = ClaudeConfig(headless=True)
        async with ClaudeChatAgent(config) as agent:
            await agent.chat("Hello!")
            stats = agent.get_stats()
            assert stats.provider == "claude"
            assert stats.total_turns == 1
            assert stats.total_processing_time_ms > 0
