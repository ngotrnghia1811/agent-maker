"""Claude data agent — browser automation for structured data generation."""

import logging
import subprocess
import sys
from typing import Optional

from ...browser.base_browser_agent import BaseBrowserAgent
from ...browser.dom import find_element, type_text
from ...core.json_utils import extract_json as _extract_json
from ...core.prompt_builder import build_data_prompt as _build_data_prompt
from .config import ClaudeDataConfig
from .selectors import CLAUDE_SELECTORS

logger = logging.getLogger(__name__)

class ClaudeDataAgent(BaseBrowserAgent):
    """Claude browser agent specialized for structured data generation.

    Builds prompts with JSON input blocks and extracts JSON from responses.

    Usage:
        async with ClaudeDataAgent() as agent:
            prompt = agent.build_data_prompt(
                "Generate user profiles",
                input_json={"count": 5},
            )
            response = await agent.chat(prompt)
            data = agent.extract_json(response)
    """

    SELECTORS = CLAUDE_SELECTORS

    # Claude auto-converts long pasted text into a file attachment.
    # Only use paste for very long messages (e.g. those with the kendo dictionary).
    LONG_MESSAGE_WORD_THRESHOLD = 1000

    def __init__(self, config: ClaudeDataConfig | None = None):
        super().__init__(config or ClaudeDataConfig())
        self._extract_thinking_enabled = self.browser_config.extract_thinking  # type: ignore[attr-defined]
        self._js_injected = False

    async def _post_navigate(self, page) -> None:
        """Inject fetch override JS after navigating to Claude."""
        if self._extract_thinking_enabled and not self._js_injected:
            await self.browser_mgr.inject_js("fetch_override.js")
            self._js_injected = True

    async def _pre_chat_hook(self, page) -> None:
        await super()._pre_chat_hook(page)
        if self._extract_thinking_enabled:
            try:
                await page.evaluate("window.clearCapturedThinking && window.clearCapturedThinking()")
            except Exception:
                pass

    async def _extract_thinking(self, page) -> tuple[Optional[str], Optional[str]]:
        """Extract thinking via fetch override (same strategies as chat agent)."""
        if not self._extract_thinking_enabled:
            return None, None
        # Check captured API responses
        for resp in reversed(self.browser_mgr.get_captured_responses()):
            data = resp.get("data", {})
            for msg in reversed(data.get("chat_messages", [])):
                content = msg.get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "thinking" and block.get("thinking"):
                        return block["thinking"], "playwright_intercept"
        # Check JS fetch override
        try:
            result = await page.evaluate("window.getThinkingFromCapturedData && window.getThinkingFromCapturedData()")
            if result and result.get("thinking"):
                return result["thinking"], "fetch_override_js"
        except Exception:
            pass
        return None, None

    @staticmethod
    def build_data_prompt(
        prompt: str,
        input_json: dict | list | None = None,
        final_remind: str = "",
    ) -> str:
        """Build a data generation prompt with optional JSON input block."""
        return _build_data_prompt(prompt, input_json, final_remind)

    @staticmethod
    def extract_json(response: str) -> dict | list | None:
        """Extract JSON from a response (searches code blocks first, then raw JSON)."""
        return _extract_json(response)

    async def _send_message(self, page, message: str) -> None:
        """Paste long messages into Claude (auto-converts to file); type short ones."""
        word_count = len(message.split())
        if word_count > self.LONG_MESSAGE_WORD_THRESHOLD:
            pasted = await self._paste_long_message(page, message)
            if pasted:
                return
            logger.warning(
                "Paste failed for %d-word message, falling back to type_text",
                word_count,
            )
        input_el = await find_element(page, self.SELECTORS.input)
        await type_text(input_el, message)

    async def _paste_long_message(self, page, message: str) -> bool:
        """Paste *message* into Claude's ProseMirror input via clipboard.

        Claude automatically converts long pasted text into a file attachment.
        This is more reliable than navigator.clipboard API which requires
        browser clipboard permissions not available in automation contexts.

        Returns True if the paste succeeded and Claude processed it.
        """
        try:
            # Write to the OS clipboard directly — avoids browser permission issues
            if sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=message.encode("utf-8"), check=True)
            elif sys.platform.startswith("linux"):
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=message.encode("utf-8"),
                    check=True,
                )
            else:
                raise RuntimeError(f"Unsupported platform for clipboard: {sys.platform}")

            # Focus the ProseMirror input then paste
            input_el = await find_element(page, self.SELECTORS.input)
            await input_el.click()
            await page.wait_for_timeout(500)

            modifier = "Meta" if sys.platform == "darwin" else "Control"
            await page.keyboard.press(f"{modifier}+v")

            # Wait for Claude to process the paste (may show loading indicator)
            await page.wait_for_timeout(2000)
            for _ in range(30):  # up to 30 seconds
                loading = page.locator('text="Loading..."')
                if await loading.count() == 0:
                    break
                await page.wait_for_timeout(1000)

            logger.info("Long message pasted via system clipboard (%d words)", len(message.split()))
            return True
        except Exception as e:
            logger.debug("System clipboard paste failed: %s", e)
            return False
