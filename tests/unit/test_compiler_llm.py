"""Tests for CompilerLLM — lightweight LLM client for custom answer interpretation."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from universal_agents.compiler.compiler_llm import CompilerLLM, _DEFAULTS


# ======================================================================
# _parse_json_value
# ======================================================================

class TestParseJsonValue:
    def test_simple_string_value(self):
        assert CompilerLLM._parse_json_value('{"value": "openai"}') == "openai"

    def test_boolean_value(self):
        assert CompilerLLM._parse_json_value('{"value": true}') is True

    def test_list_value(self):
        assert CompilerLLM._parse_json_value('{"value": ["a", "b"]}') == ["a", "b"]

    def test_int_value(self):
        assert CompilerLLM._parse_json_value('{"value": 42}') == 42

    def test_null_value(self):
        assert CompilerLLM._parse_json_value('{"value": null}') is None

    def test_markdown_fenced_json(self):
        text = '```json\n{"value": "claude"}\n```'
        assert CompilerLLM._parse_json_value(text) == "claude"

    def test_markdown_fenced_no_lang(self):
        text = '```\n{"value": "gemini"}\n```'
        assert CompilerLLM._parse_json_value(text) == "gemini"

    def test_dict_without_value_key(self):
        result = CompilerLLM._parse_json_value('{"provider": "openai"}')
        assert result == {"provider": "openai"}

    def test_invalid_json_returns_string(self):
        assert CompilerLLM._parse_json_value("not json at all") == "not json at all"

    def test_whitespace_handling(self):
        assert CompilerLLM._parse_json_value('  {"value": "ok"}  ') == "ok"


# ======================================================================
# Constructor
# ======================================================================

class TestCompilerLLMInit:
    def test_defaults(self):
        llm = CompilerLLM()
        assert llm.provider == _DEFAULTS["provider"]
        assert llm.model == _DEFAULTS["model"]

    def test_custom_provider_and_model(self):
        llm = CompilerLLM(provider="openai", model="gpt-4o")
        assert llm.provider == "openai"
        assert llm.model == "gpt-4o"


# ======================================================================
# Graceful degradation — no API key
# ======================================================================

class TestGracefulDegradation:
    def test_interpret_no_api_key_returns_raw(self):
        """Without an API key, interpret_custom returns the raw user text."""
        llm = CompilerLLM(provider="openrouter")
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}, clear=False):
            result = asyncio.run(
                llm.interpret_custom(
                    question_text="Pick provider",
                    field_name="provider_preference",
                    user_text="I want to use Claude",
                    valid_values=["openai", "openrouter", "claude"],
                )
            )
        # Should gracefully return raw text (which goes through _parse_json_value
        # but since it's the prompt text, not JSON, it returns as-is)
        assert isinstance(result, str)

    def test_refine_no_api_key_returns_raw(self):
        llm = CompilerLLM(provider="openai")
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            result = asyncio.run(llm.refine_system_prompt("Be a helpful assistant"))
        assert "helpful assistant" in result


# ======================================================================
# HTTP call mocking
# ======================================================================

class TestCallMocking:
    @pytest.fixture
    def mock_response(self):
        """Create a mock HTTP response."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "choices": [{"message": {"content": '{"value": "openai"}'}}]
        }
        return resp

    def test_interpret_custom_with_api_key(self, mock_response):
        llm = CompilerLLM(provider="openrouter")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        llm._client = mock_client

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-12345678"}, clear=False):
            result = asyncio.run(
                llm.interpret_custom(
                    question_text="Pick provider",
                    field_name="provider_preference",
                    user_text="I want OpenAI",
                    valid_values=["openai", "openrouter"],
                )
            )

        assert result == "openai"
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        assert "Bearer test-key-12345678" in call_kwargs[1]["headers"]["Authorization"]

    def test_refine_system_prompt_with_api_key(self, mock_response):
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "You are a professional code reviewer..."}}]
        }
        llm = CompilerLLM(provider="openai")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        llm._client = mock_client

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test123456789"}, clear=False):
            result = asyncio.run(llm.refine_system_prompt("review my code"))

        assert "code reviewer" in result

    def test_explain_compilation(self, mock_response):
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OpenAI was selected because..."}}]
        }
        llm = CompilerLLM(provider="openrouter")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        llm._client = mock_client

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-12345678"}, clear=False):
            result = asyncio.run(
                llm.explain_compilation(
                    provider="openai",
                    agent_class="OpenAIChatAgent",
                    capabilities=["streaming", "thinking"],
                )
            )

        assert "OpenAI" in result

    def test_http_error_graceful_degradation(self, mock_response):
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        llm = CompilerLLM(provider="openrouter")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        llm._client = mock_client

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-12345678"}, clear=False):
            result = asyncio.run(
                llm.interpret_custom(
                    question_text="Pick provider",
                    field_name="provider_preference",
                    user_text="I want OpenAI",
                )
            )

        # Should return raw prompt text (graceful degradation)
        assert isinstance(result, str)

    def test_empty_choices_graceful(self, mock_response):
        mock_response.json.return_value = {"choices": []}
        llm = CompilerLLM(provider="openrouter")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        llm._client = mock_client

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-12345678"}, clear=False):
            result = asyncio.run(
                llm.interpret_custom(
                    question_text="Pick provider",
                    field_name="provider_preference",
                    user_text="I want OpenAI",
                )
            )

        assert isinstance(result, str)

    def test_openrouter_adds_extra_headers(self, mock_response):
        llm = CompilerLLM(provider="openrouter")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        llm._client = mock_client

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-12345678"}, clear=False):
            asyncio.run(llm.interpret_custom("q", "f", "t"))

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs[1]["headers"]
        assert "HTTP-Referer" in headers
        assert "X-Title" in headers

    def test_openai_no_extra_headers(self, mock_response):
        llm = CompilerLLM(provider="openai")
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        llm._client = mock_client

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test123456789"}, clear=False):
            asyncio.run(llm.interpret_custom("q", "f", "t"))

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs[1]["headers"]
        assert "HTTP-Referer" not in headers


# ======================================================================
# QuestionFlow integration with CompilerLLM
# ======================================================================

class TestQuestionFlowLLMIntegration:
    def test_question_flow_accepts_compiler_llm(self):
        """QuestionFlow constructor accepts a compiler_llm parameter."""
        from universal_agents.compiler.question_flow import QuestionFlow
        from universal_agents.compiler.auth_detector import AuthDetector, AuthStatus
        import io

        det = AuthDetector.__new__(AuthDetector)
        det.detect = lambda: AuthStatus(available={"openai_key": True}, details={})

        llm = CompilerLLM(provider="openai", model="gpt-4o")
        flow = QuestionFlow(
            auth_detector=det,
            input_fn=lambda p: "1",
            output=io.StringIO(),
            compiler_llm=llm,
        )
        assert flow._compiler_llm is llm

    def test_question_flow_default_no_llm(self):
        """QuestionFlow default has no CompilerLLM."""
        from universal_agents.compiler.question_flow import QuestionFlow
        from universal_agents.compiler.auth_detector import AuthDetector, AuthStatus
        import io

        det = AuthDetector.__new__(AuthDetector)
        det.detect = lambda: AuthStatus(available={"openai_key": True}, details={})

        flow = QuestionFlow(
            auth_detector=det,
            input_fn=lambda p: "1",
            output=io.StringIO(),
        )
        assert flow._compiler_llm is None
