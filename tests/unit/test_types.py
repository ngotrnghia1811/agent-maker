"""Unit tests for core/types.py."""

from datetime import datetime

from universal_agents.core.types import AgentStats, ConversationTurn, Message, TurnResult


class TestMessage:
    def test_defaults(self):
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}

    def test_metadata(self):
        msg = Message(role="assistant", content="hi", metadata={"model": "claude"})
        assert msg.metadata["model"] == "claude"


class TestConversationTurn:
    def test_successful_turn(self):
        user = Message(role="user", content="q")
        assistant = Message(role="assistant", content="a")
        turn = ConversationTurn(
            turn_number=1,
            user_message=user,
            assistant_message=assistant,
            processing_time_ms=150.0,
        )
        assert turn.success is True
        assert turn.thinking is None
        assert turn.error is None

    def test_failed_turn(self):
        user = Message(role="user", content="q")
        assistant = Message(role="assistant", content="")
        turn = ConversationTurn(
            turn_number=1,
            user_message=user,
            assistant_message=assistant,
            success=False,
            error="timeout",
        )
        assert turn.success is False
        assert turn.error == "timeout"


class TestTurnResult:
    def test_to_dict(self):
        result = TurnResult(
            turn_number=1,
            success=True,
            response="answer",
            thinking="thought",
            processing_time_ms=100.0,
        )
        d = result.to_dict()
        assert d["turn_number"] == 1
        assert d["success"] is True
        assert d["thinking"] == "thought"


class TestAgentStats:
    def test_avg_processing_time(self):
        stats = AgentStats(
            session_id="test",
            provider="claude",
            total_turns=4,
            total_processing_time_ms=1000.0,
        )
        assert stats.avg_processing_time_ms == 250.0

    def test_zero_turns(self):
        stats = AgentStats(session_id="test", provider="claude")
        assert stats.avg_processing_time_ms == 0.0

    def test_to_dict(self):
        stats = AgentStats(session_id="s", provider="p", total_turns=1)
        d = stats.to_dict()
        assert "session_id" in d
        assert "avg_processing_time_ms" in d
