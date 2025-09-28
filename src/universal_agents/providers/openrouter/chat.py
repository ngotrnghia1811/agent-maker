"""OpenRouter chat agent — HTTP API with model fallback."""

import logging
from typing import Optional

import httpx

from ...api.base_api_agent import BaseAPIAgent
from ...core.exceptions import APIError
from .config import OpenRouterConfig

logger = logging.getLogger(__name__)


class OpenRouterChatAgent(BaseAPIAgent):
    """OpenRouter API agent with model fallback and rate-limit retry.

    Usage:
        async with OpenRouterChatAgent() as agent:
            response = await agent.chat("Hello!")
            print(response)
    """

    def __init__(self, config: OpenRouterConfig | None = None):
        super().__init__(config or OpenRouterConfig())
        self._or_config = self.api_config  # type: OpenRouterConfig

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._or_config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._or_config.site_url,  # type: ignore[attr-defined]
            "X-Title": self._or_config.site_name,  # type: ignore[attr-defined]
        }

    async def chat(self, message: str, **kwargs) -> str:
        """Send message with model fallback on failure."""
        try:
            return await super().chat(message, **kwargs)
        except (APIError, httpx.HTTPStatusError) as e:
            logger.warning("Primary model failed: %s. Trying fallbacks.", e)
            return await self._chat_with_fallback(message, **kwargs)

    async def _chat_with_fallback(self, message: str, **kwargs) -> str:
        """Try fallback models in order."""
        original_model = self.api_config.model
        for model in self._or_config.fallback_models:  # type: ignore[attr-defined]
            logger.info("Trying fallback model: %s", model)
            self.api_config.model = model
            try:
                return await super().chat(message, **kwargs)
            except (APIError, httpx.HTTPStatusError) as e:
                logger.warning("Fallback model %s failed: %s", model, e)
                continue
            finally:
                self.api_config.model = original_model
        raise APIError("All models failed (primary + fallbacks)")
