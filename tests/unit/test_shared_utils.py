"""Unit tests for shared JSON extraction and prompt building utilities."""

import pytest

from universal_agents.core.json_utils import extract_json
from universal_agents.core.prompt_builder import build_data_prompt


class TestExtractJson:
    """Tests for extract_json() — the shared JSON extraction function."""

    def test_json_code_block(self):
        text = 'Here:\n```json\n{"key": "value"}\n```\nDone.'
        assert extract_json(text) == {"key": "value"}

    def test_generic_code_block(self):
        text = 'Here:\n```\n[1, 2, 3]\n```'
        assert extract_json(text) == [1, 2, 3]

    def test_raw_json_object(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_raw_json_array_in_text(self):
        assert extract_json("Some text [1, 2, 3] more text") == [1, 2, 3]

    def test_no_json_returns_none(self):
        assert extract_json("no json here at all") is None

    def test_prefers_code_block_over_raw(self):
        text = '{"outer": true}\n```json\n{"inner": true}\n```'
        assert extract_json(text) == {"inner": True}

    def test_nested_json(self):
        text = '```json\n{"users": [{"name": "Alice"}, {"name": "Bob"}]}\n```'
        result = extract_json(text)
        assert len(result["users"]) == 2
        assert result["users"][0]["name"] == "Alice"

    def test_invalid_json_in_code_block_tries_next(self):
        text = '```json\nnot valid json\n```\n```json\n{"valid": true}\n```'
        assert extract_json(text) == {"valid": True}

    def test_multiline_json(self):
        text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        assert extract_json(text) == {"a": 1, "b": 2}

    def test_empty_string(self):
        assert extract_json("") is None

    def test_direct_raw_json(self):
        """Direct JSON string with no surrounding text."""
        assert extract_json('{"status": "ok"}') == {"status": "ok"}

    def test_raw_json_string(self):
        """Raw JSON without code fencing."""
        assert extract_json('["a", "b", "c"]') == ["a", "b", "c"]


class TestBuildDataPrompt:
    """Tests for build_data_prompt() — the shared prompt builder."""

    def test_basic_prompt(self):
        result = build_data_prompt("Generate users")
        assert result == "Generate users"
        assert "```json" not in result

    def test_with_json_input(self):
        result = build_data_prompt(
            "Generate users",
            input_json={"count": 5, "locale": "en_US"},
        )
        assert "Generate users" in result
        assert "```json" in result
        assert '"count": 5' in result
        assert '"locale": "en_US"' in result

    def test_with_final_remind(self):
        result = build_data_prompt(
            "Generate data",
            final_remind="Return valid JSON only",
        )
        assert "Generate data" in result
        assert "Return valid JSON only" in result

    def test_full_prompt(self):
        result = build_data_prompt(
            "Generate users",
            input_json=[1, 2, 3],
            final_remind="JSON only",
        )
        assert "Generate users" in result
        assert "```json" in result
        assert "JSON only" in result

    def test_unicode_json(self):
        result = build_data_prompt(
            "Translate",
            input_json={"text": "こんにちは"},
        )
        assert "こんにちは" in result

    def test_empty_dict(self):
        result = build_data_prompt("Test", input_json={})
        assert "```json" in result
        assert "{}" in result

    def test_none_json_no_block(self):
        result = build_data_prompt("Test", input_json=None)
        assert "```json" not in result
