"""GPT DOM selectors."""

from ...browser.selectors import ProviderSelectors

GPT_SELECTORS = ProviderSelectors(
    input=[
        "#prompt-textarea",
        "textarea[data-id='root']",
        "textarea[placeholder*='Message']",
        "textarea[placeholder*='ChatGPT']",
        "textarea[placeholder*='Send']",
        "[contenteditable='true']",
        "div[contenteditable='true']",
        "textarea",
        "[role='textbox']",
        "input[type='text']",
    ],
    submit=[
        'button[data-testid="send-button"]',
        'button[aria-label*="Send"]',
        'button[aria-label*="Submit"]',
        '[data-testid*="send"]',
        'button[type="submit"]',
        "button.send-button",
    ],
    response=[
        'article[data-testid^="conversation-turn-"]',
        '[data-message-author-role="assistant"]',
        '[data-message-author-role="assistant"] .markdown',
        ".agent-turn .markdown.prose",
        "div.markdown.prose",
        ".markdown",
        ".text-message .markdown",
        '[data-testid="conversation-message-assistant"]',
        '[data-testid="message-content"]',
        ".message-content",
    ],
)
