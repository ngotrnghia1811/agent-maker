"""Perplexity DOM selectors."""

from ...browser.selectors import ProviderSelectors

PPLX_SELECTORS = ProviderSelectors(
    input=[
        "textarea[placeholder*='Ask']",
        "textarea[placeholder*='Search']",
        "textarea[placeholder*='Follow up']",
        "textarea[aria-label*='Search']",
        "textarea[aria-label*='Ask']",
        "[contenteditable='true']",
        "div[contenteditable='true']",
        "textarea",
        "[role='textbox']",
        "input[type='text']",
    ],
    submit=[
        'button[aria-label*="Submit"]',
        'button[aria-label*="Search"]',
        'button[aria-label*="Send"]',
        '[data-testid*="submit"]',
        '[data-testid*="search"]',
        'button[type="submit"]',
    ],
    response=[
        "div.prose",
        "div[class*='prose'][class*='dark']",
        "div[class*='prose'][class*='break-words']",
        "div[class*='threadContentWidth'] div.prose",
        "[class*='thread'] div[class*='prose']",
        ".response-content",
        '[data-testid="response-text"]',
        ".message-content",
    ],
    loading=[
        ".searching",
        ".loading",
        "[aria-label*='Loading']",
    ],
)

CITATION_SELECTORS = [
    ".sources-list",
    "[data-testid='sources']",
    ".citation-list",
    "[class*='source']",
    "[class*='citation']",
]

# ---------------------------------------------------------------------------
# Deep Research mode selectors
# ---------------------------------------------------------------------------

# Buttons / toggles that enable Deep Research mode before submitting
DEEP_RESEARCH_TOGGLE_SELECTORS = [
    # data-testid patterns (most stable across UI changes)
    '[data-testid="deep-research-toggle"]',
    '[data-testid="deep-research-button"]',
    '[data-testid*="deep-research"]',
    # Aria-label patterns
    'button[aria-label*="Deep Research"]',
    'button[aria-label*="deep research"]',
    # Text-based (Playwright :has-text pseudo)
    'button:has-text("Deep Research")',
    '[role="button"]:has-text("Deep Research")',
    # Class / generic patterns
    '[class*="deep-research"]',
    '[class*="deepResearch"]',
    # Fallback — icon button near the search bar labelled "Pro" or "Research"
    'button:has-text("Pro")',
    'button[aria-label*="Research"]',
]

# Indicators that Deep Research is currently running
DEEP_RESEARCH_PROGRESS_SELECTORS = [
    # Explicit progress / status text
    '[data-testid="research-progress"]',
    '[data-testid*="research-status"]',
    '[class*="research-progress"]',
    '[class*="researchProgress"]',
    # Loading / thinking states
    '[aria-label*="researching"]',
    '[aria-label*="Researching"]',
    # Generic streaming/loading spinners that appear only during deep research
    '.research-step',
    '[class*="researchStep"]',
    # Text-based progress cues
    ':has-text("Searching the web")',
    ':has-text("Reading sources")',
    ':has-text("Analyzing")',
]

# Indicator that Deep Research mode is *active* (toggle is ON)
DEEP_RESEARCH_ACTIVE_INDICATORS = [
    '[data-testid*="deep-research"][aria-pressed="true"]',
    '[data-testid*="deep-research"][class*="active"]',
    '[data-testid*="deep-research"][class*="selected"]',
    '[class*="deepResearch"][class*="active"]',
    'button:has-text("Deep Research")[aria-pressed="true"]',
]
