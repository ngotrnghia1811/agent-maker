# Universal Agents v2 — Migration Plan

**Created:** 2026-03-19
**Scope:** Full rewrite — code/space optimization, Selenium → Playwright, multi-agent monitoring
**Source:** Based on CODEBASE_REPORT.md analysis of v1

---

## 0. Problem Summary (v1)

| Problem | Evidence | Impact |
|---------|----------|--------|
| Massive code duplication | 5 browser agents each reimplement the same chat loop (1548 + 835 + 597 + 635 + 1321 = ~4900 lines of near-identical logic) | Hard to fix bugs, every UI change requires 5+ edits |
| Copy-pasted JS constants | `FETCH_OVERRIDE_JS` and `THINKING_EXTRACTOR_JS` duplicated across claude chat-agent and data-agent (~300+ lines each, ×2) | Drift risk, doubled file sizes |
| No abstract base class | `chat()`, `get_history()`, `get_turns()` etc. described in docs but never enforced in code | No type safety, agents silently diverge |
| No dependency manifest | No `requirements.txt`, `pyproject.toml`, or `setup.py` | Impossible to install, version, or reproduce |
| SeleniumBase + Chrome profile copying | Temp profile from user profile, `uc_mode`, CDP events — complex and fragile | Slow startup (~5-8s), frequent stale profile errors |
| Each agent = standalone directory | 7 providers × up to 5 agent types = 35 possible directories, each with its own `parameter_parser.py` | ~12,000 lines of config/parser boilerplate |
| No shared utilities | DOM selectors, retry logic, output saving, history management all reimplemented per agent | ~60% of agent code is not agent-specific |
| Integration tests only | Every test requires a live browser or API key; no mocking, no CI | Zero automated quality gates |
| Empty placeholders | 5 empty `research-agent/` dirs, empty `rag-agent/`, minimal `vscode-llm/` | Clutter, misleading project structure |
| ~200+ files, ~25,000 lines | Benchmark datasets, debug artifacts, chat exports, draft docs | Repository is 10× larger than the actual agent code |

---

## 1. v2 Target Architecture

### 1.1 Directory Structure

