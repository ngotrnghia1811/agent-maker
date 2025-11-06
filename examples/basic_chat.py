"""Basic single-agent chat example."""

import asyncio

from universal_agents.providers.claude.chat import ClaudeChatAgent
from universal_agents.providers.claude.config import ClaudeConfig


async def main():
    config = ClaudeConfig(
        # Set CLAUDE_STORAGE_STATE env var or pass path here
        # storage_state="/path/to/storage_state.json",
    )

    async with ClaudeChatAgent(config) as agent:
        response = await agent.chat("What is the capital of France?")
        print(f"Response: {response}")

        response = await agent.chat("What about Germany?")
        print(f"Follow-up: {response}")

        stats = agent.get_stats()
        print(f"\nStats: {stats.total_turns} turns, avg {stats.avg_processing_time_ms:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
