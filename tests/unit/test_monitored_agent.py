"""Tests for monitor/monitored_agent.py — MonitoredAgent wrapper."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from universal_agents.monitor.events import EventBus, EventType
from universal_agents.monitor.monitored_agent import MonitoredAgent


def _make_agent(provider="claude", session_id="test-id"):
    agent = AsyncMock()
    agent.session_id = session_id
    agent.config = MagicMock()
    agent.config.provider_name = provider
    agent.chat = AsyncMock(return_value="response text")
    agent.get_stats = MagicMock()
    agent.get_turns = MagicMock(return_value=[])
    agent.get_history = MagicMock(return_value=[])
    agent.close = AsyncMock()
    return agent


class TestMonitoredAgent:
    @pytest.mark.asyncio
    async def test_chat_emits_start_and_complete(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventType.TURN_STARTED, lambda e: events.append(e))
        bus.subscribe(EventType.TURN_COMPLETED, lambda e: events.append(e))

        agent = _make_agent(session_id="m1", provider="claude")
        monitored = MonitoredAgent(agent, bus)
        result = await monitored.chat("Hello")

        assert result == "response text"
        assert len(events) == 2
        assert events[0].event_type == EventType.TURN_STARTED
        assert events[0].data["turn"] == 1
        assert events[0].data["message_preview"] == "Hello"
        assert events[1].event_type == EventType.TURN_COMPLETED
        assert events[1].data["turn"] == 1
        assert "latency_ms" in events[1].data

    @pytest.mark.asyncio
    async def test_chat_emits_failed_on_error(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventType.TURN_FAILED, lambda e: events.append(e))

        agent = _make_agent()
        agent.chat = AsyncMock(side_effect=RuntimeError("boom"))
        monitored = MonitoredAgent(agent, bus)

        with pytest.raises(RuntimeError, match="boom"):
            await monitored.chat("fail")

        assert len(events) == 1
        assert events[0].event_type == EventType.TURN_FAILED
        assert events[0].data["error"] == "boom"
        assert "latency_ms" in events[0].data

    @pytest.mark.asyncio
    async def test_turn_count_increments(self):
        bus = EventBus()
        started_turns = []
        bus.subscribe(EventType.TURN_STARTED, lambda e: started_turns.append(e.data["turn"]))

        agent = _make_agent()
        monitored = MonitoredAgent(agent, bus)

        await monitored.chat("first")
        await monitored.chat("second")
        await monitored.chat("third")

        assert started_turns == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_message_preview_truncated(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventType.TURN_STARTED, lambda e: events.append(e))

        agent = _make_agent()
        monitored = MonitoredAgent(agent, bus)
        long_msg = "x" * 200
        await monitored.chat(long_msg)

        assert len(events[0].data["message_preview"]) == 80

    def test_property_delegation(self):
        agent = _make_agent(session_id="s1", provider="gemini")
        bus = EventBus()
        monitored = MonitoredAgent(agent, bus)

        assert monitored.session_id == "s1"
        assert monitored.config.provider_name == "gemini"
        assert monitored.agent is agent

    def test_get_stats_delegates(self):
        agent = _make_agent()
        bus = EventBus()
        monitored = MonitoredAgent(agent, bus)
        monitored.get_stats()
        agent.get_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_emits_event(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventType.AGENT_CLOSED, lambda e: events.append(e))

        agent = _make_agent(session_id="c1")
        monitored = MonitoredAgent(agent, bus)
        await monitored.close()

        agent.close.assert_awaited_once()
        assert len(events) == 1
        assert events[0].event_type == EventType.AGENT_CLOSED

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        events = []
        bus = EventBus()
        bus.subscribe(EventType.AGENT_CLOSED, lambda e: events.append(e))

        agent = _make_agent()
        async with MonitoredAgent(agent, bus) as m:
            await m.chat("hi")

        agent.close.assert_awaited_once()
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_kwargs_passed_through(self):
        agent = _make_agent()
        bus = EventBus()
        monitored = MonitoredAgent(agent, bus)
        await monitored.chat("test", temperature=0.5)
        agent.chat.assert_awaited_once_with("test", temperature=0.5)
