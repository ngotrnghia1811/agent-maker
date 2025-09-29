"""OpenAI chat agent — direct HTTP API integration."""

import logging

from ...api.base_api_agent import BaseAPIAgent
from .config import OpenAIConfig

logger = logging.getLogger(__name__)


class OpenAIChatAgent(BaseAPIAgent):
    """OpenAI API chat agent.

    Usage:
        async with OpenAIChatAgent() as agent:
            response = await agent.chat("Hello!")
            print(response)
    """

    def __init__(self, config: OpenAIConfig | None = None):
        super().__init__(config or OpenAIConfig())

    def _build_request_body(self, messages: list[dict[str, str]], **kwargs) -> dict:
        """Build request body, replacing max_tokens with max_completion_tokens."""
        body = super()._build_request_body(messages, **kwargs)
        cfg = self.api_config
        # OpenAI newer models require max_completion_tokens instead of max_tokens
        max_ct = getattr(cfg, "max_completion_tokens", None)
        max_t = body.pop("max_tokens", None)
        body["max_completion_tokens"] = max_ct if max_ct else max_t
        return body
