"""Gemini DOM selectors (validated against Gemini 2025-06 Angular UI)."""

from ...browser.selectors import ProviderSelectors

GEMINI_SELECTORS = ProviderSelectors(
    input=[
        "div[contenteditable='true'][aria-label*='prompt']",
        "div[contenteditable='true']",
        "[contenteditable='true']",
        "rich-textarea div[contenteditable='true']",
    ],
    submit=[
        "button[aria-label='Send message']",
        "button[aria-label*='Send']",
        "button[aria-label*='Submit']",
    ],
    response=[
        ".response-container-content .markdown",
        ".markdown.markdown-main-panel",
        "message-content .markdown",
        ".model-response-text",
        ".response-container-content",
        "model-response",
    ],
    loading=[
        ".response-container-header-processing-state",
        "[aria-label*='Loading']",
    ],
    new_chat=[
        "a[aria-label='New chat']",
        "button:has-text('New chat')",
    ],
)
