"""Live terminal dashboard showing agent status via rich."""

import asyncio
from collections import defaultdict

from rich.console import Console
from rich.live import Live
from rich.table import Table

from .agent_registry import AgentRegistry
from .events import AgentEvent, EventType


class Dashboard:
    """Live terminal dashboard showing agent status."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._agent_status: dict[str, str] = {}
        self._agent_latencies: dict[str, float] = {}
        self._agent_errors: dict[str, int] = defaultdict(int)
        self._console = Console()

        # Subscribe to all event types
        for et in EventType:
            registry.event_bus.subscribe(et, self._on_event)

    def _on_event(self, event: AgentEvent):
        aid = event.agent_id
        if event.event_type == EventType.AGENT_REGISTERED:
            self._agent_status[aid] = "registered"
        elif event.event_type == EventType.AGENT_STARTED:
            self._agent_status[aid] = "running"
        elif event.event_type == EventType.TURN_STARTED:
            self._agent_status[aid] = "processing"
        elif event.event_type == EventType.TURN_COMPLETED:
            self._agent_status[aid] = "idle"
            self._agent_latencies[aid] = event.data.get("latency_ms", 0.0)
        elif event.event_type == EventType.TURN_FAILED:
            self._agent_status[aid] = "error"
            self._agent_errors[aid] += 1
            self._agent_latencies[aid] = event.data.get("latency_ms", 0.0)
        elif event.event_type == EventType.AGENT_ERROR:
            self._agent_status[aid] = "error"
            self._agent_errors[aid] += 1
        elif event.event_type == EventType.AGENT_CLOSED:
            self._agent_status[aid] = "closed"

    def _build_table(self) -> Table:
        table = Table(title="Universal Agents Monitor")
        table.add_column("Agent ID", style="cyan", max_width=12)
        table.add_column("Provider", style="green")
        table.add_column("Status", style="bold")
        table.add_column("Turns", justify="right")
        table.add_column("Last Latency", justify="right")
        table.add_column("Errors", justify="right", style="red")

        for agent_id, agent in self.registry.agents.items():
            status = self._agent_status.get(agent_id, "unknown")
            stats = agent.get_stats()
            latency = self._agent_latencies.get(agent_id, 0.0)
            errors = self._agent_errors.get(agent_id, 0)
            table.add_row(
                agent_id[:12],
                agent.config.provider_name,
                status,
                str(stats.total_turns),
                f"{latency:.0f}ms",
                str(errors),
            )
        return table

    def print_snapshot(self):
        """Print a single snapshot of the dashboard (non-live)."""
        self._console.print(self._build_table())

    async def run(self, stop_event: asyncio.Event | None = None):
        """Launch live-updating dashboard.

        Args:
            stop_event: If provided, the dashboard stops when this event is set.
                        If None, runs until cancelled.
        """
        with Live(self._build_table(), refresh_per_second=2, console=self._console) as live:
            while True:
                if stop_event and stop_event.is_set():
                    break
                live.update(self._build_table())
                await asyncio.sleep(0.5)