```
universal-agents-v2/
│
├── pyproject.toml                          # Single dependency manifest (PEP 621)
├── README.md                               # Project overview
├── .env.example                            # Template for required env vars
│
├── src/
│   └── universal_agents/
│       ├── __init__.py                     # Public exports
│       │
│       ├── core/                           # ── Shared Foundation ──
│       │   ├── __init__.py
│       │   ├── base_agent.py               # ABC: BaseChatAgent, BaseDataAgent
│       │   ├── types.py                    # Message, ConversationTurn, TurnResult, etc.
│       │   ├── config.py                   # BaseConfig dataclass + env loader
│       │   ├── history.py                  # ConversationHistory manager
│       │   ├── output.py                   # Unified output saving (JSON, TXT, MD)
│       │   ├── retry.py                    # Retry decorator with backoff
│       │   ├── exceptions.py               # AgentError, BrowserError, APIError, TimeoutError
│       │   └── logging.py                  # Structured logging + terminal capture
│       │
│       ├── browser/                        # ── Playwright Browser Layer ──
│       │   ├── __init__.py
│       │   ├── base_browser_agent.py       # ABC for all browser agents (extends BaseChatAgent)
│       │   ├── browser_manager.py          # Playwright context lifecycle (launch, reuse, close)
│       │   ├── dom.py                      # DOM interaction helpers (find, type, click, wait)
│       │   ├── selectors.py                # Provider selector registry (CSS/XPath per provider)
│       │   ├── response_detector.py        # Response stabilization logic (shared)
│       │   └── js/                         # Injected JavaScript (single source of truth)
│       │       ├── fetch_override.js       # Intercept API responses
│       │       └── thinking_extractor.js   # React state search for thinking blocks
│       │
│       ├── api/                            # ── HTTP API Layer ──
│       │   ├── __init__.py
│       │   ├── base_api_agent.py           # ABC for API agents (extends BaseChatAgent)
│       │   └── http_client.py              # Shared httpx client with retry + streaming
│       │
│       ├── cli/                            # ── CLI Subprocess Layer ──
│       │   ├── __init__.py
│       │   └── base_cli_agent.py           # ABC for CLI agents (extends BaseChatAgent)
│       │
│       ├── providers/                      # ── Provider Implementations ──
│       │   ├── __init__.py
│       │   ├── claude/
│       │   │   ├── __init__.py
│       │   │   ├── chat.py                 # ClaudeChatAgent (extends BaseBrowserAgent)
│       │   │   ├── data.py                 # ClaudeDataAgent
│       │   │   ├── translator.py           # ClaudeTranslatorAgent (wraps data agent)
│       │   │   ├── config.py               # ClaudeConfig dataclass
│       │   │   └── selectors.py            # Claude DOM selectors (input, submit, response)
│       │   │
│       │   ├── gemini/
│       │   │   ├── __init__.py
│       │   │   ├── chat.py                 # GeminiChatAgent
│       │   │   ├── data.py                 # GeminiDataAgent
│       │   │   ├── config.py
│       │   │   └── selectors.py
│       │   │
│       │   ├── gpt/
│       │   │   ├── __init__.py
│       │   │   ├── chat.py                 # GPTChatAgent
│       │   │   ├── config.py
│       │   │   └── selectors.py
│       │   │
│       │   ├── pplx/
│       │   │   ├── __init__.py
│       │   │   ├── chat.py                 # PerplexityChatAgent
│       │   │   ├── config.py
│       │   │   └── selectors.py
│       │   │
│       │   ├── openrouter/
│       │   │   ├── __init__.py
│       │   │   ├── chat.py                 # OpenRouterChatAgent (extends BaseAPIAgent)
│       │   │   ├── data.py                 # OpenRouterDataAgent
│       │   │   └── config.py
│       │   │
│       │   └── copilot/
│       │       ├── __init__.py
│       │       ├── chat.py                 # CopilotChatAgent (extends BaseCLIAgent)
│       │       └── config.py
│       │
│       └── monitor/                        # ── Agent Monitor ──
│           ├── __init__.py
│           ├── agent_registry.py           # Register, list, query running agents
│           ├── events.py                   # AgentEvent, EventBus (pub/sub)
│           ├── dashboard.py                # Terminal dashboard (rich)
│           └── reporter.py                 # Run reports, cost tracking, error summaries
│
├── tests/
│   ├── conftest.py                         # Shared fixtures, mock browser context
│   ├── unit/
│   │   ├── test_history.py
│   │   ├── test_config.py
│   │   ├── test_output.py
│   │   ├── test_response_detector.py
│   │   ├── test_retry.py
│   │   └── test_selectors.py
│   ├── integration/
│   │   ├── test_claude_chat.py
│   │   ├── test_gemini_chat.py
│   │   ├── test_openrouter_chat.py
│   │   └── ...
│   └── mocks/
│       ├── mock_browser.py                 # Playwright page mock
│       └── mock_responses.py               # Canned HTML/API responses
│
├── docs/
│   ├── AGENT_STRUCTURE.md
│   ├── API_REFERENCE.md
│   └── MIGRATION_GUIDE.md                  # v1 → v2 migration instructions
│
└── examples/
    ├── basic_chat.py
    ├── multi_agent_run.py
    └── translation_job.py
```

**Estimated file count:** ~70 files (down from 200+)
**Estimated lines:** ~8,000-10,000 (down from 25,000+)

### 1.2 What Gets Removed

| v1 Content | Action | Reason |
|------------|--------|--------|
| `raw_data/` (14 benchmark datasets, ~400K examples) | Remove from repo, document download scripts in separate repo or README | Not agent code; inflates repo by GBs |
| `downloaded_files/`, `debug_*.html/json` | Delete | One-off debug artifacts |
| `_draft/`, `_chat_history/`, `_references/` | Delete | Working notes, not distributable |
| `scrape_claude_conversations*.py`, `scrape_diagnose_dom.py` | Move to separate tool or `examples/` | Standalone utility, not core agent logic |
| `ai_docs/` (7 workflow files, ~4,600 lines) | Delete | AI-session-specific, not runtime code |
| `message_draft*.md`, `Codebase Report Prompt.md` | Delete | Working documents |
| Empty placeholder dirs (5 research-agents, rag-agent, vscode-llm) | Delete | No code inside |
| Per-agent `agent_docs/`, `agent_history/`, `agent_archive/` | Delete (replaced by `docs/` + config) | Agent docs were for AI assistant consumption; config replaces description.md |
| Per-agent `latest_logs/`, `downloaded_files/`, `storage/` | Delete (output dirs created at runtime) | Runtime dirs should not be in repo |
| Per-agent duplicate `test_comprehensive.py`, `test_realistic.py`, `test_multi_turn.py` | Consolidate into `tests/integration/` | Near-identical across providers |

