"""Unit tests for _send_message file-upload-for-long-messages behaviour."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from universal_agents.browser.base_browser_agent import BaseBrowserAgent
from universal_agents.providers.gemini.data import GeminiDataAgent
from universal_agents.providers.gemini.config import GeminiDataConfig
from universal_agents.providers.claude.data import ClaudeDataAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_page():
    """Return a minimal AsyncMock Playwright page."""
    page = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.keyboard = AsyncMock()
    return page


def _mock_locator(visible=True, count=1):
    loc = AsyncMock()
    loc.is_visible = AsyncMock(return_value=visible)
    loc.count = AsyncMock(return_value=count)
    loc.evaluate = AsyncMock(side_effect=lambda js: "div")
    loc.click = AsyncMock()
    loc.press_sequentially = AsyncMock()
    loc.press = AsyncMock()
    type(loc).page = MagicMock(return_value=_mock_page())
    return loc


class _MockFileChooserCtx:
    """Fake async context manager for page.expect_file_chooser()."""

    def __init__(self, file_chooser):
        self._fc = file_chooser
        # Playwright returns fc_info.value as an awaitable
        fut = asyncio.get_event_loop().create_future()
        fut.set_result(file_chooser)
        self.value = fut

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


# ---------------------------------------------------------------------------
# BaseBrowserAgent._send_message  (always types, regardless of length)
# ---------------------------------------------------------------------------

class TestBaseSendMessage:
    @pytest.mark.asyncio
    async def test_short_message_types(self):
        """Short messages should be typed via type_text."""
        page = _mock_page()
        loc = _mock_locator()
        with (
            patch("universal_agents.browser.base_browser_agent.find_element", new=AsyncMock(return_value=loc)),
            patch("universal_agents.browser.base_browser_agent.type_text", new=AsyncMock()) as mock_type,
        ):
            agent = BaseBrowserAgent.__new__(BaseBrowserAgent)
            agent.SELECTORS = MagicMock()
            await agent._send_message(page, "hi there")
            mock_type.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_long_message_still_types(self):
        """Base class has no file upload — always types."""
        page = _mock_page()
        loc = _mock_locator()
        long_msg = " ".join(["word"] * 200)
        with (
            patch("universal_agents.browser.base_browser_agent.find_element", new=AsyncMock(return_value=loc)),
            patch("universal_agents.browser.base_browser_agent.type_text", new=AsyncMock()) as mock_type,
        ):
            agent = BaseBrowserAgent.__new__(BaseBrowserAgent)
            agent.SELECTORS = MagicMock()
            await agent._send_message(page, long_msg)
            mock_type.assert_awaited_once()


# ---------------------------------------------------------------------------
# GeminiDataAgent._send_message  (uploads > threshold, types otherwise)
# ---------------------------------------------------------------------------

class TestGeminiSendMessage:
    def _make_agent(self):
        """Create a bare GeminiDataAgent without __init__ side-effects."""
        agent = GeminiDataAgent.__new__(GeminiDataAgent)
        agent.SELECTORS = GeminiDataAgent.SELECTORS
        agent.LONG_MESSAGE_WORD_THRESHOLD = 100
        return agent

    @pytest.mark.asyncio
    async def test_short_message_types(self):
        """Messages ≤100 words are typed normally."""
        page = _mock_page()
        agent = self._make_agent()
        short_msg = " ".join(["word"] * 50)
        with (
            patch("universal_agents.providers.gemini.data.find_element", new=AsyncMock(return_value=_mock_locator())),
            patch("universal_agents.providers.gemini.data.type_text", new=AsyncMock()) as mock_type,
        ):
            await agent._send_message(page, short_msg)
            mock_type.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_long_message_uploads_file(self):
        """Messages >100 words trigger file upload."""
        page = _mock_page()
        agent = self._make_agent()
        long_msg = " ".join(["word"] * 200)
        with patch.object(agent, "_upload_file_to_gemini", new=AsyncMock(return_value=True)) as mock_upload:
            await agent._send_message(page, long_msg)
            mock_upload.assert_awaited_once_with(page, long_msg)

    @pytest.mark.asyncio
    async def test_long_message_fallback_on_upload_failure(self):
        """If file upload fails, falls back to type_text."""
        page = _mock_page()
        agent = self._make_agent()
        long_msg = " ".join(["word"] * 200)
        with (
            patch.object(agent, "_upload_file_to_gemini", new=AsyncMock(return_value=False)),
            patch("universal_agents.providers.gemini.data.find_element", new=AsyncMock(return_value=_mock_locator())),
            patch("universal_agents.providers.gemini.data.type_text", new=AsyncMock()) as mock_type,
        ):
            await agent._send_message(page, long_msg)
            mock_type.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exactly_100_words_types(self):
        """Exactly 100 words should NOT trigger upload (boundary: >100)."""
        page = _mock_page()
        agent = self._make_agent()
        msg_100 = " ".join(["word"] * 100)
        with (
            patch("universal_agents.providers.gemini.data.find_element", new=AsyncMock(return_value=_mock_locator())),
            patch("universal_agents.providers.gemini.data.type_text", new=AsyncMock()) as mock_type,
        ):
            await agent._send_message(page, msg_100)
            mock_type.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_101_words_triggers_upload(self):
        """101 words should trigger upload."""
        page = _mock_page()
        agent = self._make_agent()
        msg_101 = " ".join(["word"] * 101)
        with patch.object(agent, "_upload_file_to_gemini", new=AsyncMock(return_value=True)) as mock_upload:
            await agent._send_message(page, msg_101)
            mock_upload.assert_awaited_once()


# ---------------------------------------------------------------------------
# GeminiDataAgent._upload_file_to_gemini
# ---------------------------------------------------------------------------

class TestUploadFileToGemini:
    def _make_agent(self):
        agent = GeminiDataAgent.__new__(GeminiDataAgent)
        agent.SELECTORS = GeminiDataAgent.SELECTORS
        return agent

    @pytest.mark.asyncio
    async def test_upload_via_hidden_button(self):
        """Strategy 1: hidden file upload button triggers file chooser."""
        page = _mock_page()
        agent = self._make_agent()

        file_chooser = AsyncMock()
        file_chooser.set_files = AsyncMock()

        btn_locator = AsyncMock()
        btn_locator.count = AsyncMock(return_value=1)
        btn_locator.dispatch_event = AsyncMock()

        input_locator = _mock_locator()

        def locator_side_effect(sel):
            loc = AsyncMock()
            if "hidden-local-file-upload" in sel:
                loc.first = btn_locator
            elif 'input[type="file"]' in sel:
                loc.first = AsyncMock()
                loc.first.count = AsyncMock(return_value=0)
            else:
                loc.first = AsyncMock()
                loc.first.count = AsyncMock(return_value=0)
            return loc

        page.locator = MagicMock(side_effect=locator_side_effect)

        # Mock expect_file_chooser as async context manager
        fc_ctx = _MockFileChooserCtx(file_chooser)
        page.expect_file_chooser = MagicMock(return_value=fc_ctx)

        with (
            patch("universal_agents.providers.gemini.data.find_element", new=AsyncMock(return_value=input_locator)),
            patch("universal_agents.providers.gemini.data.type_text", new=AsyncMock()) as mock_type,
        ):
            result = await agent._upload_file_to_gemini(page, "test content " * 50)

        assert result is True
        file_chooser.set_files.assert_awaited_once()
        mock_type.assert_awaited_once()  # Short instruction prompt typed

    @pytest.mark.asyncio
    async def test_all_strategies_fail_returns_false(self):
        """When all upload strategies fail, returns False."""
        page = _mock_page()
        agent = self._make_agent()

        # Make all locators return count=0
        fail_locator = AsyncMock()
        fail_locator.count = AsyncMock(return_value=0)

        def locator_side_effect(sel):
            loc = AsyncMock()
            loc.first = fail_locator
            return loc

        page.locator = MagicMock(side_effect=locator_side_effect)

        result = await agent._upload_file_to_gemini(page, "test content " * 50)
        assert result is False


# ---------------------------------------------------------------------------
# LONG_MESSAGE_WORD_THRESHOLD class attribute
# ---------------------------------------------------------------------------

class TestThresholdAttribute:
    def test_base_class_has_threshold(self):
        assert BaseBrowserAgent.LONG_MESSAGE_WORD_THRESHOLD == 100

    def test_gemini_inherits_threshold(self):
        assert GeminiDataAgent.LONG_MESSAGE_WORD_THRESHOLD == 100

    def test_claude_has_higher_threshold(self):
        assert ClaudeDataAgent.LONG_MESSAGE_WORD_THRESHOLD == 1000


# ---------------------------------------------------------------------------
# ClaudeDataAgent._send_message  (pastes > threshold, types otherwise)
# ---------------------------------------------------------------------------

class TestClaudeSendMessage:
    def _make_agent(self):
        agent = ClaudeDataAgent.__new__(ClaudeDataAgent)
        agent.SELECTORS = ClaudeDataAgent.SELECTORS
        agent.LONG_MESSAGE_WORD_THRESHOLD = 1000
        return agent

    @pytest.mark.asyncio
    async def test_short_message_types(self):
        """Messages ≤1000 words are typed normally."""
        page = _mock_page()
        agent = self._make_agent()
        short_msg = " ".join(["word"] * 500)
        with (
            patch("universal_agents.providers.claude.data.find_element", new=AsyncMock(return_value=_mock_locator())),
            patch("universal_agents.providers.claude.data.type_text", new=AsyncMock()) as mock_type,
        ):
            await agent._send_message(page, short_msg)
            mock_type.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_long_message_pastes(self):
        """Messages >1000 words trigger clipboard paste."""
        page = _mock_page()
        agent = self._make_agent()
        long_msg = " ".join(["word"] * 1500)
        with patch.object(agent, "_paste_long_message", new=AsyncMock(return_value=True)) as mock_paste:
            await agent._send_message(page, long_msg)
            mock_paste.assert_awaited_once_with(page, long_msg)

    @pytest.mark.asyncio
    async def test_paste_failure_falls_back_to_type(self):
        """If paste fails, falls back to type_text."""
        page = _mock_page()
        agent = self._make_agent()
        long_msg = " ".join(["word"] * 1500)
        with (
            patch.object(agent, "_paste_long_message", new=AsyncMock(return_value=False)),
            patch("universal_agents.providers.claude.data.find_element", new=AsyncMock(return_value=_mock_locator())),
            patch("universal_agents.providers.claude.data.type_text", new=AsyncMock()) as mock_type,
        ):
            await agent._send_message(page, long_msg)
            mock_type.assert_awaited_once()
