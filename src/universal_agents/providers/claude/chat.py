"""Claude chat agent — browser automation with thinking extraction."""

import logging
from typing import Optional

from ...browser.base_browser_agent import BaseBrowserAgent
from .config import ClaudeConfig
from .selectors import CLAUDE_SELECTORS

logger = logging.getLogger(__name__)


class ClaudeChatAgent(BaseBrowserAgent):
    """Claude browser agent with fetch interception and thinking extraction.

    Usage:
        async with ClaudeChatAgent() as agent:
            response = await agent.chat("Hello Claude!")
            print(response)
    """

    SELECTORS = CLAUDE_SELECTORS

    def __init__(self, config: ClaudeConfig | None = None):
        super().__init__(config or ClaudeConfig())
        self._extract_thinking_enabled = self.browser_config.extract_thinking  # type: ignore[attr-defined]
        self._js_injected = False

    async def _post_navigate(self, page) -> None:
        """Inject fetch override JS after navigating to Claude."""
        if self._extract_thinking_enabled and not self._js_injected:
            await self.browser_mgr.inject_js("fetch_override.js")
            self._js_injected = True
            logger.info("Fetch override JS injected for thinking extraction")

    async def _pre_chat_hook(self, page) -> None:
        """Clear captured thinking data before each turn."""
        await super()._pre_chat_hook(page)
        if self._extract_thinking_enabled:
            try:
                await page.evaluate("window.clearCapturedThinking && window.clearCapturedThinking()")
            except Exception:
                pass

    async def _extract_thinking(self, page) -> tuple[Optional[str], Optional[str]]:
        """Extract Claude's extended thinking via multiple strategies.

        Strategy 1: Native Playwright response interception (captured by BrowserManager).
        Strategy 2: Fetch override JS (injected into page).
        Strategy 3: React fiber/global state search via thinking_extractor.js.

        Returns:
            Tuple of (thinking_text, source_name). Both None if nothing found.
        """
        if not self._extract_thinking_enabled:
            return None, None

        # Strategy 1: Check captured API responses from Playwright interception
        thinking = self._extract_from_captured_responses()
        if thinking:
            logger.debug("Thinking extracted via Playwright response interception")
            return thinking, "playwright_intercept"

        # Strategy 2: Check JS fetch override captured data
        try:
            result = await page.evaluate("window.getThinkingFromCapturedData && window.getThinkingFromCapturedData()")
            if result and result.get("thinking"):
                logger.debug("Thinking extracted via fetch override JS")
                return result["thinking"], "fetch_override_js"
        except Exception:
            pass

        # Strategy 3: React state search via thinking_extractor.js
        try:
            await self.browser_mgr.inject_js("thinking_extractor.js")
            result = await page.evaluate("window.claudeThinkingExtractor && window.claudeThinkingExtractor.extractAll()")
            if result and result.get("thinking"):
                source = f"react_state_{result.get('found_via', 'unknown')}"
                logger.debug("Thinking extracted via React state search (%s)", result.get("found_via"))
                return result["thinking"], source
        except Exception:
            pass

        logger.debug("No thinking content found")
        return None, None

    def _extract_from_captured_responses(self) -> Optional[str]:
        """Parse thinking blocks from captured Playwright API responses."""
        for resp in reversed(self.browser_mgr.get_captured_responses()):
            data = resp.get("data", {})
            chat_messages = data.get("chat_messages", [])

            for msg in reversed(chat_messages):
                content = msg.get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "thinking"
                        and block.get("thinking")
                    ):
                        return block["thinking"]
        return None
