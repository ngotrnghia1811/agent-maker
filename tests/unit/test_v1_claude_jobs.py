"""
V1 Claude Jobs — Ported to V2

Tests adapted from v1 claude/chat-agent, data-agent, and translator-agent
test suites to verify v2 provides equivalent functionality. These test
configs, data classes, JSON extraction, prompt building, and utility functions
from all three agent types.

Source files:
  - _references/universal-agent_v1/claude/chat-agent/test_agent.py
  - _references/universal-agent_v1/claude/chat-agent/test_comprehensive.py
  - _references/universal-agent_v1/claude/data-agent/test_agent.py
  - _references/universal-agent_v1/claude/translator-agent/test_agent.py
"""

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# --- V2 imports ---
from universal_agents.core.config import BaseConfig, BrowserConfig
from universal_agents.providers.claude.config import (
    ClaudeConfig,
    ClaudeDataConfig,
    ClaudeTranslatorConfig,
)
from universal_agents.providers.claude.chat import ClaudeChatAgent
from universal_agents.providers.claude.data import ClaudeDataAgent
from universal_agents.providers.claude.selectors import CLAUDE_SELECTORS
from universal_agents.providers.claude.translator import (
    ClaudeTranslatorAgent,
    ProgressState,
    TranslationChunk,
    TranslationResult,
)


# ═══════════════════════════════════════════════════════════════
#  V1 Chat Agent Tests → V2
# ═══════════════════════════════════════════════════════════════

class TestChatAgentV1Ported:
    """Adapted from v1 claude/chat-agent/test_agent.py"""

    # v1 test_seleniumbase_availability → v2: Playwright is the backend
    def test_playwright_is_used(self):
        """V2 replaced SeleniumBase with Playwright. Verify import path."""
        from universal_agents.browser import browser_manager
        assert hasattr(browser_manager, "BrowserManager")

    # v1 test_configuration → v2: ClaudeConfig defaults and custom values
    def test_claude_config_defaults(self):
        config = ClaudeConfig()
        assert config.headless is True
        assert config.timeout == 180
        assert config.max_history_turns == 50
        assert config.max_retries == 3
        assert config.provider_name == "claude"
        assert config.base_url == "https://claude.ai/new"

    def test_claude_config_custom(self):
        config = ClaudeConfig(
            headless=False,
            timeout=120,
            max_history_turns=20,
        )
        assert config.headless is False
        assert config.timeout == 120
        assert config.max_history_turns == 20

    def test_claude_config_env_storage_state(self, monkeypatch):
        """v1 tested env config loading; v2 reads CLAUDE_STORAGE_STATE."""
        monkeypatch.setenv("CLAUDE_STORAGE_STATE", "/tmp/test_state.json")
        config = ClaudeConfig()
        assert config.storage_state == "/tmp/test_state.json"

    # v1 test_agent_initialization → v2: check selector counts
    def test_agent_selectors_count(self):
        """V1 checked INPUT_SELECTORS and RESPONSE_SELECTORS counts."""
        assert len(CLAUDE_SELECTORS.input) == 10
        assert len(CLAUDE_SELECTORS.submit) == 7
        assert len(CLAUDE_SELECTORS.response) == 9

    def test_agent_has_extract_thinking(self):
        agent = ClaudeChatAgent(ClaudeConfig())
        assert agent._extract_thinking_enabled is True

    def test_agent_thinking_disabled(self):
        agent = ClaudeChatAgent(ClaudeConfig(extract_thinking=False))
        assert agent._extract_thinking_enabled is False

    # v1 test_error_handling → v2: config accepts numeric bounds
    def test_negative_timeout_accepted(self):
        """V2 uses plain dataclasses without validate(). Negative values allowed
        at construction time (validated at runtime by Playwright/httpx timeouts)."""
        config = ClaudeConfig(timeout=-1)
        assert config.timeout == -1  # No validation on construction

    def test_zero_max_retries(self):
        config = ClaudeConfig(max_retries=0)
        assert config.max_retries == 0


