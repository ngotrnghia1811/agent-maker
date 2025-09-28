"""Wrapper that emits monitoring events for every chat turn."""

import time

from ..core.base_agent import BaseChatAgent
from .events import AgentEvent, EventBus, EventType


class MonitoredAgent:
    """Decorator that emits events for every chat turn.

    Delegates all operations to the wrapped agent while publishing
    events to the EventBus on turn start, completion, and failure.
    """

    def __init__(self, agent: BaseChatAgent, event_bus: EventBus):
        self._agent = agent
        self._bus = event_bus
        self._turn_count = 0

    @property
    def agent(self) -> BaseChatAgent:
        return self._agent

    @property
    def session_id(self) -> str:
        return self._agent.session_id

    @property
    def config(self):
        return self._agent.config

    async def chat(self, message: str, **kwargs) -> str:
        self._turn_count += 1
        self._bus.publish(AgentEvent(
            event_type=EventType.TURN_STARTED,
            agent_id=self._agent.session_id,
            provider=self._agent.config.provider_name,
            data={"turn": self._turn_count, "message_preview": message[:80]},
        ))
        start = time.monotonic()
        try:
            response = await self._agent.chat(message, **kwargs)
            elapsed_ms = (time.monotonic() - start) * 1000
            self._bus.publish(AgentEvent(
                event_type=EventType.TURN_COMPLETED,
                agent_id=self._agent.session_id,
                provider=self._agent.config.provider_name,
                data={"turn": self._turn_count, "latency_ms": elapsed_ms},
            ))
            return response
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._bus.publish(AgentEvent(
                event_type=EventType.TURN_FAILED,
                agent_id=self._agent.session_id,
                provider=self._agent.config.provider_name,
                data={"turn": self._turn_count, "error": str(e), "latency_ms": elapsed_ms},
            ))
            raise

    def get_stats(self):
        return self._agent.get_stats()

    def get_turns(self):
        return self._agent.get_turns()

    def get_history(self):
        return self._agent.get_history()

    async def close(self):
        await self._agent.close()
        self._bus.publish(AgentEvent(
            event_type=EventType.AGENT_CLOSED,
            agent_id=self._agent.session_id,
            provider=self._agent.config.provider_name,
        ))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
