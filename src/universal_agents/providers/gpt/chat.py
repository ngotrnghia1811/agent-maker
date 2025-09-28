"""GPT chat agent — browser automation."""

from ...browser.base_browser_agent import BaseBrowserAgent
from .config import GPTConfig
from .selectors import GPT_SELECTORS


class GPTChatAgent(BaseBrowserAgent):
    """GPT browser agent (standard chat, no thinking extraction).

    Usage:
        async with GPTChatAgent() as agent:
            response = await agent.chat("Hello GPT!")
            print(response)
    """

    SELECTORS = GPT_SELECTORS

    def __init__(self, config: GPTConfig | None = None):
        super().__init__(config or GPTConfig())