class TestChatAgentComprehensiveV1Ported:
    """Adapted from v1 claude/chat-agent/test_comprehensive.py.

    V1 had three browser-based scenarios: simple, complex (3-turn), long (5-turn).
    Here we verify the data structures and history that would back those scenarios.
    """

    def test_conversation_history_context(self):
        """v1 complex test: 3-turn conversation with context dependency.
        Verify history builds correct message sequence for 3 turns."""
        from universal_agents.core.history import ConversationHistory
        from universal_agents.core.types import Message
        history = ConversationHistory(max_turns=50)

        # Turn 1: number 42
        history.add_turn(Message(role="user", content="What is the answer to life?"),
                         Message(role="assistant", content="42"))
        # Turn 2: double it → 84
        history.add_turn(Message(role="user", content="Double that number"),
                         Message(role="assistant", content="84"))
        # Turn 3: add 16 → 100
        history.add_turn(Message(role="user", content="Add 16 to that"),
                         Message(role="assistant", content="100"))

        msgs = history.get_messages_for_context()
        assert len(msgs) == 6  # 3 user + 3 assistant
        assert msgs[0]["role"] == "user"
        assert msgs[1]["content"] == "42"
        assert msgs[4]["content"] == "Add 16 to that"
        assert msgs[5]["content"] == "100"

    def test_conversation_turn_tracking(self):
        """v1 tracked turn_results with success/validation.
        V2 uses ConversationHistory.turns with success flag."""
        from universal_agents.core.history import ConversationHistory
        history = ConversationHistory(max_turns=50)

        t1 = history.add_turn("q1", "a1", processing_time_ms=100.0, success=True)
        t2 = history.add_turn("q2", "a2", processing_time_ms=200.0, success=True)
        t3 = history.add_turn("q3", "a3", processing_time_ms=150.0, success=False, error="timeout")

        turns = history.turns
        assert len(turns) == 3
        assert turns[0].success is True
        assert turns[2].success is False
        assert turns[2].error == "timeout"

    def test_agent_stats_aggregation(self):
        """v1 test_comprehensive computed stats. V2 stats via AgentStats."""
        from universal_agents.core.types import AgentStats
        stats = AgentStats(
            session_id="test-session",
            provider="claude",
            total_turns=5,
            successful_turns=4,
            failed_turns=1,
            total_processing_time_ms=1500.0,
        )
        assert stats.avg_processing_time_ms == 300.0
        assert stats.to_dict()["total_turns"] == 5


class TestChatAgentRealisticV1Ported:
    """Adapted from v1 claude/chat-agent/test_realistic.py.

    V1 had simple (3-turn), complex (5-turn), long (10-turn) scenarios.
    Verify history sliding window handles 10-turn extended dialogue.
    """

    def test_history_sliding_window_10_turns(self):
        from universal_agents.core.history import ConversationHistory
        from universal_agents.core.types import Message
        history = ConversationHistory(max_turns=5)

        # Simulate 10-turn dialogue
        for i in range(10):
            history.add_turn(
                Message(role="user", content=f"question_{i}"),
                Message(role="assistant", content=f"answer_{i}"),
            )

        # Window should only keep last 5 turns = 10 messages
        msgs = history.get_messages_for_context()
        assert len(msgs) == 10  # 5 turns × 2 messages
        assert msgs[0]["content"] == "question_5"  # First kept turn
        assert msgs[-1]["content"] == "answer_9"  # Last turn

    def test_turn_numbering_after_truncation(self):
        """V1 tracked total turns. V2 history._total_turns continues
        counting internally, but turn_count returns window size."""
        from universal_agents.core.history import ConversationHistory
        from universal_agents.core.types import Message
        history = ConversationHistory(max_turns=3)

        for i in range(7):
            history.add_turn(
                Message(role="user", content=f"q{i}"),
                Message(role="assistant", content=f"a{i}"),
            )

        # V2: turn_count = window size (len of _turns), _total_turns is internal
        assert history.turn_count == 3  # Window size
        assert history._total_turns == 7  # Internal total counter
        assert len(history.turns) == 3  # Same as turn_count


# ═══════════════════════════════════════════════════════════════
#  V1 Data Agent Tests → V2
# ═══════════════════════════════════════════════════════════════