### 1.3 Lines-of-Code Reduction Breakdown

| Component | v1 Lines | v2 Lines | Savings | How |
|-----------|----------|----------|---------|-----|
| Browser agent logic (5 agents) | ~4,900 | ~800 | 84% | Shared `BaseBrowserAgent` + per-provider selectors only |
| Parameter parsers (7+ files) | ~3,200 | ~600 | 81% | Single `BaseConfig` + per-provider dataclass |
| Data agents (3 agents) | ~3,500 | ~900 | 74% | Shared `BaseDataAgent` with provider override points |
| JS constants (fetch override + thinking extractor) | ~600 (×2 copies) | ~300 (1 copy, `.js` files) | 75% | External `.js` files, loaded once |
| Test files | ~5,000+ | ~2,000 | 60% | Parameterized tests, mock fixtures, no copy-paste |
| Docs / AI docs / drafts | ~8,000 | ~1,500 | 81% | Consolidated docs, no AI working notes |
| **Total** | ~25,000 | ~8,000-10,000 | **60-68%** | |

---

## 2. Selenium → Playwright Migration

### 2.1 Why Playwright

| Feature | SeleniumBase (v1) | Playwright (v2) | Impact |
|---------|-------------------|------------------|--------|
| Browser launch | ~5-8s (Chrome + ChromeDriver) | ~1-2s (bundled browsers) | 4× faster startup |
| Anti-detection | `uc_mode` (fragile, breaks often) | `playwright-stealth` plugin + persistent contexts | More reliable, actively maintained |
| Profile handling | Copy entire Chrome profile to temp dir | `browser.new_context(storage_state=...)` | No 500MB temp dirs, instant reuse |
| Network interception | JS `fetch` override injection | `page.route()` native API | No JS injection needed for API capture |
| Wait mechanisms | `time.sleep()` + DOM polling | `page.wait_for_selector()`, `page.wait_for_load_state()`, `expect(locator)` | Built-in smart waits, no manual polling loops |
| Async support | None (blocking only) | Native `async/await` | Multiple agents can share an event loop |
| Multi-browser | Chrome only | Chromium + Firefox + WebKit | Cross-browser testing |
| Response capture | JS fetch override → poll JS variable | `page.on("response", handler)` | Native, no race conditions |
| Headless mode | `--headless=new` (Chrome flag) | First-class support | Cleaner, more stable |
| Auto-wait | Manual `WebDriverWait` + `EC.*` | Built-in auto-wait on every action | Less boilerplate |
| Element interaction | `driver.find_element()` + ActionChains | `page.locator()` + `.fill()`, `.click()` | Simpler, more reliable API |
| Dependencies | `seleniumbase` + `selenium` + `chromedriver` | `playwright` (single package, browsers bundled) | Simpler install |

### 2.2 Key Migration Mappings

```python
# ═══════════════════════════════════════════
# v1 (SeleniumBase) → v2 (Playwright)
# ═══════════════════════════════════════════

# ── Browser Launch ──
# v1:
sb = SB(uc=True, headless=True, uc_cdp_events=True, uc_subprocess=True)
sb.open(url)

# v2:
browser = await playwright.chromium.launch(headless=True)
context = await browser.new_context(storage_state="auth.json")  # Reuse login
page = await context.new_page()
await page.goto(url)


# ── Find Element ──
# v1:
element = None
for selector in INPUT_SELECTORS:  # 21 selectors tried one by one
    try:
        element = driver.find_element(By.CSS_SELECTOR, selector)
        break
    except NoSuchElementException:
        continue

# v2:
element = page.locator("div.ProseMirror, textarea[placeholder], div[contenteditable]").first


# ── Type Text ──
# v1:
for word in text.split():
    element.send_keys(word + " ")
    time.sleep(0.05)

# v2:
await element.fill(text)  # or type() for character-by-character


# ── Wait for Response ──
# v1:
count_before = len(driver.find_elements(By.CSS_SELECTOR, ".response-class"))
while True:
    time.sleep(2)
    current = driver.find_element(By.CSS_SELECTOR, ".response-class:last-child").text
    if current == previous and checks >= 3:
        break

# v2:
response_locator = page.locator(".response-class").last
await response_locator.wait_for(state="attached")
await page.wait_for_load_state("networkidle")
# or: await page.wait_for_function("() => !document.querySelector('.loading-indicator')")


# ── Intercept API (Thinking Extraction) ──
# v1:
FETCH_OVERRIDE_JS = """...(100+ lines)..."""
driver.execute_script(FETCH_OVERRIDE_JS)
# then poll: driver.execute_script("return window.__capturedData")

# v2:
captured = []
async def handle_response(response):
    if "chat_conversations" in response.url:
        data = await response.json()
        captured.append(data)

page.on("response", handle_response)
# Data arrives automatically — no polling, no JS injection


# ── Close Browser ──
# v1:
sb.quit()
# + cleanup temp profile dirs manually

# v2:
await context.close()
await browser.close()
# No temp dirs to clean
```

