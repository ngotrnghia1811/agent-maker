"""Unit tests for browser provider configs and selectors."""

import pytest

from universal_agents.providers.gemini.config import GeminiConfig
from universal_agents.providers.gemini.selectors import GEMINI_SELECTORS
from universal_agents.providers.gpt.config import GPTConfig
from universal_agents.providers.gpt.selectors import GPT_SELECTORS


class TestGeminiConfig:
    def test_defaults(self):
        config = GeminiConfig()
        assert config.provider_name == "gemini"
        assert config.base_url == "https://gemini.google.com"
        assert config.extract_thinking is True

    def test_required_model(self):
        config = GeminiConfig(required_model="pro")
        assert config.required_model == "pro"


class TestGeminiSelectors:
    def test_has_all_fields(self):
        assert len(GEMINI_SELECTORS.input) > 0
        assert len(GEMINI_SELECTORS.submit) > 0
        assert len(GEMINI_SELECTORS.response) > 0
        assert GEMINI_SELECTORS.loading is not None


class TestGPTConfig:
    def test_defaults(self):
        config = GPTConfig()
        assert config.provider_name == "gpt"
        assert config.base_url == "https://chatgpt.com"


class TestGPTSelectors:
    def test_has_required_selectors(self):
        assert len(GPT_SELECTORS.input) > 0
        assert len(GPT_SELECTORS.submit) > 0
        assert len(GPT_SELECTORS.response) > 0

    def test_primary_selector(self):
        assert "#prompt-textarea" in GPT_SELECTORS.input
