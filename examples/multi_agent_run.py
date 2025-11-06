"""Multi-agent concurrent run with monitoring and reporting."""

import asyncio

from universal_agents.monitor import AgentRegistry, Dashboard, MonitoredAgent, Reporter
from universal_agents.providers.claude.chat import ClaudeChatAgent
from universal_agents.providers.claude.config import ClaudeConfig
from universal_agents.providers.openrouter.chat import OpenRouterChatAgent
from universal_agents.providers.openrouter.config import OpenRouterConfig


async def main():
    # Set up monitoring
    registry = AgentRegistry()
    reporter = Reporter(registry)

    # Create agents
    claude = ClaudeChatAgent(ClaudeConfig())
    openrouter = OpenRouterChatAgent(OpenRouterConfig(
        api_key="your-api-key",  # or set OPENROUTER_API_KEY env var
        model="anthropic/claude-sonnet-4",
    ))

    # Register
    registry.register(claude)
    registry.register(openrouter)

    # Wrap for event monitoring
    m_claude = MonitoredAgent(claude, registry.event_bus)
    m_openrouter = MonitoredAgent(openrouter, registry.event_bus)

    question = "Explain the difference between async and threading in Python"

    # Run concurrently
    try:
        results = await asyncio.gather(
            m_claude.chat(question),
            m_openrouter.chat(question),
            return_exceptions=True,
        )

        # Print results
        for agent_info, result in zip(registry.list_agents(), results):
            provider = agent_info["provider"]
            if isinstance(result, Exception):
                print(f"\n[{provider}] ERROR: {result}")
            else:
                print(f"\n[{provider}] {result[:300]}...")
    finally:
        # Generate report
        print("\n" + reporter.print_report())
        reporter.save_report("run_report.json")

        # Clean up
        await registry.close_all()


if __name__ == "__main__":
    asyncio.run(main())