### 2.3 Anti-Detection Strategy (Playwright)

```python
# Install: pip install playwright-stealth

from playwright_stealth import stealth_async

async def create_stealth_context(playwright, storage_state=None):
    """Create a browser context that avoids bot detection."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ]
    )
    context = await browser.new_context(
        storage_state=storage_state,
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
        locale="en-US",
    )
    page = await context.new_page()
    await stealth_async(page)  # Patches navigator.webdriver, plugins, etc.
    return browser, context, page
```

### 2.4 Persistent Login (Replace Profile Copying)

```python
# ── One-time login (interactive) ──
async def save_login_state(provider_url: str, state_file: str):
    """Open browser for manual login, save cookies/storage."""
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(provider_url)
    input("Log in manually, then press Enter...")
    await context.storage_state(path=state_file)  # Saves cookies + localStorage
    await browser.close()

# ── Subsequent runs (headless, instant) ──
async def create_authenticated_context(state_file: str):
    """Reuse saved login state — no profile copy, no temp dirs."""
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(storage_state=state_file)
    return browser, context
```

**v1 pain point solved:** SeleniumBase copied the user's entire Chrome profile (~500MB) to a temp directory on every launch, causing slow startup, disk bloat, and stale-profile crashes. Playwright's `storage_state` saves only cookies and localStorage (~10KB JSON file).

---

## 3. Core Abstractions (v2)

### 3.1 Base Agent ABC

```python
# src/universal_agents/core/base_agent.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from .types import Message, ConversationTurn, AgentStats
from .config import BaseConfig
from .history import ConversationHistory

class BaseChatAgent(ABC):
    """Abstract base class all chat agents must implement."""

    def __init__(self, config: BaseConfig):
        self.config = config
        self.history = ConversationHistory(max_turns=config.max_history_turns)
        self.session_id: str = str(uuid4())

    @abstractmethod
    async def chat(self, message: str, **kwargs) -> str:
        """Send a message and return the response."""
        ...

    def get_history(self) -> List[Message]:
        return self.history.messages

    def get_turns(self) -> List[ConversationTurn]:
        return self.history.turns

    def clear_history(self) -> None:
        self.history.clear()

    def get_stats(self) -> AgentStats:
        return AgentStats(
            session_id=self.session_id,
            provider=self.config.provider_name,
            total_turns=len(self.history.turns),
        )

    async def close(self) -> None:
        """Release resources. Override in subclasses."""
        pass

    # Context manager support
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
```

### 3.2 Base Browser Agent

```python
# src/universal_agents/browser/base_browser_agent.py

from ..core.base_agent import BaseChatAgent
from .browser_manager import BrowserManager
from .response_detector import ResponseDetector
from .selectors import ProviderSelectors

class BaseBrowserAgent(BaseChatAgent):
    """Shared logic for all browser-automated agents."""

    # Subclasses set this
    SELECTORS: ProviderSelectors  

    def __init__(self, config):
        super().__init__(config)
        self.browser_mgr = BrowserManager(config)
        self.detector = ResponseDetector(config)

    async def chat(self, message: str, **kwargs) -> str:
        page = await self.browser_mgr.ensure_page()

        # 1. Enter text
        input_el = page.locator(self.SELECTORS.input).first
        await input_el.fill(message)

        # 2. Count existing responses
        count_before = await page.locator(self.SELECTORS.response).count()

        # 3. Submit
        await page.locator(self.SELECTORS.submit).first.click()

        # 4. Wait for new response
        response_text = await self.detector.wait_for_new_response(
            page, self.SELECTORS.response, count_before
        )

        # 5. Optional: extract thinking
        thinking = await self._extract_thinking(page)

        # 6. Record turn
        self.history.add_turn(message, response_text, thinking=thinking)
        return response_text

    async def _extract_thinking(self, page) -> Optional[str]:
        """Override in providers that support thinking (Claude)."""
        return None

    async def close(self):
        await self.browser_mgr.close()
```

