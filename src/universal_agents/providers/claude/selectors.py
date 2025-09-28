"""Claude DOM selectors."""

from ...browser.selectors import ProviderSelectors

CLAUDE_SELECTORS = ProviderSelectors(
    input=[
        "div.ProseMirror[contenteditable='true']",
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true']",
        "div[aria-label*='Write your prompt to Claude']",
        "div.ProseMirror",
        "textarea[placeholder*='Message']",
        "textarea[placeholder*='Ask']",
        "[contenteditable='true']",
        "textarea",
        "[role='textbox']",
    ],
    submit=[
        'button[type="submit"]',
        '[aria-label*="Send"]',
        '[data-testid*="send"]',
        'button[aria-label*="Send message"]',
        'button[aria-label*="Submit message"]',
        '[aria-label*="Submit"]',
        'button[class*="send"]',
    ],
    response=[
        ".standard-markdown",
        ".progressive-markdown",
        ".font-claude-response .standard-markdown",
        ".font-claude-response .progressive-markdown",
        "[class*='standard-markdown']",
        "[class*='progressive-markdown']",
        ".message-content",
        '[data-testid="message-content"]',
        ".response-content",
    ],
    loading=[
        "div[data-is-streaming='true']",
    ],
    new_chat=[
        "a[href='/new']",
        "button:has-text('New chat')",
    ],
)