class TestDataAgentV1Ported:
    """Adapted from v1 claude/data-agent/test_agent.py"""

    # v1 test_data_generation_input → v2 build_data_prompt
    def test_build_data_prompt_with_complex_json(self):
        """v1 DataGenerationInput.build_full_prompt() → v2 build_data_prompt()."""
        input_json = {
            "question_id": "test_001",
            "question_text": "What is the capital of France?",
            "options": ["Paris", "London", "Berlin"],
        }
        prompt = ClaudeDataAgent.build_data_prompt(
            "Transform the input JSON into the expected output format.",
            input_json=input_json,
        )
        assert "Transform the input JSON" in prompt
        assert "```json" in prompt
        assert '"question_id": "test_001"' in prompt
        assert '"options"' in prompt

    def test_build_data_prompt_serialization_round_trip(self):
        """v1 tested DataGenerationInput.to_dict(); verify prompt can be
        reconstructed from serialized input JSON."""
        original = {"name": "Test", "value": 42}
        prompt = ClaudeDataAgent.build_data_prompt("Generate", input_json=original)

        # Extract JSON back from prompt
        m = re.search(r"```json\s*([\s\S]*?)\s*```", prompt)
        assert m is not None
        roundtripped = json.loads(m.group(1))
        assert roundtripped == original

    # v1 test_data_generation_result → v2 doesn't have DataGenerationResult
    # but v2's extract_json covers the same extraction logic

    # v1 test_config_loading
    def test_data_config_defaults(self):
        config = ClaudeDataConfig()
        assert config.timeout == 300
        assert config.headless is True
        assert config.provider_name == "claude"
        assert config.extract_thinking is True

    def test_data_config_custom(self):
        config = ClaudeDataConfig(timeout=600, headless=False)
        assert config.timeout == 600
        assert config.headless is False

    # v1 test_json_extraction — adapted with v2's extract_json
    def test_json_extraction_markdown_block(self):
        text = 'Here is the result:\n```json\n{"task": "test", "value": 42}\n```'
        result = ClaudeDataAgent.extract_json(text)
        assert result == {"task": "test", "value": 42}

    def test_json_extraction_plain_block(self):
        text = 'Output:\n```\n{"status": "success"}\n```'
        result = ClaudeDataAgent.extract_json(text)
        assert result == {"status": "success"}

    def test_json_extraction_multiple_blocks(self):
        """v1: multiple JSON blocks → should get first valid one."""
        text = '```json\n{"first": true}\n```\nAnd also:\n```json\n{"second": true}\n```'
        result = ClaudeDataAgent.extract_json(text)
        assert result == {"first": True}

    def test_json_extraction_raw_in_text(self):
        text = 'The answer is {"answer": "Paris", "confidence": 0.95}'
        result = ClaudeDataAgent.extract_json(text)
        assert result == {"answer": "Paris", "confidence": 0.95}

    def test_json_extraction_returns_none_for_no_json(self):
        assert ClaudeDataAgent.extract_json("no json here at all") is None

    # v1 test_output_saving → v2 uses core.output module
    def test_output_module_exists(self):
        """v1 saved raw_response.md, conversation.json, output.json.
        V2 uses core.output functions for file saving."""
        from universal_agents.core import output
        assert hasattr(output, "save_turn")
        assert hasattr(output, "save_summary")
        assert hasattr(output, "save_full_results")

    # v1 test_example_prompt_parsing — BREAK dataset style
    def test_break_dataset_prompt(self):
        """v1 tested parsing BREAK dataset example. Adapt to v2 build_data_prompt."""
        example_input = {
            "question_id": "NLVR2_train_train-1023-2-1",
            "question_text": "If an image shows wine bottle, glass, grapes and green leaves.",
            "decomposition": "return wine bottle ;return glass ;return grapes ;return leaves",
            "operators": "['select', 'select', 'select', 'select', 'filter']",
            "split": "train",
        }
        example_prompt = (
            "# BREAK Dataset Transformation Prompt v2 (ESV-RAG Aligned)\n\n"
            "## Role\n"
            "**You are a Senior Cognitive AI Researcher and ESV-RAG Training Data Specialist**\n\n"
            "## Task Description\n"
            "Transform BREAK QDMR decompositions into training data for ESV-RAG.\n\n"
            "## Instructions\n"
            "Complete all four tasks and output JSON for each."
        )

        full_prompt = ClaudeDataAgent.build_data_prompt(
            example_prompt, input_json=example_input
        )
        assert "BREAK Dataset Transformation" in full_prompt
        assert '"question_id": "NLVR2_train_train-1023-2-1"' in full_prompt
        assert "```json" in full_prompt
        assert "ESV-RAG" in full_prompt


