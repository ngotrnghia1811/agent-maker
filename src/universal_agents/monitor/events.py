"""Event system for agent monitoring."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable


class EventType(Enum):
    AGENT_REGISTERED = "agent_registered"
    AGENT_STARTED = "agent_started"
    TURN_STARTED = "turn_started"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    AGENT_ERROR = "agent_error"
    AGENT_CLOSED = "agent_closed"


@dataclass
class AgentEvent:
    event_type: EventType
    agent_id: str
    provider: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Publish/subscribe event bus for agent monitoring."""

    def __init__(self):
        self._subscribers: dict[EventType, list[Callable[[AgentEvent], None]]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[AgentEvent], None]):
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[AgentEvent], None]):
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event: AgentEvent):
        for handler in self._subscribers.get(event.event_type, []):
            handler(event)