**Result:** Each provider's chat agent becomes ~50-80 lines (selectors + overrides) instead of 600-1500 lines.

### 3.3 Provider Selector Registry

```python
# src/universal_agents/browser/selectors.py

from dataclasses import dataclass

@dataclass(frozen=True)
class ProviderSelectors:
    """CSS selectors for a provider's web UI."""
    input: str          # Text input element
    submit: str         # Submit button
    response: str       # Response container(s)
    loading: str = ""   # Loading indicator (optional)
    new_chat: str = ""  # New chat button (optional)


# src/universal_agents/providers/claude/selectors.py

from ...browser.selectors import ProviderSelectors

CLAUDE_SELECTORS = ProviderSelectors(
    input="div.ProseMirror[contenteditable='true']",
    submit="button[aria-label='Send message'], button[type='submit']",
    response="div[data-is-streaming] .markdown, .font-claude-message .markdown",
    loading="div[data-is-streaming='true']",
    new_chat="a[href='/new'], button:has-text('New chat')",
)
```

### 3.4 Provider Chat Agent (Example: Claude)

```python
# src/universal_agents/providers/claude/chat.py

from ...browser.base_browser_agent import BaseBrowserAgent
from .selectors import CLAUDE_SELECTORS
from .config import ClaudeConfig

class ClaudeChatAgent(BaseBrowserAgent):
    """Claude browser agent — only provider-specific overrides."""

    SELECTORS = CLAUDE_SELECTORS

    def __init__(self, config: ClaudeConfig = None):
        super().__init__(config or ClaudeConfig())

    async def _extract_thinking(self, page) -> Optional[str]:
        """Claude-specific: extract thinking from intercepted API responses."""
        captured = self.browser_mgr.get_captured_responses()
        for resp in reversed(captured):
            if thinking := _parse_thinking_blocks(resp):
                return thinking
        return None
```

**~30 lines** replaces **1,548 lines** in v1.

### 3.5 Shared Config

```python
# src/universal_agents/core/config.py

from dataclasses import dataclass, field
import os

@dataclass
class BaseConfig:
    provider_name: str = ""
    max_history_turns: int = 50
    max_retries: int = 3
    retry_delay: float = 2.0
    timeout: int = 180

@dataclass
class BrowserConfig(BaseConfig):
    base_url: str = ""
    headless: bool = True
    storage_state: str = ""          # Path to Playwright storage state JSON
    viewport_width: int = 1920
    viewport_height: int = 1080

@dataclass
class APIConfig(BaseConfig):
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False

# Per-provider configs just set defaults:
# src/universal_agents/providers/claude/config.py

@dataclass
class ClaudeConfig(BrowserConfig):
    provider_name: str = "claude"
    base_url: str = "https://claude.ai/new"
    storage_state: str = field(
        default_factory=lambda: os.getenv("CLAUDE_STORAGE_STATE", "")
    )
```

---

## 4. Multi-Agent Monitoring System

### 4.1 Design Goals

1. **Register** any number of agents (same or different providers) in a single session
2. **Track** each agent's status, turn count, errors, and timing in real-time
3. **Observe** agents via an event bus — no tight coupling
4. **Report** on runs with cost, latency, and error summaries
5. **Dashboard** with a terminal UI (via `rich`) showing live agent status

### 4.2 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentRegistry                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Claude#1 │  │ Gemini#1 │  │ GPT#1    │  │ OR#1     │   │
│  │ (chat)   │  │ (chat)   │  │ (data)   │  │ (chat)   │   │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘   │
│        │              │              │              │        │
│        └──────────────┴──────────────┴──────────────┘        │
│                              │                               │
│                         EventBus                             │
│                              │                               │
│              ┌───────────────┼───────────────┐               │
│              ▼               ▼               ▼               │
│        ┌──────────┐   ┌──────────┐   ┌──────────┐          │
│        │ Dashboard │   │ Reporter │   │ Logger   │          │
│        │ (rich)    │   │ (summary)│   │ (file)   │          │
│        └──────────┘   └──────────┘   └──────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Core Components

