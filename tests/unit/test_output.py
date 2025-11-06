"""Unit tests for core/output.py."""

import json
from pathlib import Path

from universal_agents.core.output import save_full_results, save_summary, save_turn
from universal_agents.core.types import ConversationTurn, Message, TurnResult


class TestSaveTurn:
    def test_saves_three_files(self, tmp_path):
        result = TurnResult(
            turn_number=1,
            success=True,
            response="Hello!",
            thinking="Let me think...",
            processing_time_ms=150.0,
        )
        saved = save_turn(result, tmp_path, "test_conv", "claude")

        assert "json" in saved
        assert "txt" in saved
        assert "md" in saved

        # Verify JSON
        data = json.loads(Path(saved["json"]).read_text())
        assert data["response"] == "Hello!"
        assert data["thinking"] == "Let me think..."

        # Verify TXT
        assert Path(saved["txt"]).read_text() == "Hello!"

        # Verify MD includes thinking
        md = Path(saved["md"]).read_text()
        assert "Let me think..." in md
        assert "Hello!" in md


class TestSaveSummary:
    def test_saves_summary(self, tmp_path):
        turns = [
            ConversationTurn(
                turn_number=1,
                user_message=Message(role="user", content="q"),
                assistant_message=Message(role="assistant", content="a"),
                processing_time_ms=100.0,
            ),
        ]
        saved = save_summary(turns, tmp_path, "conv", "claude", "session-1")

        data = json.loads(Path(saved["json"]).read_text())
        assert data["total_turns"] == 1
        assert data["successful_turns"] == 1


class TestSaveFullResults:
    def test_saves_full_results(self, tmp_path):
        turns = [
            ConversationTurn(
                turn_number=1,
                user_message=Message(role="user", content="question"),
                assistant_message=Message(role="assistant", content="answer"),
                thinking="thought",
                processing_time_ms=200.0,
            ),
        ]
        path = save_full_results(turns, tmp_path, "conv", "claude", "session-1")

        data = json.loads(Path(path).read_text())
        assert data["turns"][0]["user_message"] == "question"
        assert data["turns"][0]["thinking"] == "thought"
