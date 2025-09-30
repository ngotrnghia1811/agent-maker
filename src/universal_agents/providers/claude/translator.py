"""Claude translator agent — multi-turn translation via browser automation.

Wraps ClaudeDataAgent to provide:
- Multi-turn conversation with automatic splitting after N turns
- PDF/image file upload via Playwright
- Progress state for resumable translation jobs
- Chunk-based text and file translation
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .config import ClaudeTranslatorConfig
from .data import ClaudeDataAgent
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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProgressState":
        return cls(
            document_id=data["document_id"],
            total_chunks=data["total_chunks"],
            completed_chunks=data.get("completed_chunks", []),
            current_conversation_index=data.get("current_conversation_index", 0),
            current_turn_in_conversation=data.get("current_turn_in_conversation", 0),
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


# Selectors for file upload
FILE_INPUT_SELECTORS = [
    'input[data-testid="file-upload"]',
    '#chat-input-file-upload-onpage',
    'input[type="file"]',
    'input[accept*="pdf"]',
    'input[accept*="image"]',
]

ATTACH_BUTTON_SELECTORS = [
    'button[aria-label*="Add files"]',
    'button[aria-label*="Attach"]',
    'button[aria-label*="attach"]',
    'button[aria-label*="Upload"]',
    'button[aria-label*="upload"]',
    'button[data-testid*="upload"]',
    'button[data-testid*="attach"]',
    '[aria-label*="Add content"]',
    'button[aria-label*="Add file"]',
]


class ClaudeTranslatorAgent:
    """Translation agent using Claude via browser automation.

    Wraps ClaudeDataAgent to provide multi-turn translation with conversation
    splitting, file upload, and progress tracking.
    """

    def __init__(self, config: ClaudeTranslatorConfig | None = None):
        self.config = config or ClaudeTranslatorConfig()
        self._agent: ClaudeDataAgent | None = None
        self.results: list[TranslationResult] = []
        self.conversation_index = 0
        self.turn_in_conversation = 0
        self.progress: ProgressState | None = None
        self._progress_path: Path | None = None

    @property
    def session_id(self) -> str:
        if self._agent:
            return self._agent.session_id
        return ""

    async def __aenter__(self):
        self._agent = ClaudeDataAgent(self.config)
        await self._agent.__aenter__()
        return self

    async def __aexit__(self, *exc):
        if self._agent:
            await self._agent.__aexit__(*exc)
            self._agent = None

    def should_split_conversation(self) -> bool:
        return self.turn_in_conversation >= self.config.max_turns_per_conversation

    def init_progress(
        self, document_id: str, total_chunks: int, progress_path: str | Path,
    ) -> None:
        """Initialize or resume progress tracking.

        If a progress file exists at the path, it will be loaded to allow
        resuming from a previous run.
        """
        self._progress_path = Path(progress_path)
        existing = ProgressState.load(self._progress_path)
        if existing and existing.document_id == document_id:
            self.progress = existing
            self.conversation_index = existing.current_conversation_index
            self.turn_in_conversation = existing.current_turn_in_conversation
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
            self.progress.save(self._progress_path)

    async def start_new_conversation(self) -> None:
        """Navigate to claude.ai/new and reset conversation state."""
        if not self._agent:
            raise RuntimeError("Agent not started. Use async with.")
        page = await self._agent.browser_mgr.ensure_page()
        await page.goto(self.config.base_url)
        self._agent.history.clear()
        self.conversation_index += 1
        self.turn_in_conversation = 0
        logger.info("Started new conversation (index: %d)", self.conversation_index)

    async def upload_file(self, file_path: str, prompt_text: str = "") -> bool:
        """Upload a file via Claude's file upload mechanism.

        Strategy 1: Click the attach button and use the file chooser dialog.
        Strategy 2: Directly set files on hidden input[type=file] elements.
        Strategy 3: Use JS to expose hidden file inputs and set files.
        """
        if not self._agent:
            raise RuntimeError("Agent not started. Use async with.")

        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        page = await self._agent._ensure_ready()
        abs_path = str(p)
        attached = False

        # Strategy 1: Click attach button and intercept file chooser
        for btn_selector in ATTACH_BUTTON_SELECTORS:
            try:
                btn = page.locator(btn_selector).first
                if await btn.count() > 0:
                    async with page.expect_file_chooser(timeout=5000) as fc_info:
                        await btn.click()
                    file_chooser = await fc_info.value
                    await file_chooser.set_files(abs_path)
                    logger.info("File attached via attach button: %s", btn_selector)
                    attached = True
                    break
            except Exception:
                continue

        # Strategy 2: Try existing file inputs directly (even hidden ones)
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

        # Strategy 3: JS fallback — expose hidden file input
        if not attached:
            try:
                await page.evaluate("""() => {
                    let input = document.querySelector('input[type="file"]');
                    if (input) {
                        input.style.display = 'block';
                        input.style.visibility = 'visible';
                        input.style.opacity = '1';
                        input.style.position = 'fixed';
                        input.style.top = '0';
                        input.style.left = '0';
                        input.style.zIndex = '99999';
                    }
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
                await type_text(input_el, prompt_text)
            except Exception as e:
                logger.warning("File attached but failed to type text: %s", e)

        return True

    async def translate_text(
        self,
        chunk: TranslationChunk,
        system_prompt: str | None = None,
        continue_prompt: str | None = None,
        is_first_turn: bool = False,
    ) -> TranslationResult:
        """Translate a text chunk via Claude browser chat."""
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
            response = await self._agent.chat(prompt)
            elapsed_ms = (time.monotonic() - start) * 1000
            self.turn_in_conversation += 1

            # Capture thinking from the last conversation turn
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
        """Translate a file (PDF/image) chunk via Claude with file upload."""
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
            uploaded = await self.upload_file(chunk.source_file, prompt)
            if not uploaded:
                raise RuntimeError("Failed to upload file")

            # Use the data agent's detector and flow for submit + wait
            page = await self._agent.browser_mgr.ensure_page()
            count_before, selector_hint = await self._agent.detector.count_responses(
                page, self._agent.SELECTORS.response
            )

            from ...browser.dom import click_submit
            await click_submit(page, self._agent.SELECTORS.submit)

            response = await self._agent.detector.wait_for_new_response(
                page, self._agent.SELECTORS.response, count_before,
                selector_hint=selector_hint,
            )

            thinking, thinking_source = await self._agent._extract_thinking(page)

            # Capture raw API responses and record in history
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
                "max_turns_per_conversation": self.config.max_turns_per_conversation,
            },
            "results": [r.to_dict() for r in self.results],
            "total_chunks": len(self.results),
            "successful_chunks": sum(1 for r in self.results if r.success),
            "conversations_used": self.conversation_index + 1,
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
