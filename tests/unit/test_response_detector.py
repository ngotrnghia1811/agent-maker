"""Unit tests for browser/response_detector.py using mocked Playwright page."""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from universal_agents.browser.response_detector import ResponseDetector
from universal_agents.core.config import BrowserConfig
from universal_agents.core.exceptions import ResponseTimeoutError


def make_mock_page(count_sequence: list[int], text_sequence: list[str]):
    """Create a mock Playwright page that returns canned locator data.

    count_sequence: successive values returned by locator.count()
    text_sequence: successive values returned by locator.last.text_content()

    When a sequence is exhausted, the last value is repeated indefinitely.
    """
    page = AsyncMock()
    locator = AsyncMock()
    count_iter = iter(count_sequence)
    text_iter = iter(text_sequence)

    def count_fn():
        try:
            return next(count_iter)
        except StopIteration:
            return count_sequence[-1] if count_sequence else 0

    def text_fn():
        try:
            return next(text_iter)
        except StopIteration:
            return text_sequence[-1] if text_sequence else ""

    locator.count = AsyncMock(side_effect=count_fn)

    last_locator = AsyncMock()
    last_locator.text_content = AsyncMock(side_effect=text_fn)
    type(locator).last = PropertyMock(return_value=last_locator)

    page.locator = MagicMock(return_value=locator)
    page.wait_for_timeout = AsyncMock()

    return page


class TestResponseDetector:
    @pytest.fixture
    def detector(self):
        config = BrowserConfig(
            timeout=5,
            response_check_interval=0.01,
            required_stable_checks=2,
        )
        return ResponseDetector(config)

    @pytest.mark.asyncio
    async def test_detects_new_response(self, detector):
        # count goes 0 → 0 → 1, then text stabilizes after 2 checks
        page = make_mock_page(
            count_sequence=[0, 0, 1, 1, 1, 1],  # extra for _find_working_selector
            text_sequence=["hello", "hello world", "hello world"],
        )
        result = await detector.wait_for_new_response(page, [".response"], count_before=0)
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_timeout_no_new_response(self, detector):
        # count never increases
        config = BrowserConfig(
            timeout=0.05,
            response_check_interval=0.01,
            required_stable_checks=2,
        )
        det = ResponseDetector(config)
        page = make_mock_page(
            count_sequence=[0] * 100,
            text_sequence=[""] * 100,
        )
        with pytest.raises(ResponseTimeoutError):
            await det.wait_for_new_response(page, [".response"], count_before=0)

    @pytest.mark.asyncio
    async def test_count_responses(self, detector):
        page = make_mock_page(count_sequence=[3], text_sequence=[])
        count, selector = await detector.count_responses(page, [".response"])
        assert count == 3
        assert selector == ".response"
