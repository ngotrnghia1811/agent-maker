"""Post-run report generation with cost, latency, and error summaries."""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .agent_registry import AgentRegistry
from .events import AgentEvent, EventType


@dataclass
class AgentReport:
    agent_id: str
    provider: str
    total_turns: int = 0
    successful_turns: int = 0
    failed_turns: int = 0
    total_latency_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_turns == 0:
            return 0.0
        return self.total_latency_ms / self.total_turns

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "provider": self.provider,
            "total_turns": self.total_turns,
            "successful_turns": self.successful_turns,
            "failed_turns": self.failed_turns,
            "total_latency_ms": round(self.total_latency_ms, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "errors": self.errors,
        }


class Reporter:
    """Collects events and generates post-run reports."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._reports: dict[str, AgentReport] = {}

        # Subscribe to relevant events
        for et in (EventType.AGENT_REGISTERED, EventType.TURN_COMPLETED,
                    EventType.TURN_FAILED, EventType.AGENT_ERROR):
            registry.event_bus.subscribe(et, self._on_event)

    def _on_event(self, event: AgentEvent):
        aid = event.agent_id
        if event.event_type == EventType.AGENT_REGISTERED:
            self._reports[aid] = AgentReport(
                agent_id=aid,
                provider=event.provider,
            )
        elif event.event_type == EventType.TURN_COMPLETED:
            report = self._reports.get(aid)
            if report:
                report.total_turns += 1
                report.successful_turns += 1
                report.total_latency_ms += event.data.get("latency_ms", 0.0)
        elif event.event_type == EventType.TURN_FAILED:
            report = self._reports.get(aid)
            if report:
                report.total_turns += 1
                report.failed_turns += 1
                report.total_latency_ms += event.data.get("latency_ms", 0.0)
                report.errors.append(event.data.get("error", "unknown"))
        elif event.event_type == EventType.AGENT_ERROR:
            report = self._reports.get(aid)
            if report:
                report.errors.append(event.data.get("error", "unknown"))

    def get_report(self, agent_id: str) -> AgentReport | None:
        return self._reports.get(agent_id)

    def get_all_reports(self) -> list[AgentReport]:
        return list(self._reports.values())

    def summary(self) -> dict:
        """Generate an aggregate summary across all agents."""
        reports = self.get_all_reports()
        total_turns = sum(r.total_turns for r in reports)
        total_success = sum(r.successful_turns for r in reports)
        total_failed = sum(r.failed_turns for r in reports)
        total_latency = sum(r.total_latency_ms for r in reports)
        total_errors = sum(len(r.errors) for r in reports)

        return {
            "agent_count": len(reports),
            "total_turns": total_turns,
            "successful_turns": total_success,
            "failed_turns": total_failed,
            "total_latency_ms": round(total_latency, 1),
            "avg_latency_ms": round(total_latency / total_turns, 1) if total_turns else 0.0,
            "total_errors": total_errors,
            "agents": [r.to_dict() for r in reports],
        }

    def save_report(self, path: str | Path) -> Path:
        """Save the full report as JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.summary(), indent=2))
        return path

    def print_report(self) -> str:
        """Return a human-readable text report."""
        s = self.summary()
        lines = [
            "=" * 60,
            "Universal Agents — Run Report",
            "=" * 60,
            f"Agents: {s['agent_count']}",
            f"Total turns: {s['total_turns']} (success: {s['successful_turns']}, failed: {s['failed_turns']})",
            f"Total latency: {s['total_latency_ms']:.0f}ms (avg: {s['avg_latency_ms']:.0f}ms/turn)",
            f"Total errors: {s['total_errors']}",
            "",
            "Per-Agent Breakdown:",
            "-" * 60,
        ]
        for a in s["agents"]:
            lines.append(
                f"  [{a['provider']}] {a['agent_id'][:12]}  "
                f"turns={a['total_turns']} ok={a['successful_turns']} fail={a['failed_turns']}  "
                f"avg_lat={a['avg_latency_ms']:.0f}ms  errors={len(a['errors'])}"
            )
        lines.append("=" * 60)
        return "\n".join(lines)