```python
# src/universal_agents/monitor/events.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from datetime import datetime

class EventType(Enum):
    AGENT_REGISTERED = "agent_registered"
    AGENT_STARTED = "agent_started"
    TURN_STARTED = "turn_started"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    AGENT_ERROR = "agent_error"
    AGENT_CLOSED = "agent_closed"

@dataclass
class AgentEvent:
    event_type: EventType
    agent_id: str
    provider: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: dict = field(default_factory=dict)  # latency_ms, error, turn_number, etc.

class EventBus:
    """Publish/subscribe event bus for agent monitoring."""

    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[AgentEvent], None]):
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event: AgentEvent):
        for handler in self._subscribers.get(event.event_type, []):
            handler(event)
```

```python
# src/universal_agents/monitor/agent_registry.py

from ..core.base_agent import BaseChatAgent
from .events import EventBus, EventType, AgentEvent

class AgentRegistry:
    """Central registry for managing multiple agents."""

    def __init__(self):
        self.agents: dict[str, BaseChatAgent] = {}
        self.event_bus = EventBus()

    def register(self, agent: BaseChatAgent) -> str:
        """Register an agent and return its ID."""
        agent_id = agent.session_id
        self.agents[agent_id] = agent
        self.event_bus.publish(AgentEvent(
            event_type=EventType.AGENT_REGISTERED,
            agent_id=agent_id,
            provider=agent.config.provider_name,
        ))
        return agent_id

    def get(self, agent_id: str) -> BaseChatAgent:
        return self.agents[agent_id]

    def list_agents(self) -> list[dict]:
        return [
            {"id": aid, "provider": a.config.provider_name, "turns": len(a.get_turns())}
            for aid, a in self.agents.items()
        ]

    async def close_all(self):
        for agent in self.agents.values():
            await agent.close()
        self.agents.clear()
```

### 4.4 Monitored Agent Wrapper

```python
# Wraps any agent to emit events on every action

class MonitoredAgent:
    """Decorator that emits events for every chat turn."""

    def __init__(self, agent: BaseChatAgent, event_bus: EventBus):
        self._agent = agent
        self._bus = event_bus
        self._turn_count = 0

    async def chat(self, message: str, **kwargs) -> str:
        self._turn_count += 1
        self._bus.publish(AgentEvent(
            event_type=EventType.TURN_STARTED,
            agent_id=self._agent.session_id,
            provider=self._agent.config.provider_name,
            data={"turn": self._turn_count, "message_preview": message[:80]},
        ))
        start = time.monotonic()
        try:
            response = await self._agent.chat(message, **kwargs)
            elapsed_ms = (time.monotonic() - start) * 1000
            self._bus.publish(AgentEvent(
                event_type=EventType.TURN_COMPLETED,
                agent_id=self._agent.session_id,
                provider=self._agent.config.provider_name,
                data={"turn": self._turn_count, "latency_ms": elapsed_ms},
            ))
            return response
        except Exception as e:
            self._bus.publish(AgentEvent(
                event_type=EventType.TURN_FAILED,
                agent_id=self._agent.session_id,
                provider=self._agent.config.provider_name,
                data={"turn": self._turn_count, "error": str(e)},
            ))
            raise
```

### 4.5 Terminal Dashboard

```python
# src/universal_agents/monitor/dashboard.py

from rich.live import Live
from rich.table import Table
from rich.console import Console

class Dashboard:
    """Live terminal dashboard showing agent status."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self._events: list[AgentEvent] = []
        # Subscribe to all events
        for et in EventType:
            registry.event_bus.subscribe(et, self._on_event)

    def _on_event(self, event: AgentEvent):
        self._events.append(event)

    def _build_table(self) -> Table:
        table = Table(title="Universal Agents Monitor")
        table.add_column("Agent ID", style="cyan", max_width=12)
        table.add_column("Provider", style="green")
        table.add_column("Status", style="bold")
        table.add_column("Turns", justify="right")
        table.add_column("Last Latency", justify="right")
        table.add_column("Errors", justify="right", style="red")

        for agent_id, agent in self.registry.agents.items():
            status = self._get_status(agent_id)
            stats = agent.get_stats()
            table.add_row(
                agent_id[:12],
                agent.config.provider_name,
                status,
                str(stats.total_turns),
                f"{self._last_latency(agent_id):.0f}ms",
                str(self._error_count(agent_id)),
            )
        return table

    async def run(self):
        """Launch live-updating dashboard."""
        with Live(self._build_table(), refresh_per_second=2) as live:
            while True:
                live.update(self._build_table())
                await asyncio.sleep(0.5)
```

