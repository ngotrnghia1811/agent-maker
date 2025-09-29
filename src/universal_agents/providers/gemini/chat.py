"""Gemini chat agent — browser automation with thinking extraction."""

import asyncio
import logging
from typing import Optional

from ...browser.base_browser_agent import BaseBrowserAgent
from .config import GeminiConfig
from .selectors import GEMINI_SELECTORS

logger = logging.getLogger(__name__)

# JS: click "Show thinking" button in the last model-response, then extract text.
_JS_CLICK_AND_EXTRACT_THINKING = """
() => {
    // Find all model responses to target the most recent one
    const responses = document.querySelectorAll(
        'model-response, .model-response, [data-message-author-role="assistant"]'
    );
    if (responses.length === 0) return null;
    const lastResponse = responses[responses.length - 1];

    // Click "Show thinking" button if it's collapsed
    const btn = lastResponse.querySelector('[data-test-id="thoughts-header-button"]')
             || lastResponse.querySelector('.thoughts-header-button')
             || lastResponse.querySelector('button[aria-label*="thinking"]');
    if (btn && btn.getAttribute('aria-expanded') !== 'true') {
        btn.scrollIntoView({block: 'center'});
        btn.click();
        return '__CLICKED__';
    }
    // Already expanded or no button
    return btn ? '__ALREADY_EXPANDED__' : null;
}
"""

_JS_EXTRACT_THINKING_TEXT = """
() => {
    const responses = document.querySelectorAll(
        'model-response, .model-response, [data-message-author-role="assistant"]'
    );
    if (responses.length === 0) return null;
    const lastResponse = responses[responses.length - 1];

    // Strategy 1: model-thoughts container (clone → remove header → get text)
    const container = lastResponse.querySelector('[data-test-id="model-thoughts"]');
    if (container) {
        const clone = container.cloneNode(true);
        clone.querySelectorAll('.thoughts-header, button, [data-test-id="thoughts-header-button"]')
             .forEach(el => el.remove());
        const text = clone.textContent.trim()
            .replace(/Show thinking/gi, '').replace(/Hide thinking/gi, '').trim();
        if (text.length > 10) return text;
    }

    // Strategy 2: expanded details / aria-expanded containers
    const expanded = lastResponse.querySelectorAll('details[open], [aria-expanded="true"]');
    for (const el of expanded) {
        const clone = el.cloneNode(true);
        const hdr = clone.querySelector('summary, button');
        if (hdr) hdr.remove();
        const text = clone.textContent.trim();
        if (text.length > 50) return text;
    }
    return null;
}
"""


class GeminiChatAgent(BaseBrowserAgent):
    """Gemini browser agent with DOM-based thinking extraction.

    Gemini's thinking content is only available in the UI (not in API responses).
    Primary strategy: click "Show thinking" button → extract from DOM.

    Usage:
        async with GeminiChatAgent() as agent:
            response = await agent.chat("Hello Gemini!")
            print(response)
    """

    SELECTORS = GEMINI_SELECTORS

    def __init__(self, config: GeminiConfig | None = None):
        super().__init__(config or GeminiConfig())
        self._extract_thinking_enabled = self.browser_config.extract_thinking  # type: ignore[attr-defined]

    async def _post_navigate(self, page) -> None:
        """Wait for Angular hydration."""
        # Gemini's Angular app takes 10-15s to hydrate after domcontentloaded.
        # Wait for the contenteditable input to appear before proceeding.
        try:
            await page.wait_for_selector(
                "div[contenteditable='true']",
                state="visible",
                timeout=30_000,
            )
            logger.info("Gemini Angular UI hydrated — input element visible")
        except Exception:
            logger.warning("Gemini input not found after 30s, proceeding anyway")

    async def _extract_thinking(self, page) -> tuple[Optional[str], Optional[str]]:
        """Extract Gemini's thinking via DOM (click "Show thinking" → extract text).

        Gemini thinking is ONLY in the UI, not in API responses.
        Strategy 1: Click "Show thinking" button → extract from model-thoughts container.
        Strategy 2: Extract from already-expanded thinking (no click needed).
        """
        if not self._extract_thinking_enabled:
            return None, None

        # Strategy 1: DOM-based — click button and extract
        try:
            click_result = await page.evaluate(_JS_CLICK_AND_EXTRACT_THINKING)
            if click_result == "__CLICKED__":
                # Wait for expansion animation
                await asyncio.sleep(1.5)
            if click_result:  # __CLICKED__ or __ALREADY_EXPANDED__
                text = await page.evaluate(_JS_EXTRACT_THINKING_TEXT)
                if text:
                    logger.debug("Thinking extracted via DOM (%d chars)", len(text))
                    return text, "dom_button_click"
        except Exception as exc:
            logger.debug("DOM thinking extraction failed: %s", exc)

        # Strategy 2: Try extracting without clicking (may already be expanded)
        try:
            text = await page.evaluate(_JS_EXTRACT_THINKING_TEXT)
            if text:
                logger.debug("Thinking extracted from already-expanded DOM (%d chars)", len(text))
                return text, "dom_already_expanded"
        except Exception:
            pass

        logger.debug("No thinking content found")
        return None, None
