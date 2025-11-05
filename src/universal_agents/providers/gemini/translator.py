"""Gemini translator agent — multi-turn translation via browser automation.

Wraps GeminiDataAgent to provide:
- Multi-turn conversation with automatic splitting after N turns
- PDF/image file upload via Playwright
- Chunk-based text and file translation
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import GeminiTranslatorConfig
from .data import GeminiDataAgent
from ...core.types import Message

logger = logging.getLogger(__name__)


@dataclass
class TranslationChunk:
    """A chunk of source text or file reference to translate."""

    chunk_id: str
    chunk_index: int
    source_text: str = ""
    source_file: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TranslationResult:
    """Result of translating a single chunk."""

    chunk_id: str
    chunk_index: int
    success: bool
    source_text: str = ""
    source_file: str = ""
    translated_text: str = ""
    thinking: str = ""
    error: str | None = None
    processing_time_ms: float = 0.0
    conversation_index: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "success": self.success,
            "source_text": self.source_text[:200] if len(self.source_text) > 200 else self.source_text,
            "source_file": self.source_file,
            "translated_text": self.translated_text,
            "thinking": self.thinking,
            "error": self.error,
            "processing_time_ms": self.processing_time_ms,
            "conversation_index": self.conversation_index,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ProgressState:
    """Resume state for a translation job."""

    document_id: str
    total_chunks: int
    completed_chunks: list[int] = field(default_factory=list)
    current_conversation_index: int = 0
    current_turn_in_conversation: int = 0
    current_lines_in_conversation: int = 0

    def is_chunk_completed(self, chunk_index: int) -> bool:
        return chunk_index in self.completed_chunks

    def mark_completed(self, chunk_index: int) -> None:
        if chunk_index not in self.completed_chunks:
            self.completed_chunks.append(chunk_index)
            self.completed_chunks.sort()

    @property
    def is_complete(self) -> bool:
        return len(self.completed_chunks) >= self.total_chunks

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "total_chunks": self.total_chunks,
            "completed_chunks": self.completed_chunks,
            "current_conversation_index": self.current_conversation_index,
            "current_turn_in_conversation": self.current_turn_in_conversation,
            "current_lines_in_conversation": self.current_lines_in_conversation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgressState":
        return cls(
            document_id=data["document_id"],
            total_chunks=data["total_chunks"],
            completed_chunks=data.get("completed_chunks", []),
            current_conversation_index=data.get("current_conversation_index", 0),
            current_turn_in_conversation=data.get("current_turn_in_conversation", 0),
            current_lines_in_conversation=data.get("current_lines_in_conversation", 0),
        )

    @classmethod
    def load(cls, path: str | Path) -> "ProgressState | None":
        p = Path(path)
        if not p.exists():
            return None
        try:
            return cls.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


# Selectors for file upload on Gemini
FILE_INPUT_SELECTORS = [
    'input[type="file"]',
    'input[accept*="pdf"]',
    'input[accept*="image"]',
]

ATTACH_BUTTON_SELECTORS = [
    'button[aria-label*="Add file"]',
    'button[aria-label*="Upload"]',
    'button[aria-label*="upload"]',
    'button[aria-label*="Attach"]',
    'button[aria-label*="attach"]',
    'button[aria-label*="Add image"]',
    '[aria-label*="Add file"]',
]


class RateLimitError(Exception):
    """Raised when Gemini switches from 'pro' to 'fast' model (rate limit)."""
    pass


class GeminiTranslatorAgent:
    """Translation agent using Gemini via browser automation.

    Wraps GeminiDataAgent to provide multi-turn translation with conversation
    splitting, file upload, and progress tracking.
    """

    # Gemini mode picker selectors
    _MODE_BTN_SEL = 'button[data-test-id="bard-mode-menu-button"]'
    _MODE_MENU_SEL = '[role="menu"] [role="menuitem"]'

    def __init__(self, config: GeminiTranslatorConfig | None = None):
        self.config = config or GeminiTranslatorConfig()
        self._agent: GeminiDataAgent | None = None
        self.results: list[TranslationResult] = []
        self.conversation_index = 0
        self.turn_in_conversation = 0
        self.lines_in_conversation = 0  # Track dialog lines for 400-line limit
        self.progress: ProgressState | None = None
        self._progress_path: Path | None = None

    @property
    def session_id(self) -> str:
        if self._agent:
            return self._agent.session_id
        return ""

    async def __aenter__(self):
        self._agent = GeminiDataAgent(self.config)
        await self._agent.__aenter__()
        # Navigate to Gemini and wait for UI
        await self._agent._ensure_ready()
        return self

    async def __aexit__(self, *exc):
        if self._agent:
            storage_path = self.config.storage_state
            if storage_path:
                try:
                    await self._agent.browser_mgr.save_storage_state(storage_path)
                except Exception as e:
                    logger.warning("Could not save storage state: %s", e)
            await self._agent.__aexit__(*exc)
            self._agent = None

    def should_split_conversation(self) -> bool:
        return self.turn_in_conversation >= self.config.max_turns_per_conversation

    def should_split_for_line_limit(self, next_chunk_blocks: int = 0, max_lines: int = 400) -> bool:
        """Check if adding next_chunk_blocks would exceed the per-conversation line limit."""
        return (self.lines_in_conversation + next_chunk_blocks) > max_lines

    def init_progress(
        self, document_id: str, total_chunks: int, progress_path: str | Path,
    ) -> None:
        """Initialize or resume progress tracking."""
        self._progress_path = Path(progress_path)
        existing = ProgressState.load(self._progress_path)
        if existing and existing.document_id == document_id:
            self.progress = existing
            self.conversation_index = existing.current_conversation_index
            # Reset turn counter — we're in a fresh browser conversation on resume
            self.turn_in_conversation = 0
            self.lines_in_conversation = 0
            logger.info(
                "Resuming progress: %d/%d chunks completed",
                len(existing.completed_chunks), existing.total_chunks,
            )
        else:
            self.progress = ProgressState(
                document_id=document_id, total_chunks=total_chunks,
            )

    def _save_progress(self) -> None:
        """Persist current progress to disk."""
        if self.progress and self._progress_path:
            self.progress.current_conversation_index = self.conversation_index
            self.progress.current_turn_in_conversation = self.turn_in_conversation
            self.progress.current_lines_in_conversation = self.lines_in_conversation
            self.progress.save(self._progress_path)

    async def check_logged_in(self) -> bool:
        """Check if the user is logged in to Gemini.

        Detects the 'Sign in' button that appears for unauthenticated sessions.
        Returns True if logged in, False otherwise.
        """
        if not self._agent:
            return False
        page = await self._agent.browser_mgr.ensure_page()
        try:
            sign_in = page.locator('button.sign-in-button, a[href*="accounts.google.com"]')
            count = await sign_in.count()
            if count > 0:
                for i in range(count):
                    text = (await sign_in.nth(i).inner_text()).strip().lower()
                    if "sign in" in text:
                        logger.warning("Not logged in — 'Sign in' button detected")
                        return False
            # No sign-in button found → logged in
            logger.info("Login verified — no 'Sign in' button found")
            return True
        except Exception as e:
            logger.debug("Login check error: %s", e)
            return False

    async def detect_current_model(self) -> str | None:
        """Read the current model name from the Gemini mode picker button."""
        if not self._agent:
            return None
        try:
            page = await self._agent.browser_mgr.ensure_page()
            try:
                await page.wait_for_selector(
                    self._MODE_BTN_SEL, state="visible", timeout=10_000,
                )
            except Exception:
                return None
            btn = page.locator(self._MODE_BTN_SEL).first
            text = (await btn.inner_text()).strip().lower()
            logger.info("Current Gemini model: %s", text)
            return text
        except Exception as e:
            logger.debug("Could not detect model: %s", e)
        return None

    async def select_model(self, target: str = "pro") -> bool:
        """Select a specific Gemini model via the mode picker.

        Args:
            target: Model name to match (e.g., "pro", "fast", "thinking").

        Returns:
            True if successfully switched (or already on target model).
        """
        if not self._agent:
            return False

        page = await self._agent.browser_mgr.ensure_page()
        try:
            # Wait for the mode picker to render (may lag behind input element)
            try:
                await page.wait_for_selector(
                    self._MODE_BTN_SEL, state="visible", timeout=10_000,
                )
            except Exception:
                logger.warning("Mode picker button not found after 10s")
                return False
            btn = page.locator(self._MODE_BTN_SEL).first

            current = (await btn.inner_text()).strip().lower()
            if target.lower() in current:
                logger.info("Already on %s model", target)
                return True

            # Open the mode menu
            await btn.click()
            await page.wait_for_timeout(1500)

            menu_items = page.locator(self._MODE_MENU_SEL)
            count = await menu_items.count()
            for idx in range(count):
                item = menu_items.nth(idx)
                text = (await item.inner_text()).strip().lower()
                if target.lower() in text:
                    # Check if item is disabled (rate-limited)
                    is_disabled = await item.get_attribute("disabled")
                    aria_disabled = await item.get_attribute("aria-disabled")
                    if is_disabled is not None or aria_disabled == "true":
                        logger.warning(
                            "Model '%s' found but disabled (rate-limited)",
                            target,
                        )
                        await page.keyboard.press("Escape")
                        return False
                    await item.click()
                    await page.wait_for_timeout(2000)
                    new_model = (await btn.inner_text()).strip().lower()
                    logger.info("Switched model: %s → %s", current, new_model)
                    return target.lower() in new_model

            # Target not found — close menu
            await page.keyboard.press("Escape")
            logger.warning("Model '%s' not found in menu", target)
            return False
        except Exception as e:
            logger.warning("Model selection failed: %s", e)
            return False

    async def check_rate_limit(self) -> bool:
        """Check if Gemini auto-switched from 'pro' to 'fast' (rate limit).

        Returns:
            True if rate-limited (model switched to fast).
        """
        if not self.config.required_model:
            return False
        current = await self.detect_current_model()
        if current is None:
            return False
        required = self.config.required_model.lower()
        if required not in current and "fast" in current:
            logger.warning(
                "Rate limit detected: model switched from '%s' to '%s'",
                required, current,
            )
            return True
        return False

    async def start_new_conversation(self) -> None:
        """Navigate to gemini.google.com fresh and reset conversation state."""
        if not self._agent:
            raise RuntimeError("Agent not started. Use async with.")
        page = await self._agent.browser_mgr.ensure_page()
        await page.goto(self.config.base_url)
        # Wait for Angular hydration
        try:
            await page.wait_for_selector(
                "div[contenteditable='true']", state="visible", timeout=30_000,
            )
        except Exception:
            pass
        self._agent.history.clear()
        self.conversation_index += 1
        self.turn_in_conversation = 0
        self.lines_in_conversation = 0
        logger.info("Started new conversation (index: %d)", self.conversation_index)

    async def _type_model_prefix(self, page) -> None:
        """Type '@ModelName ' into the input field to trigger model selection.

        Gemini requires '@Pro' to be typed character-by-character into the
        contenteditable input to trigger the model autocomplete popup,
        then Space to confirm the selection.
        """
        if not self.config.required_model:
            return
        from ...browser.dom import find_element
        # Dismiss any overlays before clicking the input
        await self._agent._dismiss_overlays(page)
        input_el = await find_element(page, self._agent.SELECTORS.input)
        await input_el.click()
        await page.wait_for_timeout(300)
        # Type @ModelName character by character to trigger autocomplete
        # Capitalize first letter: "pro" → "Pro"
        model_name = self.config.required_model.capitalize()
        prefix = f"@{model_name}"
        await input_el.press_sequentially(prefix, delay=80)
        await page.wait_for_timeout(1500)  # Wait for autocomplete popup to appear
        # Press Space to confirm model selection from autocomplete
        await page.keyboard.press(" ")
        await page.wait_for_timeout(1000)  # Wait for chip to be created
        logger.info("Typed model prefix: %s", prefix)

    async def upload_file(self, file_path: str, prompt_text: str = "") -> bool:
        """Upload a file via Gemini's file upload mechanism."""
        if not self._agent:
            raise RuntimeError("Agent not started. Use async with.")

        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        page = await self._agent._ensure_ready()
        abs_path = str(p)
        attached = False

        # Wait for UI to fully stabilize (upload button may lag behind input)
        try:
            await page.wait_for_selector(
                'button[aria-label="Open upload file menu"]',
                state="visible", timeout=10_000,
            )
        except Exception:
            # Button may not exist; proceed with fallbacks
            await page.wait_for_timeout(2000)

        # Strategy 1: Click "Open upload file menu" button → triggers hidden file upload button
        # Gemini uses a hidden button with data-test-id="hidden-local-file-upload-button"
        # that acts as a file chooser trigger
        try:
            upload_menu_btn = page.locator('button[aria-label="Open upload file menu"]').first
            btn_count = await upload_menu_btn.count()
            logger.info("Upload menu button count: %d", btn_count)
            if btn_count > 0:
                await upload_menu_btn.click()
                await page.wait_for_timeout(1500)

                # After clicking, look for menu item "Upload file" and intercept chooser
                file_menu_item = page.locator('[role="menu"] [role="menuitem"]')
                menu_count = await file_menu_item.count()
                logger.info("Upload menu items: %d", menu_count)
                for idx in range(menu_count):
                    item = file_menu_item.nth(idx)
                    text = (await item.inner_text()).strip().lower()
                    logger.info("  Menu item [%d]: %s", idx, text)
                    if "file" in text or "upload" in text:
                        try:
                            async with page.expect_file_chooser(timeout=5000) as fc_info:
                                await item.click()
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(abs_path)
                            logger.info("File attached via upload menu item: %s", text)
                            attached = True
                        except Exception as e:
                            logger.warning("Upload menu item click failed: %s", e)
                        break

                if not attached:
                    # Try clicking the hidden file upload trigger directly
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)
        except Exception as e:
            logger.warning("Strategy 1 failed entirely: %s", e)

        # Strategy 2: Use the hidden file upload buttons directly via file chooser
        if not attached:
            hidden_selectors = [
                'button[data-test-id="hidden-local-file-upload-button"]',
                'button[data-test-id="hidden-local-image-upload-button"]',
            ]
            for sel in hidden_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.count() > 0:
                        async with page.expect_file_chooser(timeout=5000) as fc_info:
                            await btn.dispatch_event("click")
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(abs_path)
                        logger.info("File attached via hidden trigger: %s", sel)
                        attached = True
                        break
                except Exception:
                    continue

        # Strategy 3: Try existing file inputs directly (even hidden ones)
        if not attached:
            for selector in FILE_INPUT_SELECTORS:
                try:
                    locator = page.locator(selector).first
                    if await locator.count() > 0:
                        await locator.set_input_files(abs_path)
                        logger.info("File attached via direct input: %s", selector)
                        attached = True
                        break
                except Exception:
                    continue

        # Strategy 4: JS fallback — expose hidden file input
        if not attached:
            try:
                await page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input[type="file"]');
                    inputs.forEach(input => {
                        input.style.display = 'block';
                        input.style.visibility = 'visible';
                        input.style.opacity = '1';
                        input.style.position = 'fixed';
                        input.style.top = '0';
                        input.style.left = '0';
                        input.style.zIndex = '99999';
                    });
                }""")
                await page.wait_for_timeout(500)
                locator = page.locator('input[type="file"]').first
                if await locator.count() > 0:
                    await locator.set_input_files(abs_path)
                    logger.info("File attached via JS-exposed input")
                    attached = True
            except Exception:
                pass

        if not attached:
            logger.warning("Could not upload file: %s", file_path)
            return False

        # Wait for upload processing
        await page.wait_for_timeout(3000)

        # Enter accompanying text if provided
        if prompt_text:
            try:
                from ...browser.dom import find_element, type_text
                input_el = await find_element(page, self._agent.SELECTORS.input)
                word_count = len(prompt_text.split())
                if word_count > 100:
                    pasted = await self._agent._paste_to_input(page, prompt_text)
                    if not pasted:
                        logger.warning(
                            "Paste failed, trying JS insert for %d-word prompt",
                            word_count,
                        )
                        inserted = await self._agent._js_insert_text(page, prompt_text)
                        if not inserted:
                            logger.warning(
                                "JS insert also failed, falling back to type_text"
                            )
                            await type_text(input_el, prompt_text)
                else:
                    await type_text(input_el, prompt_text)
            except Exception as e:
                logger.warning("File attached but failed to enter text: %s", e)

            # CRITICAL: Verify the prompt text is actually in the input
            if len(prompt_text) > 50:
                has_content = await self._agent._verify_input_has_content(page, min_chars=50)
                if not has_content:
                    logger.error(
                        "CRITICAL: Prompt text (%d words) NOT in input after all strategies!",
                        len(prompt_text.split()),
                    )
                    return False

        return True

    async def translate_text(
        self,
        chunk: TranslationChunk,
        system_prompt: str | None = None,
        continue_prompt: str | None = None,
        is_first_turn: bool = False,
        num_blocks: int = 0,
    ) -> TranslationResult:
        """Translate a text chunk via Gemini browser chat.

        Args:
            num_blocks: Number of SRT dialog blocks in this chunk (for line tracking).

        Raises:
            RateLimitError: If Gemini switched to 'fast' model (rate limit hit).
        """
        if not self._agent:
            raise RuntimeError("Agent not started. Use async with.")

        # Skip already-completed chunks when resuming
        if self.progress and self.progress.is_chunk_completed(chunk.chunk_index):
            logger.info("Skipping already-completed chunk %d", chunk.chunk_index)
            return TranslationResult(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                success=True,
                source_text=chunk.source_text,
                translated_text="[previously completed]",
            )

        start = time.monotonic()

        # Build prompt
        if is_first_turn and system_prompt:
            prompt = f"{system_prompt}\n\n---\n\n{chunk.source_text}"
        elif continue_prompt:
            prompt = f"{continue_prompt}\n\n{chunk.source_text}"
        else:
            prompt = chunk.source_text

        try:
            # Type @model prefix on first turn of each conversation
            if self.turn_in_conversation == 0:
                page = await self._agent.browser_mgr.ensure_page()
                await self._type_model_prefix(page)

            response = await self._agent.chat(prompt)
            elapsed_ms = (time.monotonic() - start) * 1000
            self.turn_in_conversation += 1
            self.lines_in_conversation += num_blocks

            # Check for rate limit after each response
            if self.config.required_model and await self.check_rate_limit():
                # Save progress before raising
                self._save_progress()
                raise RateLimitError(
                    f"Rate limit: Gemini switched away from '{self.config.required_model}' model. "
                    f"Progress saved at chunk {chunk.chunk_index}."
                )

            last_turn = self._agent.history.turns[-1] if self._agent.history.turns else None
            thinking = last_turn.thinking if last_turn else ""

            result = TranslationResult(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                success=True,
                source_text=chunk.source_text,
                translated_text=response,
                thinking=thinking or "",
                processing_time_ms=elapsed_ms,
                conversation_index=self.conversation_index,
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            result = TranslationResult(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                success=False,
                source_text=chunk.source_text,
                error=str(e),
                processing_time_ms=elapsed_ms,
                conversation_index=self.conversation_index,
            )

        self.results.append(result)

        # Track progress
        if result.success and self.progress:
            self.progress.mark_completed(chunk.chunk_index)
            self._save_progress()

        return result

    async def translate_file(
        self,
        chunk: TranslationChunk,
        system_prompt: str | None = None,
        continue_prompt: str | None = None,
        is_first_turn: bool = False,
    ) -> TranslationResult:
        """Translate a file (PDF/image) via Gemini with file upload."""
        if not self._agent:
            raise RuntimeError("Agent not started. Use async with.")

        start = time.monotonic()

        if not chunk.source_file or not Path(chunk.source_file).exists():
            return TranslationResult(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                success=False,
                source_file=chunk.source_file,
                error=f"File not found: {chunk.source_file}",
                conversation_index=self.conversation_index,
            )

        # Build the accompanying prompt
        if is_first_turn and system_prompt:
            prompt = system_prompt
        elif continue_prompt:
            prompt = continue_prompt
        else:
            prompt = ""

        try:
            # Type @model prefix on first turn of each conversation
            if self.turn_in_conversation == 0 and prompt:
                page = await self._agent.browser_mgr.ensure_page()
                await self._type_model_prefix(page)

            uploaded = await self.upload_file(chunk.source_file, prompt)
            if not uploaded:
                raise RuntimeError("Failed to upload file or enter prompt text")

            # CRITICAL PRE-SUBMIT CHECK: for first-turn system prompts,
            # verify the instruction text is actually in the input before
            # clicking submit. Without this, Gemini just describes the image.
            if is_first_turn and system_prompt:
                page = await self._agent.browser_mgr.ensure_page()
                has_content = await self._agent._verify_input_has_content(
                    page, min_chars=50
                )
                if not has_content:
                    raise RuntimeError(
                        "System prompt was NOT entered into input. "
                        "Cannot submit without task instructions."
                    )
                logger.info(
                    "Pre-submit check PASSED: input has task prompt content"
                )

            # Use the data agent's detector and flow for submit + wait
            page = await self._agent.browser_mgr.ensure_page()
            count_before, selector_hint = await self._agent.detector.count_responses(
                page, self._agent.SELECTORS.response
            )

            from ...browser.dom import click_submit
            logger.info("Submitting prompt (responses before: %d)...", count_before)
            await click_submit(page, self._agent.SELECTORS.submit)

            response = await self._agent.detector.wait_for_new_response(
                page, self._agent.SELECTORS.response, count_before,
                selector_hint=selector_hint,
            )

            thinking, thinking_source = await self._agent._extract_thinking(page)

            # Record in history
            raw_api_responses = self._agent.browser_mgr.get_captured_responses()
            self._agent.browser_mgr.clear_captured_responses()
            user_msg = Message(
                role="user",
                content=f"[File: {Path(chunk.source_file).name}] {prompt}",
            )
            assistant_msg = Message(role="assistant", content=response)
            self._agent.history.add_turn(
                user_message=user_msg,
                assistant_message=assistant_msg,
                thinking=thinking,
                processing_time_ms=(time.monotonic() - start) * 1000,
                raw_api_responses=raw_api_responses,
                thinking_source=thinking_source,
            )

            elapsed_ms = (time.monotonic() - start) * 1000
            self.turn_in_conversation += 1

            result = TranslationResult(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                success=True,
                source_file=chunk.source_file,
                translated_text=response,
                thinking=thinking or "",
                processing_time_ms=elapsed_ms,
                conversation_index=self.conversation_index,
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            result = TranslationResult(
                chunk_id=chunk.chunk_id,
                chunk_index=chunk.chunk_index,
                success=False,
                source_file=chunk.source_file,
                error=str(e),
                processing_time_ms=elapsed_ms,
                conversation_index=self.conversation_index,
            )

        self.results.append(result)
        return result

    def get_full_translation(self) -> str:
        """Concatenate all successful translations."""
        return "\n\n".join(r.translated_text for r in self.results if r.success)

    def export_results(self, output_path: str | Path) -> Path:
        """Export all translation results as JSON."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "config": {
                "source_language": self.config.source_language,
                "target_language": self.config.target_language,
                "translation_mode": self.config.translation_mode,
                "max_turns_per_conversation": self.config.max_turns_per_conversation,
            },
            "results": [r.to_dict() for r in self.results],
            "total_chunks": len(self.results),
            "successful_chunks": sum(1 for r in self.results if r.success),
            "conversations_used": self.conversation_index + 1,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
