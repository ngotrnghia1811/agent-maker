"""Gemini data agent — browser automation for structured data generation."""

import asyncio
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from ...browser.base_browser_agent import BaseBrowserAgent
from ...browser.dom import find_element, type_text
from ...core.json_utils import extract_json as _extract_json
from ...core.prompt_builder import build_data_prompt as _build_data_prompt
from .chat import _JS_CLICK_AND_EXTRACT_THINKING, _JS_EXTRACT_THINKING_TEXT
from .config import GeminiDataConfig
from .selectors import GEMINI_SELECTORS

logger = logging.getLogger(__name__)


class GeminiDataAgent(BaseBrowserAgent):
    """Gemini browser agent specialized for structured data generation.

    Builds prompts with JSON input blocks and extracts JSON from responses.

    Usage:
        async with GeminiDataAgent() as agent:
            prompt = agent.build_data_prompt(
                "Generate user profiles",
                input_json={"count": 5},
            )
            response = await agent.chat(prompt)
            data = agent.extract_json(response)
    """

    SELECTORS = GEMINI_SELECTORS

    def __init__(self, config: GeminiDataConfig | None = None):
        super().__init__(config or GeminiDataConfig())
        self._extract_thinking_enabled = self.browser_config.extract_thinking  # type: ignore[attr-defined]

    async def _post_navigate(self, page) -> None:
        """Wait for Angular hydration and dismiss any promotional overlays."""
        try:
            await page.wait_for_selector(
                "div[contenteditable='true']",
                state="visible",
                timeout=30_000,
            )
            logger.info("Gemini Angular UI hydrated — input element visible")
        except Exception:
            logger.warning("Gemini input not found after 30s, proceeding anyway")

        # Dismiss Angular CDK overlays (e.g. Deep Research promo) that block input
        await self._dismiss_overlays(page)

    async def _dismiss_overlays(self, page) -> None:
        """Close any Angular CDK overlay that intercepts clicks on the input."""
        try:
            overlay = page.locator(".cdk-overlay-container .cdk-overlay-backdrop")
            if await overlay.count() > 0:
                logger.info("Overlay backdrop detected — dismissing with Escape")
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
                # Verify overlay is gone
                if await overlay.count() > 0:
                    # Try clicking the backdrop to dismiss
                    try:
                        await overlay.first.click(force=True)
                        await page.wait_for_timeout(500)
                    except Exception:
                        pass
            # Also remove any remaining overlay pane that blocks pointer events
            await page.evaluate("""() => {
                const container = document.querySelector('.cdk-overlay-container');
                if (container && container.children.length > 0) {
                    container.innerHTML = '';
                }
            }""")
        except Exception as e:
            logger.debug("Overlay dismissal: %s", e)

    async def _extract_thinking(self, page) -> tuple[Optional[str], Optional[str]]:
        """Extract thinking via DOM (same strategy as GeminiChatAgent)."""
        if not self._extract_thinking_enabled:
            return None, None

        # Strategy 1: Click button and extract
        try:
            click_result = await page.evaluate(_JS_CLICK_AND_EXTRACT_THINKING)
            if click_result == "__CLICKED__":
                await asyncio.sleep(1.5)
            if click_result:
                text = await page.evaluate(_JS_EXTRACT_THINKING_TEXT)
                if text:
                    logger.debug("Thinking extracted via DOM (%d chars)", len(text))
                    return text, "dom_button_click"
        except Exception as exc:
            logger.debug("DOM thinking extraction failed: %s", exc)

        # Strategy 2: Already expanded
        try:
            text = await page.evaluate(_JS_EXTRACT_THINKING_TEXT)
            if text:
                return text, "dom_already_expanded"
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
        """Insert long messages via JS or clipboard; type short ones normally.

        For long messages the preferred order is:
        1. JS ``execCommand('insertText')`` — most reliable, no clipboard
           involvement, works in both visible and headless Camoufox.
        2. Clipboard paste (``pbcopy`` + ``Meta+v``) — fallback; prone to
           browser-internal-clipboard contamination in headless mode when
           Gemini's "Copy" button has previously written to it.
        3. ``type_text()`` — slow character-by-character fallback.
        """
        word_count = len(message.split())
        if word_count > self.LONG_MESSAGE_WORD_THRESHOLD:
            # Primary: JS insertText (no clipboard, works headless + visible)
            inserted = await self._js_insert_text(page, message)
            if inserted:
                return
            # Fallback: clipboard paste
            pasted = await self._paste_to_input(page, message)
            if pasted:
                return
            logger.warning(
                "JS insert + paste failed for %d-word message, falling back to type_text",
                word_count,
            )
        input_el = await find_element(page, self.SELECTORS.input)
        await type_text(input_el, message)

    async def _verify_input_has_content(self, page, min_chars: int = 50) -> bool:
        """Check if the Gemini input field contains at least *min_chars* of text."""
        try:
            input_el = await find_element(page, self.SELECTORS.input)
            content = await input_el.text_content() or ""
            return len(content.strip()) >= min_chars
        except Exception:
            return False

    async def _clear_input(self, page) -> None:
        """Clear any residual text from the Gemini input field.

        Uses Ctrl/Cmd+A then Delete to select all and remove.  This prevents
        stale content (e.g. from Gemini's Copy button writing to the browser
        clipboard, which ``Meta+v`` would re-paste) from polluting the next
        message.
        """
        try:
            input_el = await find_element(page, self.SELECTORS.input)
            await input_el.click()
            await page.wait_for_timeout(200)
            modifier = "Meta" if sys.platform == "darwin" else "Control"
            await page.keyboard.press(f"{modifier}+a")
            await page.wait_for_timeout(100)
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(200)
        except Exception as e:
            logger.debug("Could not clear input: %s", e)

    async def _verify_input_matches(self, page, expected: str) -> bool:
        """Check that the input field contains text matching *expected*.

        Compares the first 200 characters of the input against the first 200
        characters of the expected text to catch clipboard contamination
        (e.g. previous Gemini response pasted instead of the intended prompt).
        """
        try:
            input_el = await find_element(page, self.SELECTORS.input)
            content = (await input_el.text_content() or "").strip()
            if len(content) < 50:
                return False
            # Compare first 200 chars (normalized whitespace)
            prefix_len = 200
            actual_prefix = " ".join(content[:prefix_len].split())
            expected_prefix = " ".join(expected[:prefix_len].split())
            if actual_prefix == expected_prefix:
                return True
            # Fuzzy: check that expected prefix is contained within actual
            # (accounts for @Model prefix chip prepended by Gemini)
            if expected_prefix in " ".join(content[:prefix_len + 100].split()):
                return True
            logger.debug(
                "Input mismatch: expected %.80r… got %.80r…",
                expected_prefix, actual_prefix,
            )
            return False
        except Exception:
            return False

    async def _paste_to_input(self, page, message: str) -> bool:
        """Paste *message* into Gemini's input via system clipboard.

        Uses pbcopy (macOS) or xclip (Linux) to write to the OS clipboard,
        then Cmd/Ctrl+V to paste.  After pasting, **verifies** that the
        input contains the expected text — not just any text (to guard against
        the browser's internal clipboard containing stale response data from
        Gemini's Copy button).

        Returns True only if the *correct* text was verified in the input.
        """
        try:
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

            # Clear input before pasting to avoid residual content
            await self._clear_input(page)

            input_el = await find_element(page, self.SELECTORS.input)
            await input_el.click()
            await page.wait_for_timeout(300)

            modifier = "Meta" if sys.platform == "darwin" else "Control"
            await page.keyboard.press(f"{modifier}+v")
            await page.wait_for_timeout(1000)

            # Verify the pasted text matches what we intended (not stale clipboard)
            if not await self._verify_input_matches(page, message):
                logger.warning(
                    "Clipboard paste: input content does not match expected message"
                )
                # Clear the wrong content so JS insert starts fresh
                await self._clear_input(page)
                return False

            logger.info("Long message pasted via clipboard (%d words)", len(message.split()))
            return True
        except Exception as e:
            logger.debug("Clipboard paste failed: %s", e)
            return False

    async def _js_insert_text(self, page, message: str) -> bool:
        """Insert *message* into the Gemini input via JS execCommand.

        Fallback for when clipboard paste fails (e.g. headless mode).
        Uses document.execCommand('insertText') which triggers Angular input events.

        Returns True only if text was verified present in the input.
        """
        try:
            await page.evaluate("""(text) => {
                const el = document.querySelector("div[contenteditable='true']");
                if (!el) throw new Error("Contenteditable input not found");
                el.focus();
                // Move cursor to end
                const sel = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(el);
                range.collapse(false);
                sel.removeAllRanges();
                sel.addRange(range);
                // Insert text (triggers input events for Angular)
                document.execCommand('insertText', false, text);
            }""", message)
            await page.wait_for_timeout(1000)

            if not await self._verify_input_has_content(page, min_chars=50):
                logger.warning("JS insertText executed but input is still empty")
                return False

            logger.info(
                "Long message inserted via JS execCommand (%d words)",
                len(message.split()),
            )
            return True
        except Exception as e:
            logger.debug("JS insertText failed: %s", e)
            return False

    async def _upload_file_to_gemini(self, page, message: str) -> bool:
        """Write *message* to a temp .txt file and upload it to Gemini.

        Returns True if the file was successfully attached.
        """
        # Write message to a temp file
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix="prompt_", delete=False
        )
        try:
            tmp.write(message)
            tmp.flush()
            tmp_path = tmp.name
        finally:
            tmp.close()

        attached = False

        # Wait for upload UI to render (may lag behind the input element)
        try:
            await page.wait_for_selector(
                'button[aria-label="Open upload file menu"]',
                state="visible",
                timeout=10_000,
            )
        except Exception:
            logger.debug("Upload menu button not found after 10s, trying fallbacks")

        # Strategy 1: Click "Open upload file menu" → click the "Upload file" item
        if not attached:
            try:
                menu_btn = page.locator(
                    'button[aria-label="Open upload file menu"]'
                ).first
                if await menu_btn.count() > 0 and await menu_btn.is_visible(timeout=2000):
                    await menu_btn.click()
                    await page.wait_for_timeout(1500)
                    items = page.locator('[role="menu"] [role="menuitem"]')
                    count = await items.count()
                    logger.debug("Upload menu has %d items", count)
                    for idx in range(count):
                        item = items.nth(idx)
                        text = (await item.inner_text()).strip().lower()
                        logger.debug("  Menu item [%d]: %s", idx, text)
                        if "file" in text or "upload" in text:
                            async with page.expect_file_chooser(timeout=5000) as fc_info:
                                await item.click()
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(tmp_path)
                            logger.info("File attached via upload menu item: %s", text)
                            attached = True
                            break
                    if not attached:
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(300)
            except Exception as e:
                logger.warning("Strategy 1 (upload menu) failed: %s", e)
                # Dismiss any open menu
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass

        # Strategy 2: Click the hidden file upload button directly (force click)
        if not attached:
            hidden_sel = 'button[data-test-id="hidden-local-file-upload-button"]'
            try:
                btn = page.locator(hidden_sel).first
                if await btn.count() > 0:
                    async with page.expect_file_chooser(timeout=5000) as fc_info:
                        await btn.click(force=True)
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(tmp_path)
                    logger.info("File attached via hidden button (force click)")
                    attached = True
            except Exception as e:
                logger.warning("Strategy 2 (hidden button) failed: %s", e)

        # Strategy 3: JS — programmatically trigger file selection on hidden button
        if not attached:
            try:
                js_result = await page.evaluate("""(filePath) => {
                    const btn = document.querySelector(
                        'button[data-test-id="hidden-local-file-upload-button"]'
                    );
                    if (btn) { btn.click(); return true; }
                    return false;
                }""", tmp_path)
                if js_result:
                    # The JS click should have triggered the file chooser
                    # We can't intercept it from JS, so this is a fallback
                    logger.warning("Strategy 3: JS click issued but cannot intercept file chooser")
            except Exception as e:
                logger.warning("Strategy 3 (JS click) failed: %s", e)

        # Clean up temp file (delay to allow upload to read it)
        async def _cleanup():
            await asyncio.sleep(5)
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

        if not attached:
            # Clean up immediately if not attached
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass
            return False

        # Wait for upload processing indicator
        await page.wait_for_timeout(3000)

        # Schedule cleanup after upload is processed
        asyncio.create_task(_cleanup())

        # Type a short instruction so Gemini processes the file
        try:
            input_el = await find_element(page, self.SELECTORS.input)
            await type_text(
                input_el,
                "Process the attached file and follow its instructions.",
            )
        except Exception as e:
            logger.warning("File attached but failed to type prompt: %s", e)

        return True
