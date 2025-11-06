"""Unit tests for core/retry.py."""

import pytest

from universal_agents.core.exceptions import AgentError, BrowserError
from universal_agents.core.retry import retry


class TestRetry:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await succeed()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01)
        async def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise BrowserError("fail")
            return "ok"

        result = await fail_twice()
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        @retry(max_attempts=2, base_delay=0.01)
        async def always_fail():
            raise AgentError("permanent")

        with pytest.raises(AgentError, match="permanent"):
            await always_fail()

    @pytest.mark.asyncio
    async def test_non_matching_exception_not_retried(self):
        call_count = 0

        @retry(max_attempts=3, base_delay=0.01, exceptions=(BrowserError,))
        async def fail_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await fail_with_value_error()
        assert call_count == 1
