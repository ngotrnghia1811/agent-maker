"""Integration tests for the monitor system — multi-agent scenarios."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from universal_agents.core.types import AgentStats
from universal_agents.monitor.agent_registry import AgentRegistry
from universal_agents.monitor.dashboard import Dashboard
from universal_agents.monitor.events import EventBus, EventType
from universal_agents.monitor.monitored_agent import MonitoredAgent
from universal_agents.monitor.reporter import Reporter


def _make_agent(provider="claude", session_id="test-id", response="ok"):
    agent = AsyncMock()
    agent.session_id = session_id
    agent.config = MagicMock()
    agent.config.provider_name = provider
    agent.chat = AsyncMock(return_value=response)
    agent.get_stats = MagicMock(return_value=AgentStats(
        session_id=session_id, provider=provider, total_turns=0,
    ))
    agent.get_turns = MagicMock(return_value=[])
    agent.get_history = MagicMock(return_value=[])
    agent.history = MagicMock()
    agent.history.turn_count = 0
    agent.close = AsyncMock()
    return agent


class TestMonitorIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow_register_chat_report(self):
        """Register agents, run monitored chats, generate report."""
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        reporter = Reporter(registry)

        a1 = _make_agent(provider="claude", session_id="c1", response="Claude says hi")
        a2 = _make_agent(provider="gpt", session_id="g1", response="GPT says hi")

        registry.register(a1)
        registry.register(a2)

        m1 = MonitoredAgent(a1, bus)
        m2 = MonitoredAgent(a2, bus)

        r1 = await m1.chat("Hello Claude")
        r2 = await m2.chat("Hello GPT")

        assert r1 == "Claude says hi"
        assert r2 == "GPT says hi"

        summary = reporter.summary()
        assert summary["agent_count"] == 2
        assert summary["total_turns"] == 2
        assert summary["successful_turns"] == 2
        assert summary["failed_turns"] == 0

    @pytest.mark.asyncio
    async def test_mixed_success_and_failure(self):
        """Some turns succeed, some fail — reporter tracks both."""
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        reporter = Reporter(registry)

        agent = _make_agent(provider="claude", session_id="c1")
        call_count = 0

        async def flaky_chat(msg, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("rate limited")
            return "ok"

        agent.chat = AsyncMock(side_effect=flaky_chat)
        registry.register(agent)
        monitored = MonitoredAgent(agent, bus)

        await monitored.chat("turn 1")
        with pytest.raises(RuntimeError):
            await monitored.chat("turn 2")
        await monitored.chat("turn 3")

        report = reporter.get_report("c1")
        assert report.total_turns == 3
        assert report.successful_turns == 2
        assert report.failed_turns == 1
        assert len(report.errors) == 1

    @pytest.mark.asyncio
    async def test_dashboard_tracks_events(self):
        """Dashboard updates its status tracking as events flow."""
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        dashboard = Dashboard(registry)

        agent = _make_agent(provider="gemini", session_id="ge1")
        registry.register(agent)

        assert dashboard._agent_status["ge1"] == "registered"

        monitored = MonitoredAgent(agent, bus)
        await monitored.chat("test")

        assert dashboard._agent_status["ge1"] == "idle"
        assert dashboard._agent_latencies["ge1"] > 0

    @pytest.mark.asyncio
    async def test_close_all_cleans_up(self):
        """close_all closes all agents and emits events."""
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        dashboard = Dashboard(registry)

        a1 = _make_agent(session_id="c1", provider="claude")
        a2 = _make_agent(session_id="g1", provider="gpt")
        registry.register(a1)
        registry.register(a2)

        await registry.close_all()

        assert len(registry.agents) == 0
        a1.close.assert_awaited_once()
        a2.close.assert_awaited_once()
        assert dashboard._agent_status.get("c1") == "closed"
        assert dashboard._agent_status.get("g1") == "closed"

    @pytest.mark.asyncio
    async def test_three_agents_concurrent(self):
        """Run 3 agents concurrently with monitoring (plan exit criteria)."""
        import asyncio

        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        reporter = Reporter(registry)

        agents = []
        monitored_agents = []
        for i, provider in enumerate(["claude", "gpt", "gemini"]):
            a = _make_agent(provider=provider, session_id=f"{provider}-1", response=f"{provider} response")
            registry.register(a)
            m = MonitoredAgent(a, bus)
            agents.append(a)
            monitored_agents.append(m)

        # Run concurrently
        results = await asyncio.gather(
            monitored_agents[0].chat("q1"),
            monitored_agents[1].chat("q2"),
            monitored_agents[2].chat("q3"),
        )

        assert results == ["claude response", "gpt response", "gemini response"]

        summary = reporter.summary()
        assert summary["agent_count"] == 3
        assert summary["total_turns"] == 3
        assert summary["successful_turns"] == 3

        text = reporter.print_report()
        assert "claude" in text
        assert "gpt" in text
        assert "gemini" in text
