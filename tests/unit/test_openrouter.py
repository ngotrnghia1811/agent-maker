"""Unit tests for OpenRouter agents."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from universal_agents.providers.openrouter.chat import OpenRouterChatAgent
from universal_agents.providers.openrouter.config import (
    OpenRouterConfig,
    OpenRouterDataConfig,
)
from universal_agents.providers.openrouter.data import OpenRouterDataAgent
from universal_agents.core.exceptions import APIError


class TestOpenRouterConfig:
    def test_defaults(self):
        config = OpenRouterConfig()
        assert config.provider_name == "openrouter"
        assert config.base_url == "https://openrouter.ai/api/v1"
        assert config.model == "anthropic/claude-3-5-sonnet"
        assert len(config.fallback_models) >= 2

    def test_data_config(self):
        config = OpenRouterDataConfig()
        assert config.timeout == 600
        assert config.max_tokens == 16384
        assert config.enable_thinking is True
        assert config.thinking_budget == 10000


class TestOpenRouterChatAgent:
    def test_headers_include_referer(self):
        config = OpenRouterConfig(api_key="sk-test")
        agent = OpenRouterChatAgent(config)
        headers = agent._get_headers()
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers
        assert headers["Authorization"] == "Bearer sk-test"


class TestOpenRouterDataAgent:
    def test_build_data_prompt(self):
        agent = OpenRouterDataAgent()
        prompt = agent.build_data_prompt(
            "Generate users",
            input_json={"count": 3},
            final_remind="Return valid JSON only",
        )
        assert "Generate users" in prompt
        assert '"count": 3' in prompt
        assert "Return valid JSON only" in prompt

    def test_parse_json_response_code_block(self):
        response = 'Here is the data:\n```json\n{"users": [1, 2]}\n```\nDone.'
        result = OpenRouterDataAgent.parse_json_response(response)
        assert result == {"users": [1, 2]}

    def test_parse_json_response_raw(self):
        response = '{"key": "value"}'
        result = OpenRouterDataAgent.parse_json_response(response)
        assert result == {"key": "value"}

    def test_parse_json_response_invalid(self):
        result = OpenRouterDataAgent.parse_json_response("no json here")
        assert result is None

    def test_build_request_body_with_thinking(self):
        config = OpenRouterDataConfig(
            api_key="sk-test",
            model="anthropic/claude-3-5-sonnet",
            enable_thinking=True,
            thinking_budget=5000,
        )
        agent = OpenRouterDataAgent(config)
        body = agent._build_request_body([{"role": "user", "content": "hi"}])
        assert "thinking" in body
        assert body["thinking"]["budget_tokens"] == 5000

    def test_build_request_body_no_thinking_non_claude(self):
        config = OpenRouterDataConfig(
            api_key="sk-test",
            model="openai/gpt-4",
            enable_thinking=True,
        )
        agent = OpenRouterDataAgent(config)
        body = agent._build_request_body([{"role": "user", "content": "hi"}])
        assert "thinking" not in body