### 4.6 Usage Example

```python
import asyncio
from universal_agents.providers.claude.chat import ClaudeChatAgent
from universal_agents.providers.openrouter.chat import OpenRouterChatAgent
from universal_agents.monitor.agent_registry import AgentRegistry

async def main():
    registry = AgentRegistry()

    # Register multiple agents
    claude = ClaudeChatAgent()
    openrouter = OpenRouterChatAgent()
    registry.register(claude)
    registry.register(openrouter)

    # Run agents concurrently
    tasks = [
        claude.chat("Explain quantum computing"),
        openrouter.chat("Explain quantum computing"),
    ]
    results = await asyncio.gather(*tasks)

    # Print comparative results
    for agent_id, result in zip(registry.agents, results):
        agent = registry.get(agent_id)
        print(f"[{agent.config.provider_name}] {result[:200]}...")

    # Print summary
    for info in registry.list_agents():
        print(info)

    await registry.close_all()

asyncio.run(main())
```

---

## 5. Implementation Phases

### Phase 1: Foundation (Core + Playwright Browser Layer)

**Goal:** Working `BaseChatAgent` ABC, Playwright browser manager, one provider (Claude) fully migrated.

| Task | Deliverable | Depends On |
|------|-------------|------------|
| 1.1 Create `pyproject.toml` with dependencies | Installable package with `playwright`, `httpx`, `rich`, `pyyaml` | — |
| 1.2 Implement `core/types.py` | `Message`, `ConversationTurn`, `TurnResult`, `AgentStats` dataclasses | — |
| 1.3 Implement `core/config.py` | `BaseConfig`, `BrowserConfig`, `APIConfig` with env var loading | — |
| 1.4 Implement `core/history.py` | `ConversationHistory` class with max-turn truncation | 1.2 |
| 1.5 Implement `core/base_agent.py` | `BaseChatAgent` ABC with `chat()`, `get_history()`, `close()` | 1.2, 1.3, 1.4 |
| 1.6 Implement `core/exceptions.py` | `AgentError`, `BrowserError`, `APIError` hierarchy | — |
| 1.7 Implement `core/retry.py` | `@retry` decorator with exponential backoff | 1.6 |
| 1.8 Implement `core/output.py` | `save_turn()`, `save_summary()`, `save_full_results()` | 1.2 |
| 1.9 Implement `browser/browser_manager.py` | Playwright lifecycle: launch, stealth, storage state, close | 1.3 |
| 1.10 Implement `browser/selectors.py` | `ProviderSelectors` dataclass | — |
| 1.11 Implement `browser/response_detector.py` | `wait_for_new_response()` with stability checks | 1.10 |
| 1.12 Implement `browser/dom.py` | `find_input()`, `type_text()`, `click_submit()` | 1.10 |
| 1.13 Extract `browser/js/fetch_override.js` | Single file from v1 inline JS | — |
| 1.14 Extract `browser/js/thinking_extractor.js` | Single file from v1 inline JS | — |
| 1.15 Implement `browser/base_browser_agent.py` | Shared browser `chat()` loop | 1.5, 1.9-1.14 |
| 1.16 Implement `providers/claude/` | `ClaudeChatAgent`, `ClaudeConfig`, `CLAUDE_SELECTORS` | 1.15 |
| 1.17 Write unit tests for core + browser | `tests/unit/test_*.py` with mocked Playwright page | 1.1-1.16 |
| 1.18 Write integration test for Claude | `tests/integration/test_claude_chat.py` | 1.16 |

**Exit criteria:** `ClaudeChatAgent` passes multi-turn conversation test against live Claude.ai.

### Phase 2: Remaining Providers

**Goal:** All v1 agents ported to v2. No new features — functional parity.

| Task | Deliverable | Depends On |
|------|-------------|------------|
| 2.1 Port Gemini chat + data agents | `providers/gemini/` | Phase 1 |
| 2.2 Port GPT chat agent | `providers/gpt/` | Phase 1 |
| 2.3 Port Perplexity chat agent | `providers/pplx/` | Phase 1 |
| 2.4 Implement `api/base_api_agent.py` | Shared HTTP chat loop with streaming | 1.5 |
| 2.5 Port OpenRouter chat + data agents | `providers/openrouter/` | 2.4 |
| 2.6 Implement `cli/base_cli_agent.py` | Shared subprocess wrapper | 1.5 |
| 2.7 Port Copilot agent | `providers/copilot/` | 2.6 |
| 2.8 Port Claude data agent | `providers/claude/data.py` | Phase 1 |
| 2.9 Port Claude translator agent | `providers/claude/translator.py` | 2.8 |
| 2.10 Integration tests for each provider | `tests/integration/test_*.py` | 2.1-2.9 |

