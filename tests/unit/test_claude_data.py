"""Unit tests for Claude data agent JSON extraction and prompt building."""

import pytest

from universal_agents.providers.claude.data import ClaudeDataAgent
from universal_agents.providers.claude.config import ClaudeDataConfig


class TestClaudeDataConfig:
    def test_inherits_claude_config(self):
        config = ClaudeDataConfig()
        assert config.provider_name == "claude"
        assert config.timeout == 300
        assert config.extract_thinking is True

    def test_base_url(self):
        config = ClaudeDataConfig()
        assert config.base_url == "https://claude.ai/new"


class TestClaudeDataAgent:
    def test_build_data_prompt_basic(self):
        prompt = ClaudeDataAgent.build_data_prompt("Generate users")
        assert "Generate users" in prompt
        assert "```json" not in prompt

    def test_build_data_prompt_with_json(self):
        prompt = ClaudeDataAgent.build_data_prompt(
            "Generate users",
            input_json={"count": 5, "locale": "en_US"},
        )
        assert "Generate users" in prompt
        assert "```json" in prompt
        assert '"count": 5' in prompt
        assert '"locale": "en_US"' in prompt

    def test_build_data_prompt_with_remind(self):
        prompt = ClaudeDataAgent.build_data_prompt(
            "Generate data",
            final_remind="Return valid JSON only",
        )
        assert "Return valid JSON only" in prompt

    def test_build_data_prompt_full(self):
        prompt = ClaudeDataAgent.build_data_prompt(
            "Generate users",
            input_json=[1, 2, 3],
            final_remind="JSON only",
        )
        assert "Generate users" in prompt
        assert "```json" in prompt
        assert "JSON only" in prompt

    def test_extract_json_code_block(self):
        text = 'Here:\n```json\n{"key": "value"}\n```\nDone.'
        result = ClaudeDataAgent.extract_json(text)
        assert result == {"key": "value"}

    def test_extract_json_plain_block(self):
        text = 'Here:\n```\n[1, 2, 3]\n```'
        result = ClaudeDataAgent.extract_json(text)
        assert result == [1, 2, 3]

    def test_extract_json_raw(self):
        text = '{"a": 1}'
        result = ClaudeDataAgent.extract_json(text)
        assert result == {"a": 1}

    def test_extract_json_raw_array(self):
        text = "Some text [1, 2, 3] more text"
        result = ClaudeDataAgent.extract_json(text)
        assert result == [1, 2, 3]

    def test_extract_json_none(self):
        result = ClaudeDataAgent.extract_json("no json here at all")
        assert result is None

    def test_extract_json_prefers_code_block(self):
        text = '{"outer": true}\n```json\n{"inner": true}\n```'
        result = ClaudeDataAgent.extract_json(text)
        assert result == {"inner": True}
