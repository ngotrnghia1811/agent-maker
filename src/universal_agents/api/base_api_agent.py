"""Abstract base class for HTTP API agents."""

import json
import logging
import time
from datetime import datetime
from typing import AsyncGenerator, Optional

import httpx

from ..core.base_agent import BaseChatAgent
from ..core.config import APIConfig
from ..core.exceptions import APIError, RateLimitError
from ..core.retry import retry
from ..core.types import Message

logger = logging.getLogger(__name__)


class BaseAPIAgent(BaseChatAgent):
    """Shared logic for all HTTP API chat agents.

    Subclasses must set:
      - ENDPOINT: the chat completions path (e.g. "/chat/completions")
      - _get_headers(): returns request headers dict

    Subclasses may override:
      - _build_request_body(): customize request payload
      - _parse_response(): extract content from response JSON
      - _parse_stream_chunk(): extract content from a streaming chunk
    """

    ENDPOINT: str = "/chat/completions"

    def __init__(self, config: APIConfig):
        super().__init__(config)
        self.api_config = config
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.api_config.timeout)
        return self._client

    def _get_headers(self) -> dict[str, str]:
        """Return request headers. Override in subclasses."""
        return {
            "Authorization": f"Bearer {self.api_config.api_key}",
            "Content-Type": "application/json",
        }

    def _build_request_body(self, messages: list[dict[str, str]], **kwargs) -> dict:
        """Build the JSON request body."""
        body: dict = {
            "model": self.api_config.model,
            "messages": messages,
            "temperature": self.api_config.temperature,
            "max_tokens": self.api_config.max_tokens,
        }
        if self.api_config.top_p != 1.0:
            body["top_p"] = self.api_config.top_p
        if self.api_config.frequency_penalty != 0.0:
            body["frequency_penalty"] = self.api_config.frequency_penalty
        if self.api_config.presence_penalty != 0.0:
            body["presence_penalty"] = self.api_config.presence_penalty
        body.update(kwargs)
        return body

    def _get_messages_for_request(self) -> list[dict[str, str]]:
        """Get conversation messages formatted for the API, with system prompt."""
        messages: list[dict[str, str]] = []
        if self.api_config.system_prompt:
            messages.append({"role": "system", "content": self.api_config.system_prompt})
        messages.extend(self.history.get_messages_for_context())
        return messages

    def _parse_response(self, data: dict) -> tuple[str, Optional[str]]:
        """Extract content and optional thinking from response JSON.

        Returns:
            (content, thinking) tuple.
        """
        choices = data.get("choices", [])
        if not choices:
            raise APIError("No choices in API response")
        content = choices[0].get("message", {}).get("content", "")
        return content, None

    def _parse_stream_chunk(self, data: dict) -> str:
        """Extract content from a single streaming chunk."""
        choices = data.get("choices", [])
        if not choices:
            return ""
        delta = choices[0].get("delta", {})
        return delta.get("content", "")

    async def chat(self, message: str, **kwargs) -> str:
        """Send a message and return the assistant's response."""
        start = time.monotonic()

        # Build messages with history
        messages = self._get_messages_for_request()
        messages.append({"role": "user", "content": message})

        body = self._build_request_body(messages, **kwargs)

        if self.api_config.stream:
            content = await self._chat_stream(body)
            thinking = None
        else:
            content, thinking = await self._chat_sync(body)

        elapsed_ms = (time.monotonic() - start) * 1000
        now = datetime.now()
        user_msg = Message(role="user", content=message, timestamp=now)
        assistant_msg = Message(role="assistant", content=content, timestamp=now)
        self.history.add_turn(
            user_message=user_msg,
            assistant_message=assistant_msg,
            thinking=thinking,
            processing_time_ms=elapsed_ms,
        )

        logger.info(
            "Turn %d completed in %.0fms (%d chars)",
            self.history.turn_count,
            elapsed_ms,
            len(content),
        )
        return content

    async def chat_stream(self, message: str, **kwargs) -> AsyncGenerator[str, None]:
        """Send a message and yield response chunks as they arrive."""
        start = time.monotonic()

        messages = self._get_messages_for_request()
        messages.append({"role": "user", "content": message})

        body = self._build_request_body(messages, stream=True, **kwargs)
        url = f"{self.api_config.base_url}{self.ENDPOINT}"

        full_content: list[str] = []
        async with self.client.stream("POST", url, headers=self._get_headers(), json=body) as resp:
            self._check_response(resp)
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    content = self._parse_stream_chunk(chunk)
                    if content:
                        full_content.append(content)
                        yield content
                except json.JSONDecodeError:
                    continue

        elapsed_ms = (time.monotonic() - start) * 1000
        now = datetime.now()
        combined = "".join(full_content)
        user_msg = Message(role="user", content=message, timestamp=now)
        assistant_msg = Message(role="assistant", content=combined, timestamp=now)
        self.history.add_turn(
            user_message=user_msg,
            assistant_message=assistant_msg,
            processing_time_ms=elapsed_ms,
        )

    async def _chat_sync(self, body: dict) -> tuple[str, Optional[str]]:
        """Make a synchronous (non-streaming) API call."""
        url = f"{self.api_config.base_url}{self.ENDPOINT}"
        response = await self._make_request(url, body)
        return self._parse_response(response)

    async def _chat_stream(self, body: dict) -> str:
        """Make a streaming API call and return full content."""
        body["stream"] = True
        url = f"{self.api_config.base_url}{self.ENDPOINT}"
        parts: list[str] = []

        async with self.client.stream("POST", url, headers=self._get_headers(), json=body) as resp:
            self._check_response(resp)
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    content = self._parse_stream_chunk(chunk)
                    if content:
                        parts.append(content)
                except json.JSONDecodeError:
                    continue

        return "".join(parts)

    @retry(max_attempts=3, base_delay=1.0, exceptions=(APIError, httpx.HTTPStatusError))
    async def _make_request(self, url: str, body: dict) -> dict:
        """Make an API request with retry logic."""
        resp = await self.client.post(url, headers=self._get_headers(), json=body)
        self._check_response(resp)
        return resp.json()

    @staticmethod
    def _check_response(resp: httpx.Response) -> None:
        """Check response status and raise appropriate errors."""
        if resp.status_code == 429:
            retry_after = resp.headers.get("retry-after")
            msg = f"Rate limited (429). Retry-After: {retry_after}"
            raise RateLimitError(msg)
        if resp.status_code >= 400:
            raise APIError(f"API error {resp.status_code}: {resp.text}")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