**Exit criteria:** Every v1 agent has a v2 equivalent that passes its original integration test.

### Phase 3: Monitor + Dashboard

**Goal:** Full multi-agent monitoring, terminal dashboard, run reports.

| Task | Deliverable | Depends On |
|------|-------------|------------|
| 3.1 Implement `monitor/events.py` | `EventType`, `AgentEvent`, `EventBus` | — |
| 3.2 Implement `monitor/agent_registry.py` | `AgentRegistry` with register/list/close_all | 3.1 |
| 3.3 Implement `MonitoredAgent` wrapper | Events emitted on every chat turn | 3.1 |
| 3.4 Implement `monitor/dashboard.py` | `rich` live table showing agent status | 3.2, 3.3 |
| 3.5 Implement `monitor/reporter.py` | Post-run reports: cost, latency, errors | 3.1 |
| 3.6 Add monitor integration tests | Multi-agent concurrent runs with dashboard | 3.4, 3.5 |

**Exit criteria:** Run 3+ agents concurrently, observe live dashboard, export run report.

### Phase 4: Polish + Migration Support

**Goal:** Documentation, examples, v1 migration guide, CI.

| Task | Deliverable | Depends On |
|------|-------------|------------|
| 4.1 Write `docs/MIGRATION_GUIDE.md` | v1 → v2 mapping for all agents | Phase 2 |
| 4.2 Write `examples/` | `basic_chat.py`, `multi_agent_run.py`, `translation_job.py` | Phase 2, 3 |
| 4.3 Update `docs/API_REFERENCE.md` | Reflect v2 API surface | Phase 2 |
| 4.4 Update `docs/AGENT_STRUCTURE.md` | Reflect v2 directory layout | Phase 1 |
| 4.5 Add GitHub Actions CI | Run unit tests on push, integration behind flag | Phase 2 |
| 4.6 Add `py.typed` marker + type stubs | Mypy/Pyright compatibility | Phase 2 |
| 4.7 Archive v1 code | Move v1 to `archive/v1/` branch or tag | Phase 2 |

---

## 6. Dependency Manifest

```toml
# pyproject.toml

[project]
name = "universal-agents"
version = "2.0.0"
requires-python = ">=3.10"
dependencies = [
    "playwright>=1.40",
    "httpx>=0.25",
    "pyyaml>=6.0",
    "rich>=13.0",
]

[project.optional-dependencies]
stealth = ["playwright-stealth>=1.0"]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.0",
    "mypy>=1.0",
    "ruff>=0.1",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: requires live browser/API (deselect with -m 'not integration')",
]

[tool.ruff]
line-length = 100
target-version = "py310"
```

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Provider UIs change selectors | High | Medium | Isolate selectors in `selectors.py` per provider; selector updates are 1-line fixes |
| `playwright-stealth` stops working | Medium | High | Keep fallback to non-headless mode; monitor stealth repo updates |
| Async migration breaks existing sync callers | Medium | Medium | Provide `asyncio.run()` wrappers or a sync API shim |
| Integration tests flaky on CI | High | Low | Mark integration tests with `@pytest.mark.integration`, run separately |
| Playwright bundled browsers increase install size | Low | Low | ~250MB one-time install; acceptable for dev tooling |
| Storage state tokens expire | Medium | Medium | Add token refresh helper + clear error message when auth fails |

---

## 8. Success Metrics

| Metric | v1 Baseline | v2 Target |
|--------|-------------|-----------|
| Total Python source lines | ~25,000 | <10,000 |
| Total files | ~200+ | <80 |
| Lines to add a new browser provider | ~800-1500 (full agent) | ~50-80 (config + selectors) |
| Browser startup time | 5-8s | 1-2s |
| Temp disk usage per session | ~500MB (profile copy) | ~10KB (storage state) |
| Can run agents concurrently? | No (blocking Selenium) | Yes (async Playwright) |
| Live monitoring dashboard? | No | Yes |
| CI-runnable unit tests? | 0 | 100% of unit tests |
| Time to install from zero | Manual dep hunting | `pip install -e .` + `playwright install` |
