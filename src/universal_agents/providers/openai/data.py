"""OpenAI data agent — reasoning and structured data generation."""

import logging
from typing import Optional

from ...api.base_api_agent import BaseAPIAgent
from ...core.exceptions import APIError
from ...core.json_utils import extract_json as _extract_json
from ...core.prompt_builder import build_data_prompt as _build_data_prompt
from .config import OpenAIDataConfig

logger = logging.getLogger(__name__)


class OpenAIDataAgent(BaseAPIAgent):
    """OpenAI data agent with reasoning effort control and JSON output.

    Usage:
        async with OpenAIDataAgent(config) as agent:
            prompt = agent.build_data_prompt("Generate a JSON object...")
            response = await agent.chat(prompt)
            parsed = agent.parse_json_response(response)
    """

    def __init__(self, config: OpenAIDataConfig | None = None):
        super().__init__(config or OpenAIDataConfig())
        self._data_config = self.api_config  # type: OpenAIDataConfig

    def _build_request_body(self, messages: list[dict[str, str]], **kwargs) -> dict:
        """Add reasoning_effort and response_format for OpenAI models."""
        body = super()._build_request_body(messages, **kwargs)
        cfg = self._data_config

        # OpenAI newer models require max_completion_tokens instead of max_tokens
        max_ct = getattr(cfg, "max_completion_tokens", None)
        max_t = body.pop("max_tokens", None)
        body["max_completion_tokens"] = max_ct if max_ct else max_t

        # Add reasoning effort for reasoning-capable models
        if hasattr(cfg, "reasoning_effort") and cfg.reasoning_effort:
            body["reasoning_effort"] = cfg.reasoning_effort
            # Reasoning models only support temperature=1 (default)
            body.pop("temperature", None)

        # Add response format if specified
        if hasattr(cfg, "response_format") and cfg.response_format:
            body["response_format"] = cfg.response_format

        return body

    def _parse_response(self, data: dict) -> tuple[str, Optional[str]]:
        """Extract content and reasoning token info from response."""
        choices = data.get("choices", [])
        if not choices:
            raise APIError("No choices in API response")

        message = choices[0].get("message", {})
        content = message.get("content", "")

        # Extract reasoning token count as "thinking" metadata
        usage = data.get("usage", {})
        details = usage.get("completion_tokens_details", {})
        reasoning_tokens = details.get("reasoning_tokens", 0)
        thinking = f"[reasoning_tokens: {reasoning_tokens}]" if reasoning_tokens else None

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
        """Attempt to parse JSON from a response string."""
        return _extract_json(response)
