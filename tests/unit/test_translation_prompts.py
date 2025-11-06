"""Tests for core/translation_prompts.py."""

from universal_agents.core.translation_prompts import (
    get_continue_prompt,
    get_new_conversation_prompt,
    get_system_prompt,
)


class TestGetSystemPrompt:
    def test_book_mode_default(self):
        prompt = get_system_prompt(mode="book")
        assert "translator" in prompt.lower()
        assert "Japanese" in prompt
        assert "English" in prompt

    def test_transcript_mode(self):
        prompt = get_system_prompt(mode="transcript")
        assert "subtitle" in prompt.lower() or "transcript" in prompt.lower()
        assert "timestamp" in prompt.lower()

    def test_custom_languages(self):
        prompt = get_system_prompt(source_lang="Korean", target_lang="French", mode="book")
        assert "Korean" in prompt
        assert "French" in prompt

    def test_with_title(self):
        prompt = get_system_prompt(title="My Video", mode="transcript")
        assert "My Video" in prompt

    def test_without_title(self):
        prompt = get_system_prompt(title="", mode="book")
        assert "document is:" not in prompt


class TestGetContinuePrompt:
    def test_book_continue(self):
        prompt = get_continue_prompt(mode="book")
        assert "continue" in prompt.lower()

    def test_transcript_continue_with_num(self):
        prompt = get_continue_prompt(mode="transcript", chunk_num=5)
        assert "chunk 5" in prompt

    def test_transcript_continue_no_num(self):
        prompt = get_continue_prompt(mode="transcript")
        assert "continue" in prompt.lower()


class TestGetNewConversationPrompt:
    def test_book_new_conversation(self):
        prompt = get_new_conversation_prompt(mode="book")
        assert "translator" in prompt.lower()

    def test_transcript_new_conversation(self):
        prompt = get_new_conversation_prompt(mode="transcript", last_line=100)
        assert "100" in prompt

    def test_transcript_no_last_line(self):
        prompt = get_new_conversation_prompt(mode="transcript", last_line=0)
        assert "previously translated" not in prompt.lower()
