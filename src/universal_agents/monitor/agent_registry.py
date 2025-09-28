"""Central registry for managing multiple agents."""

from ..core.base_agent import BaseChatAgent
from .events import AgentEvent, EventBus, EventType


class AgentRegistry:
    """Central registry for managing multiple agents."""

    def __init__(self, event_bus: EventBus | None = None):
        self.agents: dict[str, BaseChatAgent] = {}
        self.event_bus = event_bus or EventBus()

    def register(self, agent: BaseChatAgent) -> str:
        """Register an agent and return its ID."""
        agent_id = agent.session_id
        self.agents[agent_id] = agent
        self.event_bus.publish(AgentEvent(
            event_type=EventType.AGENT_REGISTERED,
            agent_id=agent_id,
            provider=agent.config.provider_name,
        ))
        return agent_id

    def get(self, agent_id: str) -> BaseChatAgent:
        return self.agents[agent_id]

    def list_agents(self) -> list[dict]:
        return [
            {
                "id": aid,
                "provider": a.config.provider_name,
                "turns": a.history.turn_count,
            }
            for aid, a in self.agents.items()
        ]

    async def close_all(self):
        for agent_id, agent in list(self.agents.items()):
            await agent.close()
            self.event_bus.publish(AgentEvent(
                event_type=EventType.AGENT_CLOSED,
                agent_id=agent_id,
                provider=agent.config.provider_name,
            ))
        self.agents.clear()