# ═══════════════════════════════════════════════════════════════
#  V1 Translator Agent Tests → V2
# ═══════════════════════════════════════════════════════════════

class TestTranslatorV1Ported:
    """Adapted from v1 claude/translator-agent/test_agent.py"""

    # v1 test_config_defaults
    def test_config_defaults(self):
        config = ClaudeTranslatorConfig()
        assert config.provider_name == "claude"
        assert config.base_url == "https://claude.ai/new"
        assert config.timeout == 600
        assert config.source_language == "ja"
        assert config.target_language == "en"
        assert config.translation_mode == "book"
        assert config.chunk_size == 2000
        assert config.max_turns_per_conversation == 20

    # v1 test_config_transcript_mode → v2 stores mode but doesn't auto-adjust chunk_size
    def test_config_transcript_mode(self):
        """V1 auto-adjusted chunk_size=500 for transcript mode.
        V2 stores the mode; callers set chunk_size themselves."""
        config = ClaudeTranslatorConfig(
            translation_mode="transcript", chunk_size=500
        )
        assert config.translation_mode == "transcript"
        assert config.chunk_size == 500

    # v1 test_config_validation → v2 has no validate() on configs
    def test_config_accepts_modes(self):
        """V2 doesn't validate mode at config level — runtime responsibility."""
        cfg_book = ClaudeTranslatorConfig(translation_mode="book")
        cfg_transcript = ClaudeTranslatorConfig(translation_mode="transcript")
        assert cfg_book.translation_mode == "book"
        assert cfg_transcript.translation_mode == "transcript"

    # v1 test_transcript_chunking — utility function tested standalone
    def test_transcript_chunking(self):
        """v1 chunked SRT text by block boundaries.
        Reproduce the chunking logic inline as a utility test."""

        def chunk_transcript_text(text, lines_per_chunk=50):
            blocks = re.split(r"\n\s*\n", text.strip())
            chunks, current = [], []
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                current.append(block)
                if len(current) >= lines_per_chunk:
                    chunks.append("\n\n".join(current))
                    current = []
            if current:
                chunks.append("\n\n".join(current))
            return chunks

        # Create 100 fake SRT blocks
        blocks = []
        for i in range(100):
            blocks.append(
                f"{i}\n00:0{i // 10}:{i % 10 * 6:02d},000 --> 00:0{i // 10}:{i % 10 * 6 + 5:02d},000\nテスト字幕 {i}"
            )
        text = "\n\n".join(blocks)

        chunks = chunk_transcript_text(text, lines_per_chunk=20)
        assert len(chunks) == 5

        # Verify all content preserved
        reassembled = "\n\n".join(chunks)
        for i in range(100):
            assert f"テスト字幕 {i}" in reassembled

    # v1 test_detect_srt_format
    def test_detect_srt_format(self):
        """v1 used regex to detect SRT vs plain text."""
        srt_pattern = r"\d+\s*\n\d{2}:\d{2}:\d{2}"

        srt_text = "1\n00:00:01,000 --> 00:00:05,000\nHello world"
        plain_text = "This is just plain text without any timestamps."

        assert bool(re.search(srt_pattern, srt_text[:500]))
        assert not bool(re.search(srt_pattern, plain_text[:500]))

    # v1 test_data_classes
    def test_translation_chunk_text(self):
        chunk = TranslationChunk(chunk_id="test_001", chunk_index=0, source_text="テスト文")
        assert chunk.chunk_id == "test_001"
        assert chunk.source_text == "テスト文"

    def test_translation_chunk_file(self):
        chunk = TranslationChunk(chunk_id="test_002", chunk_index=1, source_file="/path/to/page.pdf")
        assert chunk.source_file == "/path/to/page.pdf"

    def test_translation_result_dict(self):
        result = TranslationResult(
            chunk_id="test_001",
            chunk_index=0,
            success=True,
            source_text="テスト文",
            translated_text="Test text",
            conversation_index=0,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["translated_text"] == "Test text"
        assert d["conversation_index"] == 0

    # v1 test_progress_state
    def test_progress_state_full_lifecycle(self):
        """v1 tested create → mark → save → load → resume → complete."""
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_path = Path(tmpdir) / "progress.json"

            # Create and save
            progress = ProgressState(document_id="test_doc", total_chunks=10)
            progress.mark_completed(0)
            progress.mark_completed(1)
            progress.mark_completed(2)
            progress.current_conversation_index = 0
            progress.current_turn_in_conversation = 3
            progress.save(progress_path)

            assert progress_path.exists()

            # Load and verify
            loaded = ProgressState.load(progress_path)
            assert loaded is not None
            assert loaded.document_id == "test_doc"
            assert loaded.total_chunks == 10
            assert loaded.completed_chunks == [0, 1, 2]
            assert loaded.current_conversation_index == 0
            assert loaded.current_turn_in_conversation == 3
            assert loaded.is_chunk_completed(0) is True
            assert loaded.is_chunk_completed(3) is False
            assert loaded.is_complete is False

            # Complete remaining
            for i in range(3, 10):
                loaded.mark_completed(i)
            assert loaded.is_complete is True

    def test_progress_state_load_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = ProgressState.load(Path(tmpdir) / "missing.json")
            assert missing is None

    def test_progress_state_duplicate_mark(self):
        """Mark same chunk twice shouldn't duplicate."""
        state = ProgressState(document_id="d1", total_chunks=5)
        state.mark_completed(2)
        state.mark_completed(2)
        assert state.completed_chunks == [2]

    # v1 test_env_config → v2 reads env vars via dataclass factory
    def test_env_storage_state(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_STORAGE_STATE", "/tmp/test.json")
        config = ClaudeTranslatorConfig()
        assert config.storage_state == "/tmp/test.json"

    def test_overlap_chars_default(self):
        config = ClaudeTranslatorConfig()
        assert config.overlap_chars == 100


class TestTranslatorAgentV1Ported:
    """Adapted from v1 translator agent — agent-level behavior."""

    def test_should_split_at_threshold(self):
        agent = ClaudeTranslatorAgent(ClaudeTranslatorConfig(max_turns_per_conversation=5))
        agent.turn_in_conversation = 4
        assert not agent.should_split_conversation()
        agent.turn_in_conversation = 5
        assert agent.should_split_conversation()

    def test_get_full_translation_skips_failures(self):
        agent = ClaudeTranslatorAgent()
        agent.results = [
            TranslationResult(chunk_id="c0", chunk_index=0, success=True, translated_text="Part 1"),
            TranslationResult(chunk_id="c1", chunk_index=1, success=False, error="timeout"),
            TranslationResult(chunk_id="c2", chunk_index=2, success=True, translated_text="Part 3"),
        ]
        full = agent.get_full_translation()
        assert full == "Part 1\n\nPart 3"
        assert "timeout" not in full

    def test_export_results_json_structure(self, tmp_path):
        agent = ClaudeTranslatorAgent()
        agent._agent = MagicMock()
        agent._agent.session_id = "v1-compat-session"
        agent.results = [
            TranslationResult(chunk_id="c0", chunk_index=0, success=True, translated_text="ok"),
            TranslationResult(chunk_id="c1", chunk_index=1, success=False, error="fail"),
        ]
        out = agent.export_results(tmp_path / "results.json")
        data = json.loads(out.read_text())
        assert data["total_chunks"] == 2
        assert data["successful_chunks"] == 1
        assert data["session_id"] == "v1-compat-session"
        assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_translate_text_tracks_turn_count(self):
        """v1 tracked turns within conversation for splitting decisions."""
        agent = ClaudeTranslatorAgent(ClaudeTranslatorConfig(max_turns_per_conversation=3))
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(return_value="translated")
        agent._agent = mock_inner

        for i in range(3):
            chunk = TranslationChunk(chunk_id=f"c{i}", chunk_index=i, source_text=f"text_{i}")
            await agent.translate_text(chunk)

        assert agent.turn_in_conversation == 3
        assert agent.should_split_conversation()
        assert len(agent.results) == 3
        assert all(r.success for r in agent.results)

    @pytest.mark.asyncio
    async def test_translate_text_continue_prompt(self):
        """v1 used continue_prompt for non-first turns."""
        agent = ClaudeTranslatorAgent()
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(return_value="ok")
        agent._agent = mock_inner

        chunk = TranslationChunk(chunk_id="c1", chunk_index=1, source_text="more text")
        await agent.translate_text(chunk, continue_prompt="Continue translating:")

        called_prompt = mock_inner.chat.call_args[0][0]
        assert "Continue translating:" in called_prompt
        assert "more text" in called_prompt

    @pytest.mark.asyncio
    async def test_translate_text_error_recording(self):
        """v1 logged errors per result. Verify v2 records error details."""
        agent = ClaudeTranslatorAgent()
        mock_inner = AsyncMock()
        mock_inner.chat = AsyncMock(side_effect=RuntimeError("network_error"))
        agent._agent = mock_inner

        chunk = TranslationChunk(chunk_id="c0", chunk_index=0, source_text="input")
        result = await agent.translate_text(chunk)

        assert not result.success
        assert result.error == "network_error"
        assert result.processing_time_ms > 0
        assert len(agent.results) == 1

    @pytest.mark.asyncio
    async def test_translate_file_missing(self):
        """v1 checked for file existence before upload."""
        agent = ClaudeTranslatorAgent()
        agent._agent = AsyncMock()

        chunk = TranslationChunk(chunk_id="c0", chunk_index=0, source_file="/nonexistent.pdf")
        result = await agent.translate_file(chunk)

        assert not result.success
        assert "not found" in result.error


# ═══════════════════════════════════════════════════════════════
#  V1 Job Runner Utilities → V2 Standalone Tests
# ═══════════════════════════════════════════════════════════════

class TestJobRunnerUtilities:
    """Tests for utility patterns used in v1 job runners
    (specialization, book-translation, transcript-translation)."""

    def test_json_extraction_nested(self):
        """v1 specialization runner extracted JSON from 2-turn pipeline responses."""
        response = """Here is the specialized training data:

```json
{
    "task1_output": {
        "question": "What is Paris?",
        "answer": "Capital of France"
    },
    "task2_output": {
        "reasoning_chain": ["step1", "step2"]
    }
}
```

The transformation is complete."""
        result = ClaudeDataAgent.extract_json(response)
        assert result["task1_output"]["answer"] == "Capital of France"
        assert len(result["task2_output"]["reasoning_chain"]) == 2

    def test_progress_resume_pattern(self):
        """v1 runners supported --resume via ProgressState.
        Verify the resume pattern works: save partial → load → skip completed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            progress_path = Path(tmpdir) / "progress.json"

            # Simulate partial run: completed 3 of 10
            progress = ProgressState(document_id="batch_001", total_chunks=10)
            for i in range(3):
                progress.mark_completed(i)
            progress.save(progress_path)

            # Resume: load and find unprocessed
            resumed = ProgressState.load(progress_path)
            unprocessed = [
                i for i in range(resumed.total_chunks)
                if not resumed.is_chunk_completed(i)
            ]
            assert unprocessed == [3, 4, 5, 6, 7, 8, 9]

    def test_translation_result_timestamp(self):
        """v1 DataGenerationResult had timestamp. V2 TranslationResult too."""
        result = TranslationResult(
            chunk_id="c0", chunk_index=0, success=True, translated_text="ok"
        )
        d = result.to_dict()
        assert "timestamp" in d
        # Should be ISO format
        assert "T" in d["timestamp"]

    def test_config_inheritance_chain(self):
        """Verify the full config inheritance chain that v1 relied on:
        BaseConfig → BrowserConfig → ClaudeConfig → ClaudeDataConfig → ClaudeTranslatorConfig"""
        config = ClaudeTranslatorConfig()
        assert isinstance(config, BaseConfig)
        assert isinstance(config, BrowserConfig)
        assert isinstance(config, ClaudeConfig)
        assert isinstance(config, ClaudeDataConfig)
        assert isinstance(config, ClaudeTranslatorConfig)

    def test_data_agent_inherits_claude_selectors(self):
        """v1 data agent used same selectors as chat agent. Verify in v2."""
        assert ClaudeDataAgent.SELECTORS is CLAUDE_SELECTORS
        assert ClaudeChatAgent.SELECTORS is CLAUDE_SELECTORS
