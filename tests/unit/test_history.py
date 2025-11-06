"""Unit tests for core/history.py."""

from universal_agents.core.history import ConversationHistory
from universal_agents.core.types import Message


class TestConversationHistory:
    def test_empty(self):
        h = ConversationHistory()
        assert h.turn_count == 0
        assert h.messages == []
        assert h.turns == []

    def test_add_turn(self):
        h = ConversationHistory()
        user = Message(role="user", content="q")
        assistant = Message(role="assistant", content="a")
        turn = h.add_turn(user, assistant, processing_time_ms=100.0)

        assert turn.turn_number == 1
        assert h.turn_count == 1
        assert len(h.messages) == 2
        assert h.messages[0].role == "user"
        assert h.messages[1].role == "assistant"

    def test_multiple_turns(self):
        h = ConversationHistory()
        for i in range(3):
            h.add_turn(
                Message(role="user", content=f"q{i}"),
                Message(role="assistant", content=f"a{i}"),
            )
        assert h.turn_count == 3
        assert len(h.messages) == 6

    def test_max_turns_truncation(self):
        h = ConversationHistory(max_turns=2)
        for i in range(5):
            h.add_turn(
                Message(role="user", content=f"q{i}"),
                Message(role="assistant", content=f"a{i}"),
            )
        assert h.turn_count == 2
        # Should keep the last 2 turns
        assert h.turns[0].turn_number == 4
        assert h.turns[1].turn_number == 5

    def test_clear(self):
        h = ConversationHistory()
        h.add_turn(
            Message(role="user", content="q"),
            Message(role="assistant", content="a"),
        )
        h.clear()
        assert h.turn_count == 0
        assert h.messages == []

    def test_get_messages_for_context(self):
        h = ConversationHistory()
        h.add_turn(
            Message(role="user", content="hi"),
            Message(role="assistant", content="hello"),
        )
        ctx = h.get_messages_for_context()
        assert ctx == [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]

    def test_thinking_stored(self):
        h = ConversationHistory()
        turn = h.add_turn(
            Message(role="user", content="q"),
            Message(role="assistant", content="a"),
            thinking="I thought about it",
        )
        assert turn.thinking == "I thought about it"
