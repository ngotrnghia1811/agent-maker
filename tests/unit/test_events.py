"""Tests for monitor/events.py — EventType, AgentEvent, EventBus."""

from datetime import datetime

from universal_agents.monitor.events import AgentEvent, EventBus, EventType


class TestEventType:
    def test_all_values_exist(self):
        expected = {
            "agent_registered",
            "agent_started",
            "turn_started",
            "turn_completed",
            "turn_failed",
            "agent_error",
            "agent_closed",
        }
        assert {e.value for e in EventType} == expected


class TestAgentEvent:
    def test_creation_with_defaults(self):
        event = AgentEvent(
            event_type=EventType.TURN_STARTED,
            agent_id="abc",
            provider="claude",
        )
        assert event.event_type == EventType.TURN_STARTED
        assert event.agent_id == "abc"
        assert event.provider == "claude"
        assert isinstance(event.timestamp, datetime)
        assert event.data == {}

    def test_creation_with_data(self):
        event = AgentEvent(
            event_type=EventType.TURN_COMPLETED,
            agent_id="xyz",
            provider="gemini",
            data={"latency_ms": 123.4},
        )
        assert event.data["latency_ms"] == 123.4


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventType.TURN_STARTED, lambda e: received.append(e))

        event = AgentEvent(EventType.TURN_STARTED, "a1", "claude")
        bus.publish(event)

        assert len(received) == 1
        assert received[0] is event

    def test_publish_to_correct_subscribers_only(self):
        bus = EventBus()
        started = []
        completed = []
        bus.subscribe(EventType.TURN_STARTED, lambda e: started.append(e))
        bus.subscribe(EventType.TURN_COMPLETED, lambda e: completed.append(e))

        bus.publish(AgentEvent(EventType.TURN_STARTED, "a1", "claude"))
        bus.publish(AgentEvent(EventType.TURN_COMPLETED, "a1", "claude"))

        assert len(started) == 1
        assert len(completed) == 1

    def test_multiple_subscribers_same_event(self):
        bus = EventBus()
        r1, r2 = [], []
        bus.subscribe(EventType.AGENT_ERROR, lambda e: r1.append(e))
        bus.subscribe(EventType.AGENT_ERROR, lambda e: r2.append(e))

        bus.publish(AgentEvent(EventType.AGENT_ERROR, "a1", "gpt"))
        assert len(r1) == 1
        assert len(r2) == 1

    def test_publish_with_no_subscribers(self):
        bus = EventBus()
        # Should not raise
        bus.publish(AgentEvent(EventType.AGENT_CLOSED, "a1", "claude"))

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe(EventType.TURN_STARTED, handler)
        bus.unsubscribe(EventType.TURN_STARTED, handler)

        bus.publish(AgentEvent(EventType.TURN_STARTED, "a1", "claude"))
        assert len(received) == 0

    def test_unsubscribe_nonexistent_handler(self):
        bus = EventBus()
        # Should not raise
        bus.unsubscribe(EventType.TURN_STARTED, lambda e: None)
