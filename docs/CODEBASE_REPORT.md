# Universal Agents v2 — System Report

**Generated:** 2026-03-31  
**Version:** 2.0.0  
**Python:** >=3.10  
**Total source lines:** 7,127 (src/) + 10,743 (tests/) = 17,870  
**Files:** 78 source + 55 test = 133 non-boilerplate files  

---

## 0. Report Guideline

### When to Update

| Code Change                           | Sections to Update                                                    |
| ------------------------------------- | --------------------------------------------------------------------- |
| New source file                       | 1 (Directory Tree), 7 (Key Files if important)                        |
| New class or method on core module    | 2 (Core Components)                                                   |
| New provider added                    | 1 (Tree), 2 (Components), 3 (Abstractions), 4 (Config), 7 (Key Files) |
| Config parameter added/changed        | 4 (Parameters and Configuration)                                      |
| New process flow or changed chat loop | 5 (Process Flows)                                                     |
| New/changed tests                     | 6 (Verification and Quality)                                          |
| New environment variable              | 4 (Environment Variables)                                             |
| New dependency                        | 4 (Dependency Versions)                                               |
| New example or doc                    | 1 (Tree)                                                              |

### How to Update

| Section             | Trigger                                    | Action                                |
| ------------------- | ------------------------------------------ | ------------------------------------- |
| 0. Report Guideline | Report conventions change                  | Edit this section                     |
| 1. Codebase Mapping | File added/removed/moved                   | Update directory tree + annotations   |
| 2. Core Components  | Class/method signature changes             | Update method tables, attribute lists |
| 3. Key Abstractions | New provider type, new domain concept      | Add or modify abstraction docs        |
| 4. Parameters       | Config field added/removed/default changed | Update relevant config table          |
| 5. Process Flows    | Control flow or data flow changes          | Redraw affected diagrams              |
| 6. Verification     | Tests added, CI changed                    | Update counts, frameworks, pass rates |
| 7. Key Files        | Core file added or purpose changed         | Update quick-reference table          |

### Style Guidelines

