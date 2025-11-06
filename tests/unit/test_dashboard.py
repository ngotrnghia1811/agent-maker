"""Tests for monitor/dashboard.py — Dashboard."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from universal_agents.core.types import AgentStats
from universal_agents.monitor.agent_registry import AgentRegistry
from universal_agents.monitor.dashboard import Dashboard
from universal_agents.monitor.events import AgentEvent, EventBus, EventType


def _make_agent(provider="claude", session_id="test-id", turns=0):
    agent = MagicMock()
    agent.session_id = session_id
    agent.config = MagicMock()
    agent.config.provider_name = provider
    agent.get_stats = MagicMock(return_value=AgentStats(
        session_id=session_id,
        provider=provider,
        total_turns=turns,
    ))
    agent.history = MagicMock()
    agent.history.turn_count = turns
    agent.close = AsyncMock()
    return agent


class TestDashboard:
    def test_subscribes_to_all_events(self):
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        dashboard = Dashboard(registry)

        # Check all event types have at least our handler
        for et in EventType:
            assert len(bus._subscribers.get(et, [])) >= 1

    def test_on_event_updates_status(self):
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        dashboard = Dashboard(registry)

        # Simulate events
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a1", "claude"))
        assert dashboard._agent_status["a1"] == "registered"

        bus.publish(AgentEvent(EventType.TURN_STARTED, "a1", "claude"))
        assert dashboard._agent_status["a1"] == "processing"

        bus.publish(AgentEvent(EventType.TURN_COMPLETED, "a1", "claude", data={"latency_ms": 150.0}))
        assert dashboard._agent_status["a1"] == "idle"
        assert dashboard._agent_latencies["a1"] == 150.0

        bus.publish(AgentEvent(EventType.TURN_FAILED, "a1", "claude", data={"latency_ms": 50.0}))
        assert dashboard._agent_status["a1"] == "error"
        assert dashboard._agent_errors["a1"] == 1

        bus.publish(AgentEvent(EventType.AGENT_CLOSED, "a1", "claude"))
        assert dashboard._agent_status["a1"] == "closed"

    def test_on_event_error_increments(self):
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        dashboard = Dashboard(registry)

        bus.publish(AgentEvent(EventType.AGENT_ERROR, "a1", "gpt"))
        bus.publish(AgentEvent(EventType.AGENT_ERROR, "a1", "gpt"))
        assert dashboard._agent_errors["a1"] == 2

    def test_build_table_with_agents(self):
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        dashboard = Dashboard(registry)

        agent = _make_agent(provider="claude", session_id="c1", turns=5)
        registry.agents["c1"] = agent
        dashboard._agent_status["c1"] = "idle"
        dashboard._agent_latencies["c1"] = 200.0

        table = dashboard._build_table()
        assert table.title == "Universal Agents Monitor"
        assert table.row_count == 1

    def test_build_table_empty(self):
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        dashboard = Dashboard(registry)

        table = dashboard._build_table()
        assert table.row_count == 0

    def test_print_snapshot(self, capsys):
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        dashboard = Dashboard(registry)

        agent = _make_agent(provider="claude", session_id="c1", turns=2)
        registry.agents["c1"] = agent
        dashboard._agent_status["c1"] = "idle"

        # Should not raise
        dashboard.print_snapshot()
