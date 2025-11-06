"""Tests for monitor/agent_registry.py — AgentRegistry."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from universal_agents.core.config import BaseConfig
from universal_agents.monitor.agent_registry import AgentRegistry
from universal_agents.monitor.events import EventBus, EventType


def _make_agent(provider="claude", session_id="test-id"):
    agent = AsyncMock()
    agent.session_id = session_id
    agent.config = MagicMock(spec=BaseConfig)
    agent.config.provider_name = provider
    agent.history = MagicMock()
    agent.history.turn_count = 0
    agent.close = AsyncMock()
    return agent


class TestAgentRegistry:
    def test_register_returns_session_id(self):
        registry = AgentRegistry()
        agent = _make_agent(session_id="abc-123")
        aid = registry.register(agent)
        assert aid == "abc-123"

    def test_register_emits_event(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventType.AGENT_REGISTERED, lambda e: events.append(e))
        registry = AgentRegistry(event_bus=bus)

        agent = _make_agent(provider="gemini", session_id="g1")
        registry.register(agent)

        assert len(events) == 1
        assert events[0].event_type == EventType.AGENT_REGISTERED
        assert events[0].agent_id == "g1"
        assert events[0].provider == "gemini"

    def test_get_returns_agent(self):
        registry = AgentRegistry()
        agent = _make_agent(session_id="x1")
        registry.register(agent)
        assert registry.get("x1") is agent

    def test_get_missing_raises(self):
        registry = AgentRegistry()
        with pytest.raises(KeyError):
            registry.get("nonexistent")

    def test_list_agents(self):
        registry = AgentRegistry()
        a1 = _make_agent(provider="claude", session_id="c1")
        a1.history.turn_count = 3
        a2 = _make_agent(provider="gpt", session_id="g1")
        a2.history.turn_count = 1
        registry.register(a1)
        registry.register(a2)

        listing = registry.list_agents()
        assert len(listing) == 2
        assert listing[0] == {"id": "c1", "provider": "claude", "turns": 3}
        assert listing[1] == {"id": "g1", "provider": "gpt", "turns": 1}

    @pytest.mark.asyncio
    async def test_close_all(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventType.AGENT_CLOSED, lambda e: events.append(e))
        registry = AgentRegistry(event_bus=bus)

        a1 = _make_agent(session_id="c1", provider="claude")
        a2 = _make_agent(session_id="g1", provider="gpt")
        registry.register(a1)
        registry.register(a2)

        await registry.close_all()

        a1.close.assert_awaited_once()
        a2.close.assert_awaited_once()
        assert len(registry.agents) == 0
        assert len(events) == 2

    def test_register_multiple_agents(self):
        registry = AgentRegistry()
        agents = [_make_agent(session_id=f"a{i}") for i in range(5)]
        for a in agents:
            registry.register(a)
        assert len(registry.agents) == 5

    def test_default_event_bus_created(self):
        registry = AgentRegistry()
        assert isinstance(registry.event_bus, EventBus)
