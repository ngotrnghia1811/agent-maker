"""OpenRouter data agent — extended thinking support for data generation."""

import logging
from typing import Optional

from ...api.base_api_agent import BaseAPIAgent
from ...core.json_utils import extract_json as _extract_json
from ...core.prompt_builder import build_data_prompt as _build_data_prompt
from .config import OpenRouterDataConfig

logger = logging.getLogger(__name__)


class OpenRouterDataAgent(BaseAPIAgent):
    """OpenRouter data agent with extended thinking for structured data tasks.

    Usage:
        async with OpenRouterDataAgent() as agent:
            response = await agent.chat("Generate 10 test users as JSON")
            parsed = agent.parse_json_response(response)
    """

    def __init__(self, config: OpenRouterDataConfig | None = None):
        super().__init__(config or OpenRouterDataConfig())
        self._data_config = self.api_config  # type: OpenRouterDataConfig

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._data_config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._data_config.site_url,  # type: ignore[attr-defined]
            "X-Title": self._data_config.site_name,  # type: ignore[attr-defined]
        }

    def _build_request_body(self, messages: list[dict[str, str]], **kwargs) -> dict:
        """Add thinking parameters for Claude models."""
        body = super()._build_request_body(messages, **kwargs)
        cfg = self._data_config
        if cfg.enable_thinking and "claude" in cfg.model.lower():  # type: ignore[attr-defined]
            body["thinking"] = {
                "type": "enabled",
                "budget_tokens": cfg.thinking_budget,  # type: ignore[attr-defined]
            }
        return body

    def _parse_response(self, data: dict) -> tuple[str, Optional[str]]:
        """Extract content and thinking from response."""
        choices = data.get("choices", [])
        if not choices:
            from ...core.exceptions import APIError
            raise APIError("No choices in API response")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        thinking = message.get("thinking", None)
        return content, thinking

    def build_data_prompt(
        self,
        prompt: str,
        input_json: dict | list | None = None,
        final_remind: str = "",
    ) -> str:
        """Build a data generation prompt with optional JSON input."""
        return _build_data_prompt(prompt, input_json, final_remind)

    @staticmethod
    def parse_json_response(response: str) -> dict | list | None:
        """Extract JSON from a response (searches for code blocks first)."""
        return _extract_json(response)
