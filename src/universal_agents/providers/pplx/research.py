"""Perplexity deep research agent — browser automation with Deep Research mode."""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import Page

from ...browser.base_browser_agent import BaseBrowserAgent
from ...browser.dom import find_element, type_text, click_submit
from .chat import Citation, PerplexityChatAgent
from .config import PerplexityResearchConfig
from .selectors import (
    CITATION_SELECTORS,
    DEEP_RESEARCH_ACTIVE_INDICATORS,
    DEEP_RESEARCH_PROGRESS_SELECTORS,
    DEEP_RESEARCH_TOGGLE_SELECTORS,
    PPLX_SELECTORS,
)

logger = logging.getLogger(__name__)


@dataclass
class ResearchReport:
    """Structured output of a Perplexity deep research task."""

    query: str
    content: str
    citations: list[Citation] = field(default_factory=list)
    mode_used: str = "standard"  # "deep" or "standard"
    elapsed_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_markdown(self) -> str:
        """Render the report as a Markdown string."""
        lines = [
            f"# Research Report",
            f"",
            f"**Query:** {self.query}",
            f"**Mode:** {self.mode_used}",
            f"**Generated:** {self.timestamp}",
            f"**Duration:** {self.elapsed_seconds:.1f}s",
            f"",
            f"---",
            f"",
            self.content,
        ]

        if self.citations:
            lines += ["", "---", "", "## Sources", ""]
            for i, c in enumerate(self.citations, 1):
                if c.url:
                    title = c.title or c.url
                    lines.append(f"{i}. [{title}]({c.url})")
                else:
                    lines.append(f"{i}. {c.text}")

        return "\n".join(lines)

    def save(self, output_dir: Path, filename: str | None = None) -> Path:
        """Save the report to *output_dir* as a Markdown file.

        Returns the path to the saved file.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            safe_query = "".join(
                c if c.isalnum() or c in " -_" else "_" for c in self.query
            )[:60].strip()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{ts}_{safe_query}.md"

        path = output_dir / filename
        path.write_text(self.to_markdown(), encoding="utf-8")
        logger.info("Report saved: %s", path)
        return path


class PerplexityResearchAgent(BaseBrowserAgent):
    """Perplexity browser agent for deep research tasks.

    Attempts to enable Perplexity's "Deep Research" mode before submitting
    a query.  When ``research_mode="auto"`` (the default), it gracefully falls
    back to a standard Perplexity search if the Deep Research toggle cannot be
    found or activated.

    Usage::

        config = PerplexityResearchConfig(
            storage_state="storage/pplx_storage_state.json",
            research_mode="auto",
            output_dir="reports/",
        )
        async with PerplexityResearchAgent(config) as agent:
            report = await agent.research("What are the latest advances in fusion energy?")
            report.save(Path("reports/"))
            print(report.content)
    """

    SELECTORS = PPLX_SELECTORS

    def __init__(self, config: PerplexityResearchConfig | None = None):
        super().__init__(config or PerplexityResearchConfig())
        self._research_config: PerplexityResearchConfig = self.browser_config  # type: ignore[assignment]
        self.last_report: ResearchReport | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def research(self, query: str, save: bool = True) -> ResearchReport:
        """Research *query* and return a :class:`ResearchReport`.

        Args:
            query: The research question or topic.
            save:  If ``True``, automatically save the Markdown report to
                   ``config.output_dir``.

        Returns:
            A populated :class:`ResearchReport`.
        """
        start = time.monotonic()
        page = await self._ensure_ready()
        await self._pre_chat_hook(page)

        mode_used = "standard"

        # 1. Try to enable Deep Research mode (unless explicitly disabled)
        if self._research_config.research_mode in ("deep", "auto"):
            enabled = await self._enable_deep_research(page)
            if enabled:
                mode_used = "deep"
                logger.info("Deep Research mode enabled")
            elif self._research_config.research_mode == "deep":
                raise RuntimeError(
                    "Deep Research mode could not be activated and research_mode='deep'. "
                    "Set research_mode='auto' to fall back to standard search."
                )
            else:
                logger.info("Deep Research toggle not found — using standard search")

        # 2. Type the query
        input_el = await find_element(page, self.SELECTORS.input)
        await type_text(input_el, query)

        # 3. Count existing responses before submitting
        count_before, selector_hint = await self.detector.count_responses(
            page, self.SELECTORS.response
        )

        # 4. Submit
        await click_submit(page, self.SELECTORS.submit)

        # 5. Wait — Deep Research can take several minutes
        wait_timeout = (
            self._research_config.max_research_wait
            if mode_used == "deep"
            else self._research_config.timeout
        )
        response_text = await self._wait_for_research_response(
            page,
            count_before,
            selector_hint=selector_hint,
            timeout=wait_timeout,
            is_deep=mode_used == "deep",
        )

        # 6. Extract citations
        citations = await self._extract_citations(page)

        elapsed = time.monotonic() - start

        report = ResearchReport(
            query=query,
            content=response_text,
            citations=citations,
            mode_used=mode_used,
            elapsed_seconds=elapsed,
        )
        self.last_report = report

        if save:
            report.save(Path(self._research_config.output_dir))

        return report

    # ------------------------------------------------------------------
    # Deep Research mode helpers
    # ------------------------------------------------------------------

    async def _enable_deep_research(self, page: Page) -> bool:
        """Try to click the Deep Research toggle.

        Returns ``True`` if the toggle was found and activated, ``False`` otherwise.
        """
        for selector in DEEP_RESEARCH_TOGGLE_SELECTORS:
            try:
                el = page.locator(selector).first
                if await el.count() == 0:
                    continue
                if not await el.is_visible():
                    continue

                # Check if already active
                if await self._is_deep_research_active(page):
                    return True

                await el.click()
                await page.wait_for_timeout(600)

                # Verify it activated
                if await self._is_deep_research_active(page):
                    return True

                # Some toggles are just buttons; assume a single click activates
                logger.debug("Clicked Deep Research toggle (%s)", selector)
                return True

            except Exception as exc:
                logger.debug("Selector %s: %s", selector, exc)
                continue

        return False

    async def _is_deep_research_active(self, page: Page) -> bool:
        """Return ``True`` if a Deep Research active indicator is present."""
        for selector in DEEP_RESEARCH_ACTIVE_INDICATORS:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except Exception:
                continue
        return False

    # ------------------------------------------------------------------
    # Response waiting with Deep Research awareness
    # ------------------------------------------------------------------

    async def _wait_for_research_response(
        self,
        page: Page,
        count_before: int,
        *,
        selector_hint: str | None,
        timeout: int,
        is_deep: bool,
    ) -> str:
        """Wait for the research response, with extended timeout for Deep Research.

        While waiting in deep mode we log progress indicators so the user can
        see the agent is still working.
        """
        if not is_deep:
            # Standard path — use the normal response detector
            original_timeout = self.detector.timeout
            self.detector.timeout = timeout
            try:
                return await self.detector.wait_for_new_response(
                    page, self.SELECTORS.response, count_before, selector_hint=selector_hint
                )
            finally:
                self.detector.timeout = original_timeout

        # Deep Research path — poll with progress logging
        start = time.monotonic()
        deadline = start + timeout
        selector = selector_hint or self.SELECTORS.response[0]

        logger.info("Waiting up to %ds for Deep Research to complete…", timeout)

        last_progress_log = 0.0

        while time.monotonic() < deadline:
            # Check if response has appeared
            count_now = await page.locator(selector).count()
            if count_now > count_before:
                break

            # Log progress hints every 15 seconds
            elapsed = time.monotonic() - start
            if elapsed - last_progress_log >= 15:
                progress_msg = await self._get_progress_message(page)
                if progress_msg:
                    logger.info("[%.0fs] %s", elapsed, progress_msg)
                else:
                    logger.info("[%.0fs] Still researching…", elapsed)
                last_progress_log = elapsed

            await page.wait_for_timeout(2000)
        else:
            logger.warning(
                "Deep Research did not complete within %ds — returning partial content", timeout
            )

        # Wait for content to stabilize (borrow from normal detector, extended timeout)
        original_timeout = self.detector.timeout
        remaining = max(30, int(deadline - time.monotonic()))
        self.detector.timeout = remaining
        try:
            return await self.detector.wait_for_new_response(
                page, self.SELECTORS.response, count_before, selector_hint=selector
            )
        finally:
            self.detector.timeout = original_timeout

    async def _get_progress_message(self, page: Page) -> str | None:
        """Return a human-readable progress message if one is visible."""
        for selector in DEEP_RESEARCH_PROGRESS_SELECTORS:
            try:
                el = page.locator(selector).first
                if await el.count() > 0 and await el.is_visible():
                    text = (await el.text_content() or "").strip()
                    if text:
                        return text[:120]
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # Citation extraction (delegated to PerplexityChatAgent static helpers)
    # ------------------------------------------------------------------

    async def _extract_citations(self, page: Page) -> list[Citation]:
        """Extract citations from the current page."""
        citations: list[Citation] = []
        for selector in CITATION_SELECTORS:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                if count == 0:
                    continue
                for i in range(count):
                    el = elements.nth(i)
                    text = (await el.text_content() or "").strip()
                    if not text or not PerplexityChatAgent._is_citation_text(text):
                        continue
                    citation = PerplexityChatAgent._parse_citation(text)

                    link = el.locator("a").first
                    if await link.count() > 0:
                        href = await link.get_attribute("href")
                        if href:
                            citation.url = href
                        if not citation.title:
                            citation.title = (await link.text_content() or "").strip()

                    citations.append(citation)
                if citations:
                    break
            except Exception:
                continue
        logger.debug("Extracted %d citations", len(citations))
        return citations
