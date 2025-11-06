"""Shared test fixtures."""

import pytest


@pytest.fixture
def sample_config():
    """Return a minimal BrowserConfig for testing."""
    from universal_agents.core.config import BrowserConfig

    return BrowserConfig(
        provider_name="test",
        base_url="https://example.com",
        headless=True,
        timeout=30,
        response_check_interval=0.1,
        required_stable_checks=2,
    )
