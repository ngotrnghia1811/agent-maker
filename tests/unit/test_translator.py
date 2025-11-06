"""Tests for providers/claude/translator.py — ClaudeTranslatorAgent."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from universal_agents.providers.claude.config import ClaudeTranslatorConfig
from universal_agents.providers.claude.translator import (
    ClaudeTranslatorAgent,
    ProgressState,
    TranslationChunk,
    TranslationResult,
)
from universal_agents.providers.gemini.config import GeminiTranslatorConfig
from universal_agents.providers.gemini.translator import (
    GeminiTranslatorAgent,
    ProgressState as GeminiProgressState,
    TranslationChunk as GeminiTranslationChunk,
    TranslationResult as GeminiTranslationResult,
)


class TestClaudeTranslatorConfig:
    def test_defaults(self):
        cfg = ClaudeTranslatorConfig()
        assert cfg.timeout == 600
        assert cfg.max_turns_per_conversation == 20
        assert cfg.source_language == "ja"
        assert cfg.target_language == "en"
        assert cfg.translation_mode == "book"
        assert cfg.chunk_size == 2000

    def test_inherits_claude_data_config(self):
        cfg = ClaudeTranslatorConfig()
        assert cfg.provider_name == "claude"
        assert cfg.base_url == "https://claude.ai/new"
        assert cfg.extract_thinking is True


class TestTranslationChunk:
    def test_text_chunk(self):
        chunk = TranslationChunk(chunk_id="c1", chunk_index=0, source_text="Hello world")
        assert chunk.chunk_id == "c1"
        assert chunk.source_text == "Hello world"

    def test_file_chunk(self):
        chunk = TranslationChunk(chunk_id="c2", chunk_index=1, source_file="/path/to/file.pdf")
        assert chunk.source_file == "/path/to/file.pdf"


class TestTranslationResult:
    def test_to_dict(self):
        result = TranslationResult(
            chunk_id="c1", chunk_index=0, success=True,
            source_text="abc", translated_text="def",
        )
        d = result.to_dict()
        assert d["chunk_id"] == "c1"
        assert d["success"] is True
        assert d["translated_text"] == "def"

    def test_to_dict_truncates_source(self):
        result = TranslationResult(
            chunk_id="c1", chunk_index=0, success=True,
            source_text="x" * 300,
        )
        d = result.to_dict()
        assert len(d["source_text"]) == 200


class TestProgressState:
    def test_mark_completed(self):
        state = ProgressState(document_id="d1", total_chunks=3)
        state.mark_completed(1)
        state.mark_completed(0)
        assert state.completed_chunks == [0, 1]

    def test_is_complete(self):
        state = ProgressState(document_id="d1", total_chunks=2)
        assert not state.is_complete
        state.mark_completed(0)
        state.mark_completed(1)
        assert state.is_complete

    def test_roundtrip_dict(self):
        state = ProgressState(document_id="d1", total_chunks=5, completed_chunks=[0, 1])
        d = state.to_dict()
        restored = ProgressState.from_dict(d)
        assert restored.document_id == "d1"
        assert restored.completed_chunks == [0, 1]

    def test_save_load(self, tmp_path):
        p = tmp_path / "progress.json"
        state = ProgressState(document_id="d1", total_chunks=3, completed_chunks=[0])
        state.save(p)
        loaded = ProgressState.load(p)
        assert loaded is not None
        assert loaded.document_id == "d1"
        assert loaded.completed_chunks == [0]

    def test_load_missing(self, tmp_path):
        assert ProgressState.load(tmp_path / "nonexistent.json") is None


class TestClaudeTranslatorAgent:
    def test_should_split_conversation(self):
        agent = ClaudeTranslatorAgent(ClaudeTranslatorConfig(max_turns_per_conversation=3))
        assert not agent.should_split_conversation()
        agent.turn_in_conversation = 3
        assert agent.should_split_conversation()

    def test_get_full_translation(self):
        agent = ClaudeTranslatorAgent()
        agent.results = [
            TranslationResult(chunk_id="c0", chunk_index=0, success=True, translated_text="Part 1"),
            TranslationResult(chunk_id="c1", chunk_index=1, success=False, error="fail"),
            TranslationResult(chunk_id="c2", chunk_index=2, success=True, translated_text="Part 3"),
        ]
        assert agent.get_full_translation() == "Part 1\n\nPart 3"

    def test_export_results(self, tmp_path):
        agent = ClaudeTranslatorAgent()
        agent._agent = MagicMock()
        agent._agent.session_id = "test-session"
        agent.results = [
            TranslationResult(chunk_id="c0", chunk_index=0, success=True, translated_text="ok"),
        ]
        out = agent.export_results(tmp_path / "results.json")
        data = json.loads(out.read_text())
        assert data["total_chunks"] == 1
        assert data["successful_chunks"] == 1

    @pytest.mark.asyncio
    async def test_translate_text_success(self):
        agent = ClaudeTranslatorAgent()
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(return_value="translated text")
        agent._agent = mock_inner

        chunk = TranslationChunk(chunk_id="c1", chunk_index=0, source_text="input text")
        result = await agent.translate_text(chunk)

        assert result.success
        assert result.translated_text == "translated text"
        assert result.processing_time_ms > 0
        assert agent.turn_in_conversation == 1
        assert len(agent.results) == 1

    @pytest.mark.asyncio
    async def test_translate_text_with_system_prompt(self):
        agent = ClaudeTranslatorAgent()
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(return_value="ok")
        agent._agent = mock_inner

        chunk = TranslationChunk(chunk_id="c1", chunk_index=0, source_text="input")
        await agent.translate_text(chunk, system_prompt="Translate this:", is_first_turn=True)

        called_prompt = mock_inner.chat.call_args[0][0]
        assert "Translate this:" in called_prompt
        assert "input" in called_prompt

    @pytest.mark.asyncio
    async def test_translate_text_failure(self):
        agent = ClaudeTranslatorAgent()
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(side_effect=RuntimeError("timeout"))
        agent._agent = mock_inner

        chunk = TranslationChunk(chunk_id="c1", chunk_index=0, source_text="input")
        result = await agent.translate_text(chunk)

        assert not result.success
        assert result.error == "timeout"

    @pytest.mark.asyncio
    async def test_translate_file_missing_file(self):
        agent = ClaudeTranslatorAgent()
        agent._agent = AsyncMock()

        chunk = TranslationChunk(chunk_id="c1", chunk_index=0, source_file="/nonexistent.pdf")
        result = await agent.translate_file(chunk)

        assert not result.success
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_progress_skip_completed_chunk(self):
        """translate_text should skip chunks that are already completed."""
        agent = ClaudeTranslatorAgent()
        mock_inner = AsyncMock()
        agent._agent = mock_inner

        agent.progress = ProgressState(document_id="d1", total_chunks=3, completed_chunks=[0])
        chunk = TranslationChunk(chunk_id="c0", chunk_index=0, source_text="skip me")
        result = await agent.translate_text(chunk)

        assert result.success
        assert result.translated_text == "[previously completed]"
        mock_inner.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_progress_tracks_completed(self, tmp_path):
        """translate_text should mark chunks complete and save progress."""
        agent = ClaudeTranslatorAgent()
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(return_value="translated")
        agent._agent = mock_inner

        progress_file = tmp_path / "progress.json"
        agent.init_progress("d1", total_chunks=2, progress_path=progress_file)

        chunk = TranslationChunk(chunk_id="c0", chunk_index=0, source_text="text")
        await agent.translate_text(chunk)

        assert 0 in agent.progress.completed_chunks
        assert progress_file.exists()

    def test_init_progress_resumes(self, tmp_path):
        """init_progress should load existing progress file."""
        progress_file = tmp_path / "progress.json"
        state = ProgressState(document_id="d1", total_chunks=5, completed_chunks=[0, 1])
        state.save(progress_file)

        agent = ClaudeTranslatorAgent()
        agent.init_progress("d1", total_chunks=5, progress_path=progress_file)

        assert agent.progress is not None
        assert agent.progress.completed_chunks == [0, 1]


# ======================================================================
# Gemini Translator Tests
# ======================================================================


class TestGeminiTranslatorConfig:
    def test_defaults(self):
        cfg = GeminiTranslatorConfig()
        assert cfg.timeout == 600
        assert cfg.max_turns_per_conversation == 20
        assert cfg.source_language == "ja"
        assert cfg.target_language == "en"
        assert cfg.translation_mode == "book"
        assert cfg.chunk_size == 2000
        assert cfg.overlap_chars == 100

    def test_inherits_gemini_config(self):
        cfg = GeminiTranslatorConfig()
        assert cfg.provider_name == "gemini"
        assert cfg.base_url == "https://gemini.google.com"


class TestGeminiTranslatorAgent:
    def test_should_split_conversation(self):
        agent = GeminiTranslatorAgent(GeminiTranslatorConfig(max_turns_per_conversation=3))
        assert not agent.should_split_conversation()
        agent.turn_in_conversation = 3
        assert agent.should_split_conversation()

    def test_get_full_translation(self):
        agent = GeminiTranslatorAgent()
        agent.results = [
            GeminiTranslationResult(chunk_id="c0", chunk_index=0, success=True, translated_text="Part 1"),
            GeminiTranslationResult(chunk_id="c1", chunk_index=1, success=False, error="fail"),
            GeminiTranslationResult(chunk_id="c2", chunk_index=2, success=True, translated_text="Part 3"),
        ]
        assert agent.get_full_translation() == "Part 1\n\nPart 3"

    def test_export_results(self, tmp_path):
        agent = GeminiTranslatorAgent()
        agent._agent = MagicMock()
        agent._agent.session_id = "test-session"
        agent.results = [
            GeminiTranslationResult(chunk_id="c0", chunk_index=0, success=True, translated_text="ok"),
        ]
        out = agent.export_results(tmp_path / "results.json")
        data = json.loads(out.read_text())
        assert data["total_chunks"] == 1
        assert data["successful_chunks"] == 1
        assert "translation_mode" in data["config"]

    @pytest.mark.asyncio
    async def test_translate_text_success(self):
        agent = GeminiTranslatorAgent()
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(return_value="translated text")
        agent._agent = mock_inner

        chunk = GeminiTranslationChunk(chunk_id="c1", chunk_index=0, source_text="input")
        result = await agent.translate_text(chunk)

        assert result.success
        assert result.translated_text == "translated text"
        assert agent.turn_in_conversation == 1

    @pytest.mark.asyncio
    async def test_progress_skip_completed_chunk(self):
        agent = GeminiTranslatorAgent()
        agent._agent = AsyncMock()

        agent.progress = GeminiProgressState(document_id="d1", total_chunks=3, completed_chunks=[0])
        chunk = GeminiTranslationChunk(chunk_id="c0", chunk_index=0, source_text="skip")
        result = await agent.translate_text(chunk)

        assert result.success
        assert result.translated_text == "[previously completed]"

    @pytest.mark.asyncio
    async def test_progress_tracks_completed(self, tmp_path):
        agent = GeminiTranslatorAgent()
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(return_value="done")
        agent._agent = mock_inner

        progress_file = tmp_path / "progress.json"
        agent.init_progress("d1", total_chunks=2, progress_path=progress_file)

        chunk = GeminiTranslationChunk(chunk_id="c0", chunk_index=0, source_text="text")
        await agent.translate_text(chunk)

        assert 0 in agent.progress.completed_chunks
        assert progress_file.exists()

    def test_init_progress_resumes(self, tmp_path):
        progress_file = tmp_path / "progress.json"
        state = GeminiProgressState(document_id="d1", total_chunks=5, completed_chunks=[0, 1, 2])
        state.save(progress_file)

        agent = GeminiTranslatorAgent()
        agent.init_progress("d1", total_chunks=5, progress_path=progress_file)

        assert agent.progress is not None
        assert agent.progress.completed_chunks == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_translate_file_missing_file(self):
        agent = GeminiTranslatorAgent()
        agent._agent = AsyncMock()

        chunk = GeminiTranslationChunk(chunk_id="c1", chunk_index=0, source_file="/nonexistent.pdf")
        result = await agent.translate_file(chunk)

        assert not result.success
        assert "not found" in result.error


class TestGeminiTranslatorLineTracking:
    """Test line-per-conversation limits and conversation splitting."""

    def test_should_split_for_line_limit(self):
        agent = GeminiTranslatorAgent()
        agent.lines_in_conversation = 380
        assert agent.should_split_for_line_limit(50, max_lines=400)
        assert not agent.should_split_for_line_limit(20, max_lines=400)

    def test_lines_in_conversation_starts_at_zero(self):
        agent = GeminiTranslatorAgent()
        assert agent.lines_in_conversation == 0

    @pytest.mark.asyncio
    async def test_translate_text_tracks_lines(self):
        agent = GeminiTranslatorAgent()
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(return_value="translated")
        agent._agent = mock_inner

        chunk = GeminiTranslationChunk(chunk_id="c0", chunk_index=0, source_text="text")
        await agent.translate_text(chunk, num_blocks=50)
        assert agent.lines_in_conversation == 50

        await agent.translate_text(
            GeminiTranslationChunk(chunk_id="c1", chunk_index=1, source_text="more"),
            num_blocks=30,
        )
        assert agent.lines_in_conversation == 80

    def test_progress_state_includes_lines(self, tmp_path):
        state = GeminiProgressState(
            document_id="d1", total_chunks=5,
            current_lines_in_conversation=250,
        )
        path = tmp_path / "progress.json"
        state.save(path)

        loaded = GeminiProgressState.load(path)
        assert loaded.current_lines_in_conversation == 250

    def test_progress_state_default_lines_zero(self):
        state = GeminiProgressState(document_id="d1", total_chunks=3)
        assert state.current_lines_in_conversation == 0


class TestRateLimitError:
    def test_is_exception(self):
        from universal_agents.providers.gemini.translator import RateLimitError
        e = RateLimitError("rate limited")
        assert isinstance(e, Exception)
        assert str(e) == "rate limited"


class TestKendoContext:
    """Test kendo dictionary/prompt loading."""

    def test_load_kendo_dictionary(self, tmp_path):
        from universal_agents.core.kendo_context import load_kendo_dictionary
        dict_file = tmp_path / "dict.md"
        dict_file.write_text("# Kendo Dictionary\nmen: strike to head", encoding="utf-8")
        content = load_kendo_dictionary(dict_file)
        assert "men: strike to head" in content

    def test_load_kendo_dictionary_missing(self, tmp_path):
        from universal_agents.core.kendo_context import load_kendo_dictionary
        with pytest.raises(FileNotFoundError):
            load_kendo_dictionary(tmp_path / "nonexistent.md")

    def test_build_kendo_srt_system_prompt(self, tmp_path):
        from universal_agents.core.kendo_context import build_kendo_srt_system_prompt
        dict_file = tmp_path / "dict.md"
        dict_file.write_text("# Dictionary\nmen: head strike", encoding="utf-8")

        prompt = build_kendo_srt_system_prompt(dict_file, title="Kendo Basics")
        assert "Kendo Basics" in prompt
        assert "men: head strike" in prompt
        assert "Japanese" in prompt
        assert "SRT" in prompt

    def test_build_kendo_continue_prompt(self):
        from universal_agents.core.kendo_context import build_kendo_continue_prompt
        prompt = build_kendo_continue_prompt(chunk_num=3, total_chunks=10)
        assert "3/10" in prompt

    def test_build_kendo_new_conversation_prompt(self, tmp_path):
        from universal_agents.core.kendo_context import build_kendo_new_conversation_prompt
        dict_file = tmp_path / "dict.md"
        dict_file.write_text("# Dictionary\nkote: wrist strike", encoding="utf-8")

        prompt = build_kendo_new_conversation_prompt(
            dict_file, title="Test", last_block_num=400,
        )
        assert "400" in prompt
        assert "401" in prompt
        assert "kote: wrist strike" in prompt
