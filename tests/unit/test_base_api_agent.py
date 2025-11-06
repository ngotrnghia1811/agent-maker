"""Unit tests for base API agent."""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from universal_agents.api.base_api_agent import BaseAPIAgent
from universal_agents.core.config import APIConfig
from universal_agents.core.exceptions import APIError, RateLimitError


class ConcreteAPIAgent(BaseAPIAgent):
    """Concrete implementation for testing."""
    pass


class TestBaseAPIAgent:
    def make_agent(self, **kwargs) -> ConcreteAPIAgent:
        config = APIConfig(
            provider_name="test",
            api_key="test-key",
            base_url="https://api.test.com",
            model="test-model",
            **kwargs,
        )
        return ConcreteAPIAgent(config)

    def test_get_headers(self):
        agent = self.make_agent()
        headers = agent._get_headers()
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"

    def test_build_request_body(self):
        agent = self.make_agent(temperature=0.5, max_tokens=100)
        body = agent._build_request_body(
            [{"role": "user", "content": "hi"}]
        )
        assert body["model"] == "test-model"
        assert body["temperature"] == 0.5
        assert body["max_tokens"] == 100
        assert body["messages"] == [{"role": "user", "content": "hi"}]

    def test_build_request_body_optional_fields(self):
        agent = self.make_agent(top_p=0.9, frequency_penalty=0.5, presence_penalty=0.3)
        body = agent._build_request_body([])
        assert body["top_p"] == 0.9
        assert body["frequency_penalty"] == 0.5
        assert body["presence_penalty"] == 0.3

    def test_build_request_body_defaults_omit_optional(self):
        agent = self.make_agent()
        body = agent._build_request_body([])
        assert "top_p" not in body
        assert "frequency_penalty" not in body
        assert "presence_penalty" not in body

    def test_get_messages_for_request_includes_system(self):
        agent = self.make_agent(system_prompt="Be helpful")
        msgs = agent._get_messages_for_request()
        assert msgs[0] == {"role": "system", "content": "Be helpful"}

    def test_parse_response(self):
        agent = self.make_agent()
        data = {"choices": [{"message": {"role": "assistant", "content": "hello"}}]}
        content, thinking = agent._parse_response(data)
        assert content == "hello"
        assert thinking is None

    def test_parse_response_no_choices_raises(self):
        agent = self.make_agent()
        with pytest.raises(APIError):
            agent._parse_response({"choices": []})

    def test_parse_stream_chunk(self):
        agent = self.make_agent()
        chunk = {"choices": [{"delta": {"content": "hi"}}]}
        assert agent._parse_stream_chunk(chunk) == "hi"

    def test_parse_stream_chunk_empty(self):
        agent = self.make_agent()
        assert agent._parse_stream_chunk({"choices": []}) == ""

    @pytest.mark.asyncio
    async def test_chat_sync(self):
        agent = self.make_agent()
        response_data = {
            "choices": [{"message": {"content": "response text"}}]
        }

        with patch.object(
            agent, "_make_request", new_callable=AsyncMock, return_value=response_data
        ):
            result = await agent.chat("hello")

        assert result == "response text"
        assert agent.history.turn_count == 1

    @pytest.mark.asyncio
    async def test_chat_records_history(self):
        agent = self.make_agent()
        response_data = {
            "choices": [{"message": {"content": "resp1"}}]
        }

        with patch.object(
            agent, "_make_request", new_callable=AsyncMock, return_value=response_data
        ):
            await agent.chat("q1")
            await agent.chat("q2")

        assert agent.history.turn_count == 2
        turns = agent.get_turns()
        assert turns[0].user_message.content == "q1"
        assert turns[1].user_message.content == "q2"

    @pytest.mark.asyncio
    async def test_check_response_rate_limit(self):
        agent = self.make_agent()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"retry-after": "30"}
        mock_resp.text = "rate limited"
        with pytest.raises(RateLimitError) as exc_info:
            agent._check_response(mock_resp)
        assert "429" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_response_api_error(self):
        agent = self.make_agent()
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "internal server error"
        with pytest.raises(APIError):
            agent._check_response(mock_resp)

    @pytest.mark.asyncio
    async def test_close(self):
        agent = self.make_agent()
        agent._client = AsyncMock()
        agent._client.is_closed = False
        await agent.close()
        agent._client.aclose.assert_awaited_once()
