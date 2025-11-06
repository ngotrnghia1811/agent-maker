"""Tests for monitor/reporter.py — Reporter and AgentReport."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from universal_agents.monitor.agent_registry import AgentRegistry
from universal_agents.monitor.events import AgentEvent, EventBus, EventType
from universal_agents.monitor.reporter import AgentReport, Reporter


class TestAgentReport:
    def test_avg_latency(self):
        report = AgentReport(agent_id="a1", provider="claude", total_turns=4, total_latency_ms=400.0)
        assert report.avg_latency_ms == 100.0

    def test_avg_latency_zero_turns(self):
        report = AgentReport(agent_id="a1", provider="claude")
        assert report.avg_latency_ms == 0.0

    def test_to_dict(self):
        report = AgentReport(
            agent_id="a1",
            provider="claude",
            total_turns=2,
            successful_turns=1,
            failed_turns=1,
            total_latency_ms=300.0,
            errors=["timeout"],
        )
        d = report.to_dict()
        assert d["agent_id"] == "a1"
        assert d["avg_latency_ms"] == 150.0
        assert d["errors"] == ["timeout"]


class TestReporter:
    def _make_reporter(self):
        bus = EventBus()
        registry = AgentRegistry(event_bus=bus)
        reporter = Reporter(registry)
        return registry, bus, reporter

    def test_register_event_creates_report(self):
        registry, bus, reporter = self._make_reporter()
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a1", "claude"))
        assert reporter.get_report("a1") is not None
        assert reporter.get_report("a1").provider == "claude"

    def test_turn_completed_updates_report(self):
        registry, bus, reporter = self._make_reporter()
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a1", "claude"))
        bus.publish(AgentEvent(EventType.TURN_COMPLETED, "a1", "claude", data={"latency_ms": 100.0}))
        bus.publish(AgentEvent(EventType.TURN_COMPLETED, "a1", "claude", data={"latency_ms": 200.0}))

        report = reporter.get_report("a1")
        assert report.total_turns == 2
        assert report.successful_turns == 2
        assert report.total_latency_ms == 300.0

    def test_turn_failed_updates_report(self):
        registry, bus, reporter = self._make_reporter()
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a1", "claude"))
        bus.publish(AgentEvent(EventType.TURN_FAILED, "a1", "claude", data={"error": "timeout", "latency_ms": 50.0}))

        report = reporter.get_report("a1")
        assert report.total_turns == 1
        assert report.failed_turns == 1
        assert report.errors == ["timeout"]

    def test_agent_error_appends_error(self):
        registry, bus, reporter = self._make_reporter()
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a1", "claude"))
        bus.publish(AgentEvent(EventType.AGENT_ERROR, "a1", "claude", data={"error": "crash"}))

        report = reporter.get_report("a1")
        assert report.errors == ["crash"]
        # AGENT_ERROR doesn't increment turn count
        assert report.total_turns == 0

    def test_get_all_reports(self):
        registry, bus, reporter = self._make_reporter()
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a1", "claude"))
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a2", "gpt"))

        reports = reporter.get_all_reports()
        assert len(reports) == 2

    def test_summary(self):
        registry, bus, reporter = self._make_reporter()
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a1", "claude"))
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a2", "gpt"))
        bus.publish(AgentEvent(EventType.TURN_COMPLETED, "a1", "claude", data={"latency_ms": 100.0}))
        bus.publish(AgentEvent(EventType.TURN_COMPLETED, "a2", "gpt", data={"latency_ms": 200.0}))
        bus.publish(AgentEvent(EventType.TURN_FAILED, "a2", "gpt", data={"error": "fail", "latency_ms": 50.0}))

        s = reporter.summary()
        assert s["agent_count"] == 2
        assert s["total_turns"] == 3
        assert s["successful_turns"] == 2
        assert s["failed_turns"] == 1
        assert s["total_errors"] == 1
        assert len(s["agents"]) == 2

    def test_summary_empty(self):
        registry, bus, reporter = self._make_reporter()
        s = reporter.summary()
        assert s["agent_count"] == 0
        assert s["avg_latency_ms"] == 0.0

    def test_save_report(self, tmp_path):
        registry, bus, reporter = self._make_reporter()
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a1", "claude"))
        bus.publish(AgentEvent(EventType.TURN_COMPLETED, "a1", "claude", data={"latency_ms": 100.0}))

        out = reporter.save_report(tmp_path / "report.json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["agent_count"] == 1

    def test_print_report(self):
        registry, bus, reporter = self._make_reporter()
        bus.publish(AgentEvent(EventType.AGENT_REGISTERED, "a1", "claude"))
        bus.publish(AgentEvent(EventType.TURN_COMPLETED, "a1", "claude", data={"latency_ms": 100.0}))

        text = reporter.print_report()
        assert "Universal Agents" in text
        assert "claude" in text
        assert "Agents: 1" in text

    def test_unregistered_agent_events_ignored(self):
        """Events for agents not in _reports should not crash."""
        registry, bus, reporter = self._make_reporter()
        # No AGENT_REGISTERED first
        bus.publish(AgentEvent(EventType.TURN_COMPLETED, "unknown", "claude", data={"latency_ms": 100.0}))
        assert reporter.get_report("unknown") is None