- **Diagrams:** ASCII box art only (`┌─┐│└─┘───►`). No Mermaid/PlantUML.
- **Tables:** Markdown pipe-delimited. Align types/descriptions.
- **Code:** Fenced blocks with language hints (` ```python `).
- **File references:** Relative paths from repo root (e.g., `src/universal_agents/core/base_agent.py`).
- **Identifiers:** Always use exact class/method/variable names from source.

---

## 1. Codebase Mapping

```
universal-agent_v2/
│
├── pyproject.toml                  # Project metadata, deps, build config (hatchling)
├── docs/                           # ══════ DOCUMENTATION ══════
│   ├── MIGRATION_GUIDE.md          # v1 → v2 migration guide for all agents
│   ├── API_REFERENCE.md            # Full API surface reference
│   ├── AGENT_STRUCTURE.md          # Directory layout + inheritance diagrams
│   ├── agent_compiler_plan.md      # Compiler design doc (Compiler-LLM, question flow, 20 examples)
│   ├── dev_log_1.md … dev_log_5.md # Development logs with problems/solutions
│
├── examples/                       # ══════ USAGE EXAMPLES ══════
│   ├── basic_chat.py               # Single agent chat (27 lines)
│   ├── multi_agent_run.py          # Concurrent agents with monitoring (59 lines)
│   └── translation_job.py          # Multi-turn translation with progress (75 lines)
│
├── .github/workflows/ci.yml       # GitHub Actions: unit tests on push, integration on dispatch
│
├── src/universal_agents/           # ══════ MAIN PACKAGE ══════
│   ├── __init__.py                 # Top-level exports (BaseChatAgent, all configs, types)
│   ├── py.typed                    # PEP 561 type marker
│   │
│   ├── core/                       # ── SHARED ABSTRACTIONS ──
│   │   ├── __init__.py
│   │   ├── base_agent.py           # BaseChatAgent ABC (53 lines)
│   │   ├── config.py               # BaseConfig, BrowserConfig, APIConfig, CLIConfig (67 lines)
│   │   ├── types.py                # Message, ConversationTurn, TurnResult, AgentStats (81 lines)
│   │   ├── exceptions.py           # AgentError hierarchy — Browser/API/CLI errors (41 lines)
│   │   ├── history.py              # ConversationHistory with sliding window (70 lines)
│   │   ├── retry.py                # @retry decorator with exponential backoff (51 lines)
│   │   ├── output.py               # save_turn, save_summary, save_full_results (123 lines)
│   │   ├── json_utils.py           # JSON extraction from LLM responses (37 lines)
│   │   ├── prompt_builder.py       # System prompt builder (26 lines)
│   │   ├── srt_utils.py            # SRT parsing, chunking, overlap, normalization (259 lines)
│   │   ├── translation_prompts.py  # Translation prompt templates (130 lines)
│   │   └── kendo_context.py        # Kendo dictionary loader + SRT prompts (122 lines)
│   │
│   ├── browser/                    # ── BROWSER AUTOMATION LAYER ──
│   │   ├── __init__.py
│   │   ├── base_browser_agent.py   # BaseBrowserAgent — shared DOM chat loop + _send_message hook (130 lines)
│   │   ├── browser_manager.py      # Camoufox/Playwright lifecycle, stealth, storage_state (270 lines)
│   │   ├── response_detector.py    # 2-phase response detection (count + stability) (109 lines)
│   │   ├── dom.py                  # find_element, type_text, click_submit (90 lines)
│   │   ├── selectors.py            # ProviderSelectors frozen dataclass (22 lines)
│   │   └── js/                     # Injectable JavaScript for browser agents
│   │       ├── fetch_override.js       # Claude API fetch interceptor (87 lines)
│   │       ├── gemini_fetch_override.js # Gemini API fetch interceptor (58 lines)
│   │       └── thinking_extractor.js   # React state BFS for thinking blocks (125 lines)
│   │
│   ├── api/                        # ── HTTP API LAYER ──
│   │   ├── __init__.py
│   │   └── base_api_agent.py       # BaseAPIAgent — httpx sync/stream, retry (222 lines)
│   │
│   ├── cli/                        # ── CLI SUBPROCESS LAYER ──
│   │   ├── __init__.py
│   │   └── base_cli_agent.py       # BaseCLIAgent — asyncio.subprocess (110 lines)
│   │
│   ├── compiler/                   # ══════ AGENT COMPILER ══════
│   │   ├── __init__.py             # Package exports (28 lines)
│   │   ├── __main__.py             # CLI entry point: `python -m universal_agents.compiler` (82 lines)
│   │   ├── requirements.py         # UserRequirements dataclass (58 lines)
│   │   ├── question_flow.py        # Interview questions + presets (439 lines)
│   │   ├── auth_detector.py        # Detect available auth (API keys, storage states) (173 lines)
│   │   ├── capability_resolver.py  # Map (provider, use_case) → components (195 lines)
│   │   ├── config_builder.py       # Build config kwargs from resolved components (145 lines)
│   │   ├── agent_assembler.py      # Assemble CompiledAgent + generate scripts (212 lines)
│   │   ├── agent_packager.py       # Self-contained package creator (248 lines)
│   │   ├── compiler_llm.py         # Compiler-LLM for Custom option interpretation (192 lines)
│   │   └── compiler.py             # Top-level orchestrator (91 lines)
│   │
│   ├── providers/                  # ══════ PROVIDER IMPLEMENTATIONS ══════
│   │   ├── __init__.py
│   │   ├── claude/                 # ── CLAUDE (BROWSER + DATA + TRANSLATOR) ──
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # ClaudeConfig → ClaudeDataConfig → ClaudeTranslatorConfig (39 lines)
│   │   │   ├── selectors.py        # CLAUDE_SELECTORS — 10 input, 7 submit, 9 response (45 lines)
│   │   │   ├── chat.py             # ClaudeChatAgent — 3-strategy thinking extraction (100 lines)
│   │   │   ├── data.py             # ClaudeDataAgent — JSON prompt/extraction + clipboard paste (150 lines)
│   │   │   └── translator.py       # ClaudeTranslatorAgent — multi-turn + file upload (399 lines)
│   │   │
│   │   ├── gemini/                 # ── GEMINI (BROWSER + DATA + TRANSLATOR) ──
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # GeminiConfig, GeminiTranslatorConfig (22 lines)
│   │   │   ├── selectors.py        # GEMINI_SELECTORS (51 lines)
│   │   │   ├── chat.py             # GeminiChatAgent — API interception thinking (82 lines)
│   │   │   ├── data.py             # GeminiDataAgent — JSON prompt/extraction + file upload (236 lines)
│   │   │   └── translator.py       # GeminiTranslatorAgent — model selection, rate limits, progress (723 lines)
│   │   │
│   │   ├── gpt/                    # ── GPT (BROWSER) ──
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # GPTConfig (17 lines)
│   │   │   ├── selectors.py        # GPT_SELECTORS (38 lines)
│   │   │   └── chat.py             # GPTChatAgent — minimal browser agent (20 lines)
│   │   │
│   │   ├── pplx/                   # ── PERPLEXITY (BROWSER + CITATIONS) ──
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # PerplexityConfig (18 lines)
│   │   │   ├── selectors.py        # PPLX_SELECTORS + CITATION_SELECTORS (49 lines)
│   │   │   └── chat.py             # PerplexityChatAgent — citation extraction (133 lines)
│   │   │
│   │   ├── openrouter/             # ── OPENROUTER (HTTP API) ──
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # OpenRouterConfig, OpenRouterDataConfig (48 lines)
│   │   │   ├── chat.py             # OpenRouterChatAgent — model fallback (57 lines)
│   │   │   └── data.py             # OpenRouterDataAgent — thinking budget (110 lines)
│   │   │
│   │   ├── openai/                 # ── OPENAI (HTTP API) ──
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # OpenAIConfig (31 lines)
│   │   │   ├── chat.py             # OpenAIChatAgent (31 lines)
│   │   │   └── data.py             # OpenAIDataAgent — extended thinking (80 lines)
│   │   │
│   │   └── copilot/                # ── COPILOT (CLI) ──
│   │       ├── __init__.py
│   │       ├── config.py           # CopilotConfig (19 lines)
│   │       └── chat.py             # CopilotChatAgent — gh copilot CLI (47 lines)
│   │
│   └── monitor/                    # ══════ MULTI-AGENT MONITORING ══════
│       ├── __init__.py             # Package exports (16 lines)
│       ├── events.py               # EventType, AgentEvent, EventBus (44 lines)
│       ├── agent_registry.py       # AgentRegistry — register/get/list/close_all (46 lines)
│       ├── monitored_agent.py      # MonitoredAgent — event-emitting wrapper (83 lines)
│       ├── dashboard.py            # Dashboard — rich Live terminal UI (89 lines)
│       └── reporter.py             # Reporter — post-run report generation (133 lines)
│
├── tests/                          # ══════ TEST SUITE ══════
│   ├── conftest.py                 # Shared fixtures
│   ├── __init__.py
│   ├── mocks/
│   │   └── __init__.py
│   ├── unit/                       # 501 unit tests (29 files)
│   │   ├── test_types.py           # Message, Turn, Stats dataclass tests
│   │   ├── test_config.py          # Config inheritance + defaults
│   │   ├── test_history.py         # Sliding window, turn numbering
│   │   ├── test_output.py          # File saving (JSON/TXT/MD)
│   │   ├── test_retry.py           # Exponential backoff behavior
│   │   ├── test_selectors.py       # Frozen dataclass + optional fields
│   │   ├── test_response_detector.py # 2-phase detection + timeout
│   │   ├── test_base_api_agent.py  # HTTP sync/stream, rate limit
│   │   ├── test_base_cli_agent.py  # Subprocess mock
│   │   ├── test_browser_providers.py # All browser agent selectors/init
│   │   ├── test_openrouter.py      # API fallback, headers, thinking
│   │   ├── test_perplexity.py      # Citation parsing
│   │   ├── test_copilot.py         # CLI command building
│   │   ├── test_claude_data.py     # JSON prompt/extraction
│   │   ├── test_translator.py      # Translation chunks, progress, line tracking, kendo context
│   │   ├── test_events.py          # EventBus pub/sub
│   │   ├── test_agent_registry.py  # Register/get/close
│   │   ├── test_monitored_agent.py # Event emission on chat
│   │   ├── test_dashboard.py       # Status tracking, table building
│   │   ├── test_reporter.py        # Report generation + JSON export
│   │   ├── test_monitor_integration.py # Multi-agent concurrent scenarios
│   │   ├── test_shared_utils.py    # JSON utils, prompt builder
│   │   ├── test_srt_utils.py       # SRT parsing, chunking, overlap, normalization (38 tests)
│   │   ├── test_translation_prompts.py # Translation prompt templates
│   │   ├── test_auth_detector.py   # Auth detection (API keys, storage states)
│   │   ├── test_compiler_phase2.py # Capability resolver, config builder
│   │   ├── test_compiler_phase3.py # Question flow, AgentCompiler, CLI
│   │   ├── test_compiler_integration.py # End-to-end compiler pipeline
│   │   ├── test_compiler_llm.py    # CompilerLLM Custom-option interpretation
│   │   ├── test_agent_packager.py  # Self-contained packaging (21 tests)
│   │   ├── test_send_message.py    # _send_message hook: Base, Gemini upload, Claude paste (15 tests)
│   │   └── test_v1_claude_jobs.py  # V1 ported test cases
│   └── integration/
│       ├── test_claude_chat.py         # Live browser test (requires Playwright + auth)
│       ├── test_v1_claude_jobs_live.py # 10 E2E tests with full trace capture
│       ├── test_gemini_live.py         # 10 Gemini tests (chat, data, translator, model change)
│       ├── test_gemini_srt_translation.py # Gemini SRT translation integration test
│       ├── run_srt_translation.py      # Production kendo SRT batch translation runner
│       ├── test_openrouter_live.py     # OpenRouter 10-test suite
│       ├── test_openai_live.py         # OpenAI 6-test suite
│       ├── test_camoufox.py            # Camoufox headless verification
│       ├── diagnose_headless.py        # Headless diagnostic tool
│       └── fixtures/                   # Test PDFs and fixture generators
│
└── _references/                    # ══════ REFERENCE MATERIAL ══════
    └── universal-agent_v1/         # Complete v1 codebase for reference
```

### Files to Archive

| File                              | Reason                                            | Recommended Action                               |
| --------------------------------- | ------------------------------------------------- | ------------------------------------------------ |
| `_references/universal-agent_v1/` | Reference material from v1, not needed at runtime | Move to separate branch or tag when v2 is stable |
| `universal-agents-v2_plan.md`     | Implementation plan — fulfilled                   | Archive alongside v1 reference                   |

---

## 2. Core Components (Detailed)

### BaseChatAgent (`src/universal_agents/core/base_agent.py` — 53 lines)

Abstract base class all agents must implement. Provides history management, statistics, and async context manager.

| Method          | Description                                   | Parameters               | Returns                  |
| --------------- | --------------------------------------------- | ------------------------ | ------------------------ |
| `__init__`      | Initialize with config, history, session UUID | `config: BaseConfig`     | —                        |
| `chat`          | Send message and get response *(abstract)*    | `message: str, **kwargs` | `str`                    |
| `get_history`   | All messages in session                       | —                        | `list[Message]`          |
| `get_turns`     | All user↔assistant turns                      | —                        | `list[ConversationTurn]` |
| `get_stats`     | Session statistics                            | —                        | `AgentStats`             |
| `clear_history` | Reset conversation                            | —                        | `None`                   |
| `close`         | Release resources (override in subclasses)    | —                        | `None`                   |

**Key Attributes:** `config: BaseConfig`, `history: ConversationHistory`, `session_id: str`  
**Dependencies:** `config.py`, `history.py`, `types.py`

---

### BaseBrowserAgent (`src/universal_agents/browser/base_browser_agent.py` — 130 lines)

Shared browser chat loop: launch → navigate → send message → submit → wait → extract.

| Method              | Description                                       | Parameters               | Returns       |
| ------------------- | ------------------------------------------------- | ------------------------ | ------------- |
| `chat`              | Full DOM interaction cycle                        | `message: str, **kwargs` | `str`         |
| `_ensure_ready`     | Launch browser + navigate if first call           | —                        | `Page`        |
| `_send_message`     | Send message to input (override for upload/paste) | `page, message: str`     | `None`        |
| `_pre_chat_hook`    | Override for pre-turn setup                       | `page: Page`             | `None`        |
| `_post_navigate`    | Override for post-nav JS injection                | `page: Page`             | `None`        |
| `_extract_thinking` | Override for thinking extraction                  | `page: Page`             | `str \| None` |
| `close`             | Close browser manager                             | —                        | `None`        |

**Key Attributes:** `SELECTORS: ProviderSelectors` (class var), `LONG_MESSAGE_WORD_THRESHOLD: int` (100), `browser_mgr: BrowserManager`, `browser_config: BrowserConfig`  
**Overrides:** `GeminiDataAgent._send_message` (file upload, threshold=100), `ClaudeDataAgent._send_message` (clipboard paste, threshold=1000)

---

### BrowserManager (`src/universal_agents/browser/browser_manager.py` — 187 lines)

Manages Playwright browser lifecycle with stealth, anti-detection, and storage state.

| Method                   | Description                             | Parameters      | Returns      |
| ------------------------ | --------------------------------------- | --------------- | ------------ |
| `ensure_page`            | Get or create browser page              | —               | `Page`       |
| `navigate`               | Navigate + handle Cloudflare challenges | `url: str`      | `None`       |
| `inject_js`              | Inject JS file from `js/` directory     | `filename: str` | `None`       |
| `save_storage_state`     | Export auth cookies/storage             | `path: str`     | `None`       |
| `get_captured_responses` | Get intercepted API responses           | —               | `list[dict]` |
| `close`                  | Close browser + playwright              | —               | `None`       |

**Key Attributes:** `_playwright`, `_browser`, `_context`, `_page`, `_captured_responses: list[dict]`  
**Dependencies:** `playwright.async_api`, optional `playwright_stealth`

---

### ResponseDetector (`src/universal_agents/browser/response_detector.py` — 109 lines)

Two-phase response detection: (1) element count increase, (2) content stabilization via N consecutive identical reads.

| Method                  | Description                             | Parameters                               | Returns |
| ----------------------- | --------------------------------------- | ---------------------------------------- | ------- |
| `wait_for_new_response` | Block until new stable response appears | `page, response_selectors, count_before` | `str`   |
| `count_responses`       | Count visible response elements         | `page, response_selectors`               | `int`   |

**Key Attributes:** `timeout: int`, `check_interval: float`, `required_stable_checks: int`

---

### BaseAPIAgent (`src/universal_agents/api/base_api_agent.py` — 222 lines)

HTTP API base using `httpx.AsyncClient`. Supports sync and streaming modes.

| Method                | Description                       | Parameters                       | Returns                     |
| --------------------- | --------------------------------- | -------------------------------- | --------------------------- |
| `chat`                | Send message via HTTP API         | `message: str, **kwargs`         | `str`                       |
| `chat_stream`         | Streaming response generator      | `message: str, **kwargs`         | `AsyncGenerator[str, None]` |
| `_build_request_body` | Construct request payload         | `messages: list[dict], **kwargs` | `dict`                      |
| `_parse_response`     | Extract content from response     | `data: dict`                     | `tuple[str, str \| None]`   |
| `_parse_stream_chunk` | Extract content from stream chunk | `data: dict`                     | `str`                       |
| `_make_request`       | HTTP POST with @retry             | `url: str, body: dict`           | `dict`                      |

**Key Attributes:** `api_config: APIConfig`, `_client: httpx.AsyncClient \| None`  
**Dependencies:** `httpx`, `core.retry`

---

### BaseCLIAgent (`src/universal_agents/cli/base_cli_agent.py` — 110 lines)

Async subprocess wrapper for CLI-based agents.

| Method           | Description                          | Parameters               | Returns     |
| ---------------- | ------------------------------------ | ------------------------ | ----------- |
| `chat`           | Execute CLI command with message     | `message: str, **kwargs` | `str`       |
| `_build_command` | Construct CLI args *(abstract-like)* | `**kwargs`               | `list[str]` |
| `_build_prompt`  | Build prompt with history context    | `message: str`           | `str`       |
| `_parse_output`  | Parse CLI stdout                     | `raw_output: str`        | `str`       |

**Key Attributes:** `cli_config: CLIConfig`  
**Dependencies:** `asyncio.create_subprocess_exec`

---

### ConversationHistory (`src/universal_agents/core/history.py` — 70 lines)

Sliding window conversation manager. Uses `_total_turns` counter for correct numbering after truncation.

| Method                     | Description                            | Parameters                                                                      | Returns                |
| -------------------------- | -------------------------------------- | ------------------------------------------------------------------------------- | ---------------------- |
| `add_turn`                 | Record a user↔assistant exchange       | `user_message, assistant_message, thinking, processing_time_ms, success, error` | `ConversationTurn`     |
| `clear`                    | Reset all history                      | —                                                                               | `None`                 |
| `get_messages_for_context` | Get role+content dicts for API context | —                                                                               | `list[dict[str, str]]` |

**Key Attributes:** `max_turns: int`, `_messages: list[Message]`, `_turns: list[ConversationTurn]`, `_total_turns: int`  
**Properties:** `messages`, `turns`, `turn_count` (read-only copies)

---

### EventBus (`src/universal_agents/monitor/events.py` — 44 lines)

Publish/subscribe system for agent monitoring events.

| Method        | Description                   | Parameters                                 | Returns |
| ------------- | ----------------------------- | ------------------------------------------ | ------- |
| `subscribe`   | Register event handler        | `event_type: EventType, handler: Callable` | `None`  |
| `unsubscribe` | Remove event handler          | `event_type: EventType, handler: Callable` | `None`  |
| `publish`     | Dispatch event to subscribers | `event: AgentEvent`                        | `None`  |

**Key Attributes:** `_subscribers: dict[EventType, list[Callable]]`

---

### AgentRegistry (`src/universal_agents/monitor/agent_registry.py` — 46 lines)

Central registry for managing multiple agents in a session.

| Method        | Description                           | Parameters             | Returns         |
| ------------- | ------------------------------------- | ---------------------- | --------------- |
| `register`    | Register agent, emit event, return ID | `agent: BaseChatAgent` | `str`           |
| `get`         | Retrieve agent by ID                  | `agent_id: str`        | `BaseChatAgent` |
| `list_agents` | Summary of all registered agents      | —                      | `list[dict]`    |
| `close_all`   | Close all agents, emit events         | —                      | `None`          |

---

### MonitoredAgent (`src/universal_agents/monitor/monitored_agent.py` — 83 lines)

Decorator wrapping any agent to emit `TURN_STARTED`/`TURN_COMPLETED`/`TURN_FAILED` events.

| Method  | Description                           | Parameters               | Returns |
| ------- | ------------------------------------- | ------------------------ | ------- |
| `chat`  | Delegate to inner agent + emit events | `message: str, **kwargs` | `str`   |
| `close` | Close inner agent + emit AGENT_CLOSED | —                        | `None`  |

**Key Attributes:** `_agent: BaseChatAgent`, `_bus: EventBus`, `_turn_count: int`  
**Delegates:** `get_stats()`, `get_turns()`, `get_history()`, `session_id`, `config`

---

## 3. Key Abstractions and Domain Logic

### Agent Type Hierarchy

Three base agent types correspond to three interaction modes:

```
BaseChatAgent (ABC)
├── BaseBrowserAgent          # Playwright DOM automation
│   ├── ClaudeChatAgent       #   3-strategy thinking extraction
│   ├── ClaudeDataAgent       #   JSON prompt building + extraction
│   ├── GeminiChatAgent       #   API interception thinking
│   ├── GPTChatAgent          #   Minimal (no special features)
│   └── PerplexityChatAgent   #   Citation DOM extraction
├── BaseAPIAgent              # httpx HTTP client
│   ├── OpenRouterChatAgent   #   Model fallback on failure
│   └── OpenRouterDataAgent   #   Thinking budget, JSON extraction
└── BaseCLIAgent              # asyncio.subprocess
    └── CopilotChatAgent      #   gh copilot -I with tool mgmt
```

### Configuration Hierarchy

```
BaseConfig (provider_name, timeout, max_history_turns, max_retries)
├── BrowserConfig (+ base_url, headless, storage_state, viewport,
│   │               response_check_interval, required_stable_checks)
│   ├── ClaudeConfig (+ extract_thinking)
│   │   ├── ClaudeDataConfig (timeout=300)
│   │   │   └── ClaudeTranslatorConfig (timeout=600, translation settings)
│   ├── GeminiConfig (+ extract_thinking, required_model)
│   ├── GPTConfig
│   └── PerplexityConfig (+ extract_citations)
├── APIConfig (+ api_key, model, base_url, temperature, max_tokens, stream)
│   ├── OpenRouterConfig (+ fallback_models, site_url, site_name)
│   │   └── OpenRouterDataConfig (+ enable_thinking, thinking_budget)
└── CLIConfig (+ command, working_dir)
    └── CopilotConfig (+ allow_all_tools, allowed_tools, denied_tools)
```

### Provider Selectors Pattern

Each browser provider defines a `ProviderSelectors` frozen dataclass with ordered CSS selector lists:

```python
ProviderSelectors(
    input_selectors=["primary", "fallback1", "fallback2"],  # Chat input
    submit_selectors=["primary", ...],                       # Submit button
    response_selectors=["primary", ...],                     # Response elements
    loading_selectors=[...],                                 # Loading indicators
    new_chat_selectors=[...],                                # New chat button
)
```

Selectors are tried in order by `dom.find_element()` — first visible match wins. This isolates all provider-specific DOM knowledge into ~50-line `selectors.py` files.

### Thinking Extraction (Claude)

Three strategies tried in order:

1. **Playwright response interception** — `page.on("response")` captures API responses containing `thinking` blocks
2. **Fetch override JS** — Injected `fetch_override.js` monkey-patches `window.fetch` to capture response bodies
3. **React state BFS** — `thinking_extractor.js` traverses React fiber tree to find thinking content in component state

### Citation Extraction (Perplexity)

After each chat response:
1. Locate source elements via `CITATION_SELECTORS`
2. Filter with `_is_citation_text()` regex (URLs, `[1]` patterns, domain names)
3. Parse each into `Citation(text, url, title, year, citation_type)` dataclass

### Translation Orchestration (Claude Translator)

```
┌─────────────┐   chunks   ┌──────────────────┐  translate_text()  ┌─────────────┐
│ Source Text  │───────────►│ TranslationChunk │──────────────────►│ ClaudeData  │
│ / PDF files  │            │ (indexed)        │                   │ Agent (chat) │
└─────────────┘            └──────────────────┘                   └──────┬──────┘
                                    │                                     │
                                    │ should_split?                       │ response
                                    ▼                                     ▼
                           ┌──────────────────┐               ┌─────────────────┐
                           │ start_new_       │               │ TranslationResult│
                           │ conversation()   │               │ (per chunk)      │
                           └──────────────────┘               └────────┬────────┘
                                                                       │
                                                              ┌────────▼────────┐
                                                              │ ProgressState   │
                                                              │ (resume/save)   │
                                                              └─────────────────┘
```

### Monitor Event System

```
EventType enum:
  AGENT_REGISTERED → AgentRegistry.register()
  AGENT_STARTED    → (user code)
  TURN_STARTED     → MonitoredAgent.chat() entry
  TURN_COMPLETED   → MonitoredAgent.chat() success
  TURN_FAILED      → MonitoredAgent.chat() exception
  AGENT_ERROR      → (user code)
  AGENT_CLOSED     → MonitoredAgent.close() / AgentRegistry.close_all()
```

---

## 4. Parameters and Configuration

### Environment Variables

| Variable               | Required?            | Default | Description                                      |
| ---------------------- | -------------------- | ------- | ------------------------------------------------ |
| `CLAUDE_STORAGE_STATE` | No                   | `""`    | Path to Playwright storage state JSON for Claude |
| `GEMINI_STORAGE_STATE` | No                   | `""`    | Path to storage state JSON for Gemini            |
| `GPT_STORAGE_STATE`    | No                   | `""`    | Path to storage state JSON for ChatGPT           |
| `PPLX_STORAGE_STATE`   | No                   | `""`    | Path to storage state JSON for Perplexity        |
| `OPENROUTER_API_KEY`   | Yes (for OpenRouter) | `""`    | OpenRouter API key                               |

### BaseConfig Defaults

| Parameter           | Default | Description                 |
| ------------------- | ------- | --------------------------- |
| `provider_name`     | `""`    | Provider identifier string  |
| `max_history_turns` | `50`    | Sliding window size         |
| `max_retries`       | `3`     | Max retry attempts          |
| `retry_delay`       | `2.0`   | Base retry delay (seconds)  |
| `timeout`           | `180`   | Operation timeout (seconds) |

### BrowserConfig Defaults (extends BaseConfig)

| Parameter                 | Default        | Description                                         |
| ------------------------- | -------------- | --------------------------------------------------- |
| `base_url`                | `""`           | Provider chat URL                                   |
| `headless`                | `True`         | Run browser in headless mode                        |
| `storage_state`           | `""` (env var) | Path to Playwright storage state                    |
| `viewport_width`          | `1920`         | Browser viewport width                              |
| `viewport_height`         | `1080`         | Browser viewport height                             |
| `response_check_interval` | `2.0`          | Polling interval for response detection (seconds)   |
| `required_stable_checks`  | `3`            | Consecutive identical reads before declaring stable |
| `page_load_timeout`       | `30`           | Page load timeout (seconds)                         |

### APIConfig Defaults (extends BaseConfig)

| Parameter           | Default | Description                |
| ------------------- | ------- | -------------------------- |
| `api_key`           | `""`    | API authentication key     |
| `base_url`          | `""`    | API endpoint base URL      |
| `model`             | `""`    | Model identifier           |
| `temperature`       | `0.7`   | Sampling temperature       |
| `max_tokens`        | `4096`  | Max response tokens        |
| `top_p`             | `1.0`   | Nucleus sampling parameter |
| `frequency_penalty` | `0.0`   | Frequency penalty          |
| `presence_penalty`  | `0.0`   | Presence penalty           |
| `stream`            | `False` | Enable streaming responses |
| `system_prompt`     | `""`    | System prompt text         |

### CLIConfig Defaults (extends BaseConfig)

| Parameter     | Default | Description                      |
| ------------- | ------- | -------------------------------- |
| `command`     | `""`    | CLI executable path              |
| `working_dir` | `"."`   | Working directory for subprocess |

### Provider-Specific Config Overrides

| Config Class             | Key Overrides                                                                                                                          |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| `ClaudeConfig`           | `base_url="https://claude.ai/new"`, `extract_thinking=True`                                                                            |
| `ClaudeDataConfig`       | `timeout=300`                                                                                                                          |
| `ClaudeTranslatorConfig` | `timeout=600`, `max_turns_per_conversation=20`, `source_language="ja"`, `target_language="en"`, `chunk_size=2000`, `overlap_chars=100` |
| `GeminiConfig`           | `base_url="https://gemini.google.com"`, `extract_thinking=True`, `required_model=None`                                                 |
| `GPTConfig`              | `base_url="https://chatgpt.com"`                                                                                                       |
| `PerplexityConfig`       | `base_url="https://www.perplexity.ai"`, `extract_citations=True`                                                                       |
| `OpenRouterConfig`       | `base_url="https://openrouter.ai/api/v1"`, `model="anthropic/claude-3-5-sonnet"`, `fallback_models=[]`, `site_url=""`, `site_name=""`  |
| `OpenRouterDataConfig`   | `timeout=600`, `enable_thinking=True`, `thinking_budget=10000`                                                                         |
| `CopilotConfig`          | `command="copilot"`, `allow_all_tools=False`, `allowed_tools=[]`, `denied_tools=[]`                                                    |

### Dependency Versions (`pyproject.toml`)

| Package              | Version Constraint | Purpose                |
| -------------------- | ------------------ | ---------------------- |
| `playwright`         | `>=1.40`           | Browser automation     |
| `httpx`              | `>=0.25`           | Async HTTP client      |
| `pyyaml`             | `>=6.0`            | YAML config parsing    |
| `rich`               | `>=13.0`           | Terminal dashboard UI  |
| `playwright-stealth` | `>=1.0` (optional) | Browser anti-detection |
| `pytest`             | `>=7.0` (dev)      | Testing framework      |
| `pytest-asyncio`     | `>=0.23` (dev)     | Async test support     |
| `pytest-mock`        | `>=3.0` (dev)      | Mock fixtures          |
| `mypy`               | `>=1.0` (dev)      | Type checking          |
| `ruff`               | `>=0.1` (dev)      | Linting                |

---

## 5. Process Flows

### Browser Agent Chat Flow

```
┌──────────────┐
│  user code   │
│  agent.chat  │
│  ("message") │
└──────┬───────┘
       │
       ▼
┌──────────────┐   first call?   ┌────────────────┐
│ _ensure_ready│────────────────►│  BrowserManager │
│              │                 │  ensure_page()  │
└──────┬───────┘                 │  navigate(url)  │
       │                         │  stealth setup  │
       │                         │  storage_state  │
       │                         └────────┬───────┘
       │                                  │ Page
       │◄─────────────────────────────────┘
       ▼
┌──────────────┐                 ┌────────────────────┐
│_pre_chat_hook│────────────────►│ Clear captured      │
│              │                 │ thinking/responses   │
└──────┬───────┘                 └────────────────────┘
       ▼
┌──────────────┐                 ┌────────────────────┐
│_send_message │────────────────►│ Default: type_text  │
│              │                 │ Gemini: file upload  │
└──────┬───────┘                 │ Claude: clipboard   │
       ▼                         │   paste (>threshold) │
                                 └────────────────────┘
┌──────────────┐
│click_submit  │
└──────┬───────┘
       ▼
┌──────────────────┐  Phase 1   ┌────────────────┐
│ ResponseDetector │────────────►│ count increase │
│ wait_for_new_    │             └───────┬────────┘
│ response()       │  Phase 2           ▼
│                  │────────────►┌────────────────┐
└──────┬───────────┘             │ N stable reads │
       │ response text           └────────────────┘
       ▼
┌──────────────────┐
│_extract_thinking │─── Optional: thinking text
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ history.add_turn │─── ConversationTurn recorded
└──────┬───────────┘
       │
       ▼
   return response
```

### API Agent Chat Flow

```
┌──────────┐   message    ┌──────────────┐
│user.chat │─────────────►│ BaseAPIAgent  │
│("query") │              │   .chat()     │
└──────────┘              └───────┬──────┘
                                  │
                                  ▼
                          ┌──────────────────┐
                          │ history.add_turn │ (user message)
                          │ build_messages() │
                          └───────┬──────────┘
                                  │ messages[]
                                  ▼
                          ┌──────────────────┐
                          │_build_request_   │
                          │body(messages)    │
                          └───────┬──────────┘
                                  │ body dict
                  ┌───────────────┼───────────────┐
                  │ stream=False  │               │ stream=True
                  ▼               │               ▼
          ┌──────────────┐       │       ┌──────────────┐
          │ _chat_sync   │       │       │ _chat_stream │
          │ _make_request│       │       │ SSE chunks   │
          │ (with @retry)│       │       └──────┬───────┘
          └──────┬───────┘       │              │
                 │               │              │
                 ▼               │              ▼
          ┌──────────────┐       │       ┌──────────────┐
          │_parse_response│      │       │_parse_stream │
          └──────┬───────┘       │       │_chunk        │
                 │               │       └──────┬───────┘
                 └───────────────┼──────────────┘
                                 │ response text
                                 ▼
                          ┌──────────────────┐
                          │ history.add_turn │ (assistant)
                          └───────┬──────────┘
                                  │
                              return response
```

### Monitor Event Flow

```
┌──────────────┐  register()  ┌───────────────┐  AGENT_REGISTERED  ┌──────────┐
│ AgentRegistry│─────────────►│   EventBus    │───────────────────►│Dashboard │
└──────────────┘              │               │                    │Reporter  │
                              └───────┬───────┘                    └──────────┘
                                      │
                                      │  subscribe/publish
                                      │
┌──────────────┐  chat()      ┌───────┴───────┐
│MonitoredAgent│─────────────►│  TURN_STARTED │──────►  handlers
│   .chat()    │              │  TURN_COMPLETED│──────►  handlers
│              │─ exception ─►│  TURN_FAILED  │──────►  handlers
└──────────────┘              └───────────────┘
```

### CI/CD Flow

```
┌──────────┐   push/PR    ┌──────────────┐   matrix    ┌────────────┐
│ git push │─────────────►│ GitHub       │────────────►│ Python     │
│          │              │ Actions CI   │  3.10/3.11  │ 3.10, 3.11,│
└──────────┘              └──────────────┘  /3.12      │ 3.12       │
                                                       └─────┬──────┘
                                                             │
                              ┌───────────────────────────────┤
                              │                               │
                              ▼                               ▼
                       ┌────────────┐                  ┌────────────┐
                       │ ruff check │                  │ pytest     │
                       │ (lint)     │                  │ tests/unit │
                       └────────────┘                  └────────────┘
                              │
                              ▼
                       ┌────────────┐
                       │ mypy       │  (continue-on-error)
                       │ (types)    │
                       └────────────┘

Integration tests: manual dispatch only (requires secrets)
```

---

## 6. Verification and Quality

### Test Summary

| Metric               | Value                               |
| -------------------- | ----------------------------------- |
| **Framework**        | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Total unit tests** | 501                                 |
| **Pass rate**        | 100% (501/501)                      |
| **Execution time**   | 0.81s                               |
| **Test files**       | 29 unit + 10 integration            |
| **Test lines**       | ~10,300                             |
| **Run command**      | `pytest tests/unit/ -v`             |

### Integration Tests (Live Browser / API)

| Provider   | Tests | Pass | Status | Notes                                        |
| ---------- | ----- | ---- | ------ | -------------------------------------------- |
| Claude     | 10    | 10   | ✅ 100% | Headless Camoufox, full trace capture        |
| Gemini     | 10    | 9    | ✅ 90%  | Headless Camoufox, translator + model change |
| OpenRouter | 10    | 10   | ✅ 100% | API-based, model fallback                    |
| OpenAI     | 6     | 6    | ✅ 100% | API-based, extended thinking                 |

### Test Coverage by Module

| Module                         | Test File                    | Tests |
| ------------------------------ | ---------------------------- | ----- |
| core/types.py                  | test_types.py                | 7     |
| core/config.py                 | test_config.py               | ~6    |
| core/history.py                | test_history.py              | ~8    |
| core/output.py                 | test_output.py               | 3     |
| core/retry.py                  | test_retry.py                | 4     |
| browser/selectors.py           | test_selectors.py            | 2     |
| browser/response_detector.py   | test_response_detector.py    | 3     |
| browser/base_browser_agent     | test_browser_providers.py    | ~5    |
| api/base_api_agent.py          | test_base_api_agent.py       | ~12   |
| cli/base_cli_agent.py          | test_base_cli_agent.py       | ~8    |
| providers/openrouter/          | test_openrouter.py           | ~9    |
| providers/pplx/                | test_perplexity.py           | ~11   |
| providers/copilot/             | test_copilot.py              | ~5    |
| providers/claude/data.py       | test_claude_data.py          | ~8    |
| providers/claude/translator.py | test_translator.py           | 18    |
| compiler/                      | test_compiler_phase2.py      | ~30   |
| compiler/                      | test_compiler_phase3.py      | ~25   |
| compiler/                      | test_compiler_integration.py | ~15   |
| compiler/compiler_llm.py       | test_compiler_llm.py         | ~15   |
| compiler/agent_packager.py     | test_agent_packager.py       | 21    |
| core/srt_utils.py              | test_srt_utils.py            | 38    |
| core/translation_prompts.py    | test_translation_prompts.py  | ~5    |
| browser/base_browser_agent     | test_send_message.py         | 15    |
| core/json_utils.py + prompt    | test_shared_utils.py         | ~8    |
| compiler/auth_detector.py      | test_auth_detector.py        | ~12   |
| v1 ported tests                | test_v1_claude_jobs.py       | ~30   |
| monitor/events.py              | test_events.py               | ~10   |
| monitor/agent_registry.py      | test_agent_registry.py       | ~8    |
| monitor/monitored_agent.py     | test_monitored_agent.py      | ~10   |
| monitor/dashboard.py           | test_dashboard.py            | ~7    |
| monitor/reporter.py            | test_reporter.py             | ~12   |
| monitor (integration)          | test_monitor_integration.py  | 5     |

### CI/CD

- **Config:** `.github/workflows/ci.yml`
- **Triggers:** Push to `main`, PR to `main`
- **Matrix:** Python 3.10, 3.11, 3.12 on ubuntu-latest
- **Steps:** `pip install -e ".[dev]"` → `ruff check` → `mypy` (continue-on-error) → `pytest tests/unit/`
- **Integration:** Manual `workflow_dispatch` only (requires `CLAUDE_STORAGE_STATE`, `OPENROUTER_API_KEY` secrets)

### Known Issues / Tech Debt

- **No code coverage reporting** — Consider adding `pytest-cov` and coverage thresholds
- **ruff not installed in dev venv** — Download kept timing out during setup; CI will catch lint issues
- **Integration tests not runnable in CI** — Require live browser auth or API keys
- **`dom.py` type_text ProseMirror detection** — Uses heuristic (content-editable check); may need updating if provider UIs change
- **`browser_manager.py` stealth** — `playwright_stealth` is optional dependency; fallback to manual anti-detection args

---

## 7. Key Files Quick Reference

| File                                                   | Lines | Purpose                                                    |
| ------------------------------------------------------ | ----- | ---------------------------------------------------------- |
| `src/universal_agents/core/base_agent.py`              | 53    | Abstract base class for all agent types                    |
| `src/universal_agents/core/config.py`                  | 67    | All configuration dataclasses (Base/Browser/API/CLI)       |
| `src/universal_agents/core/types.py`                   | 81    | Shared data types (Message, ConversationTurn, AgentStats)  |
| `src/universal_agents/core/srt_utils.py`               | 259   | SRT parsing, chunking, overlap, normalization           |
| `src/universal_agents/core/kendo_context.py`           | 122   | Kendo dictionary loader + SRT-specific prompts             |
| `src/universal_agents/browser/base_browser_agent.py`   | 130   | Shared browser chat loop with hook pattern + _send_message |
| `src/universal_agents/browser/browser_manager.py`      | 187   | Playwright lifecycle, stealth, storage state, Cloudflare   |
| `src/universal_agents/browser/response_detector.py`    | 109   | 2-phase response stabilization detection                   |
| `src/universal_agents/api/base_api_agent.py`           | 222   | HTTP API base with sync/stream, retry, rate limiting       |
| `src/universal_agents/providers/claude/chat.py`        | 100   | Claude browser agent with 3-strategy thinking              |
| `src/universal_agents/providers/claude/translator.py`  | 399   | Multi-turn translator with file upload + progress          |
| `src/universal_agents/providers/gemini/translator.py`  | 723   | Gemini translator — model selection, rate limits, progress |
| `src/universal_agents/providers/pplx/chat.py`          | 133   | Perplexity agent with citation extraction                  |
| `src/universal_agents/compiler/compiler.py`            | 91    | Agent compiler orchestrator                                |
| `src/universal_agents/compiler/agent_packager.py`      | 248   | Self-contained agent package creator                       |
| `src/universal_agents/compiler/question_flow.py`       | 439   | Interview questions + presets for compilation              |
| `src/universal_agents/compiler/capability_resolver.py` | 195   | Map requirements → components                              |
| `src/universal_agents/monitor/events.py`               | 44    | Event system (EventType, AgentEvent, EventBus)             |
| `src/universal_agents/monitor/reporter.py`             | 133   | Post-run report generation (JSON + text)                   |
| `src/universal_agents/monitor/dashboard.py`            | 89    | Live terminal dashboard (rich)                             |
| `pyproject.toml`                                       | 48    | Project metadata, dependencies, build + tool config        |
| `.github/workflows/ci.yml`                             | 61    | GitHub Actions CI pipeline                                 |
