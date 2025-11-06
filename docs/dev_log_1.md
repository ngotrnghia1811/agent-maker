# Development Log 1 — universal-agent_v2

**Date:** 2026-03-28  
**Author:** Development Session Notes  

---

## Overview

universal-agent_v2 is a browser automation framework for interacting with LLM providers (Claude, Gemini, GPT, etc.) through their web UIs using Playwright. This log documents the implementation progress from Phase 1 through to the current state.

---

## Phase 1: Core Foundation

Built the core framework architecture:

- **`core/`** — Base configuration (`BrowserConfig`, `APIConfig`), types (`Message`, `ConversationTurn`, `TurnResult`), history management, exceptions, output utilities
- **`browser/`** — `BrowserManager` (Playwright lifecycle, stealth, storage state), `BaseBrowserAgent` (abstract agent with `_ensure_ready()`, `chat()` flow), DOM helpers (`find_element`, `type_text`, `click_submit`), `ResponseDetector` (waits for response stabilization)
- **`providers/claude/`** — `ClaudeChatAgent` with thinking extraction via 3 strategies
- **Result:** 34 unit tests passing

## Phase 2: Remaining Providers

Added provider implementations:

- **Gemini** — Chat agent with Google-specific DOM selectors
- **GPT** — ChatGPT browser agent
- **Perplexity** — Search-focused agent
- **OpenRouter** — Multi-model router
- **Copilot** — Microsoft Copilot agent
- **Claude Data Agent** — JSON generation/extraction with `build_data_prompt()` and `extract_json()`
- **Result:** 102 unit tests passing

## Phase 3: Monitor + Dashboard

Implemented monitoring infrastructure:

- **Events** — Event types and event bus for agent lifecycle tracking
- **Registry** — Agent registry for managing active agent instances
- **MonitoredAgent** — Wrapper that emits events from agent operations
- **Dashboard** — Real-time monitoring dashboard
- **Reporter** — Test result reporting and aggregation
- **Result:** 152 unit tests passing

## Phase 4: Polish

Final project setup:

- Documentation (API reference, agent structure, codebase report)
- Example scripts
- CI configuration
- `py.typed` marker for type checking
- **Result:** 170 unit tests passing

---

## Phase 2.9: Translator Agent

Implemented `ClaudeTranslatorAgent` wrapping `ClaudeDataAgent`:

- Multi-turn conversation with automatic splitting after N turns
- PDF/image file upload via Playwright (3 strategies)
- Progress state for resumable translation jobs
- Chunk-based text and file translation
- `TranslationChunk`, `TranslationResult`, `ProgressState` dataclasses
- **Result:** 170 unit tests passing

---

## Full Trace Capture Implementation

### Problem
Initial implementation only captured the final answer. Needed full trace of LLM response including intermediate steps, reasoning, and raw API data.

### Research — V1's Architecture
V1 used a 3-strategy thinking extraction approach:
1. **Playwright intercept** — Intercept `response` events on API URLs (`/api/organizations/.../chat_conversations`)
2. **Fetch override JS** — Inject JS that overrides `window.fetch` to capture response bodies
3. **React state extraction** — Navigate React component tree to find thinking content from internal state

### Implementation
Modified 8 files across the codebase:

- **`core/types.py`** — Added `raw_api_responses: list[dict]` and `thinking_source: Optional[str]` to `ConversationTurn`; matching fields in `TurnResult`
- **`core/history.py`** — `add_turn()` accepts `raw_api_responses` and `thinking_source` params
- **`browser/browser_manager.py`** — Added `_on_response()` handler that captures API responses matching `/api/organizations/.../chat_conversations`; `get_captured_responses()` and `clear_captured_responses()` methods
- **`browser/base_browser_agent.py`** — `chat()` captures raw API responses + thinking_source tuple from `_extract_thinking()`; clears captured responses before each turn
- **`providers/claude/chat.py`** — `_extract_thinking()` returns `(thinking, source)` tuple; sources: `"playwright_intercept"`, `"fetch_override_js"`, `"react_state_{found_via}"`
- **`providers/claude/data.py`** — Same tuple pattern
- **`providers/claude/translator.py`** — `translate_file()` records turns with raw API responses
- **`core/output.py`** — `save_full_results()` includes raw_api_responses, thinking_source

### Test Infrastructure
Created `test_v1_claude_jobs_live.py` with full trace capture per test:
- Each test saves `trace.json` (full structured data) + `trace.md` (human-readable) 
- Results stored in `storage/live_test_results/run_{TIMESTAMP}/`
- Consolidated `summary.json` per run

**Result:** 220 unit tests + 8/8 live tests passing

---

## CJK Typing Fix

### Problem
Japanese/Chinese text wouldn't type correctly in Claude's ProseMirror editor. The `keyboard.type()` method sends individual key presses which doesn't work for CJK characters.

### Solution
Added `_has_non_ascii()` detection in `browser/dom.py`. When non-ASCII text is detected, uses `keyboard.insert_text()` (which uses the system clipboard path) instead of `keyboard.type()`.

```python
def _has_non_ascii(text: str) -> bool:
    return any(ord(c) > 127 for c in text)
```

---

## PDF Upload Fix — 3 Bugs

### Bug 1: Missing Navigation
`upload_file()` called `browser_mgr.ensure_page()` instead of `_ensure_ready()`. The page wasn't navigated to claude.ai, so the file input elements weren't in the DOM.

**Fix:** Changed to `await self._agent._ensure_ready()`.

### Bug 2: Wrong `type_text` API
Code was calling `type_text(page, SELECTORS, text)` but the actual signature is `type_text(locator, text)`.

**Fix:** Use `find_element()` first to get a locator, then call `type_text(locator, text)`.

### Bug 3: Wrong `add_turn` Arguments
`history.add_turn()` was passed raw strings instead of `Message` objects.

**Fix:** Wrap in `Message(role="user", content=...)` and `Message(role="assistant", content=...)`.

### Upload Strategy
Implemented 3 fallback strategies:
1. Click attach button → intercept file chooser dialog
2. Direct `set_input_files()` on hidden `input[data-testid="file-upload"]`
3. JS fallback to expose hidden file inputs and set files

---

## Headless Mode & CLI Flags

### Problem
All test functions had `headless=False` hardcoded. Needed headless as default with `--visible` opt-in.

### Implementation
- Added `headless: bool = True` parameter to all 10 test functions
- Test functions pass `headless` to config constructors
- Added `--visible` CLI flag to argparse
- `run_all()` and `run_selected()` pass headless state through
- Banner shows `headless=True (hidden)` or `headless=False (visible)`

### Cloudflare Limitation
**Finding:** Headless browsers are blocked by Cloudflare's bot detection on claude.ai. Even with:
- `--headless=new` (Chrome's new headless mode)
- `navigator.webdriver` spoofing
- `playwright-stealth` library
- Enhanced init scripts (plugins, languages spoofing)

Cloudflare still shows "Performing security verification" page. The `BrowserConfig.headless` defaults to `True`, but live tests against claude.ai require `--visible` flag.

**Mitigations added:**
- `--headless=new` Chrome arg when headless=True
- Enhanced stealth init scripts (plugins, languages)
- Improved `_handle_cloudflare()` to detect "security verification" body text
- Navigate retry (up to 3 attempts) with 5s backoff on Cloudflare challenge
- `BrowserConfig` default is `headless=True` (correct for non-Cloudflare providers)

---

## Model Changing Feature

### Problem
Claude.ai allows changing the model (Sonnet, Opus, Haiku). Need to programmatically switch models.

### DOM Discovery
Used `debug_model_selector.py` to inspect the model selector DOM:
- **Button:** `[data-testid="model-selector-dropdown"]` — shows current model name
- **Menu:** `[role="menu"]` with `[role="menuitem"]` children after clicking button
- **Available models:** Opus 4.6, Sonnet 4.6, Haiku 4.5, Extended thinking, More models

### Implementation
Added `test_model_change()` test that:
1. Navigates to claude.ai via `_ensure_ready()`
2. Finds model selector button via `[data-testid="model-selector-dropdown"]`
3. Clicks to open dropdown
4. Finds all `[role="menuitem"]` options
5. Selects "Opus" option
6. Verifies button text changes
7. Sends a test message to confirm model identity

### Test Result
```
Current model: Sonnet 4.6 Extended
Available: [Opus 4.6, Sonnet 4.6, Haiku 4.5, Extended thinking, More models]
Selected: Opus 4.6 Extended
Response: "I'm Claude Opus 4.6, made by Anthropic."
✅ PASS (30228ms)
```

---

## Multi-Page PDF Sequential Upload

### Problem
Need to test uploading PDF pages one at a time and verify the agent manages conversation history/context across multiple file uploads.

### Implementation
- Created `create_multipage_pdf.py` script using reportlab with CID fonts (HeiseiMin-W3) for Japanese text
- Generates 3-page PDF (`test_japanese_multipage.pdf`, 4637 bytes) + 3 individual pages
  - Page 1: Tokyo/capital (東京は日本の首都です)
  - Page 2: Culture/anime (日本の文化は非常に豊かで多様です)
  - Page 3: Technology/Shinkansen (日本は技術革新の分野でリーダーです)
- `test_translator_multi_page_pdf()` uploads pages sequentially, checking:
  - Each upload succeeds
  - Conversation turn count increases
  - Full translation concatenates all pages
  - Context maintained (consistent style instruction in first turn)

---

## Test Suite Summary

### Unit Tests
**220 tests** — All passing (0.60s)

### Live Integration Tests (run_20260328_190521 — 8/8)

| Test                    | Status | Time  | Details                                  |
| ----------------------- | ------ | ----- | ---------------------------------------- |
| Chat Single Turn        | ✅ PASS | 25.4s | Got "4" in response                      |
| Chat Multi-Turn         | ✅ PASS | 47.2s | Context maintained: 42→84→100            |
| Chat Thinking           | ✅ PASS | 30.2s | Thinking captured (playwright_intercept) |
| Data JSON Generation    | ✅ PASS | 54.7s | JSON extracted, processed=True           |
| Data BREAK Prompt       | ✅ PASS | 55.2s | Keys: question, answer, reasoning        |
| Translator Single Chunk | ✅ PASS | 31.7s | Japanese→English translated              |
| Translator Multi-Chunk  | ✅ PASS | 41.7s | 2 chunks, 2 turns                        |
| Translator PDF Upload   | ✅ PASS | 36.8s | "Tokyo is the capital of Japan"          |

### Model Change Test (run_20260328_233349 — 1/1)

| Test         | Status | Time  | Details                                       |
| ------------ | ------ | ----- | --------------------------------------------- |
| Model Change | ✅ PASS | 30.2s | Sonnet 4.6 → Opus 4.6, confirmed via response |

### New Tests Added (pending fresh auth)
- `translator_multi_pdf` — 3-page sequential PDF upload
- `model_change` — Model switching via dropdown

---

## Architecture Notes

### Config Hierarchy
```
BrowserConfig(headless=True, viewport, storage_state, timeouts)
  └── ClaudeConfig(base_url="https://claude.ai/new", extract_thinking=True)
        └── ClaudeDataConfig(timeout=300)
              └── ClaudeTranslatorConfig(timeout=600, max_turns_per_conversation=20)
```

### Thinking Extraction Sources
1. `"playwright_intercept"` — API response interception via Playwright's `page.on("response")`
2. `"fetch_override_js"` — Injected JS overriding `window.fetch` to capture response bodies
3. `"react_state_{path}"` — React component tree traversal for internal state

### Key DOM Selectors (Claude.ai)
- Chat input: `div.ProseMirror[contenteditable='true']`
- Submit button: `button[aria-label='Send message']`
- Response: `div[data-is-streaming]`, `.font-claude-message`
- Model selector: `[data-testid="model-selector-dropdown"]`
- Model menu items: `[role="menu"] [role="menuitem"]`
- File upload: `input[data-testid="file-upload"]`, `button[aria-label*="Add files"]`

### File Structure
```
src/universal_agents/
├── core/           # Base types, config, history, exceptions, output
├── browser/        # BrowserManager, BaseBrowserAgent, DOM, ResponseDetector
├── providers/      # Claude (chat, data, translator), Gemini, GPT, etc.
├── api/            # REST API wrappers
├── cli/            # CLI tools
└── monitor/        # Events, registry, dashboard, reporter

tests/
├── unit/           # 220 unit tests (pytest)
└── integration/    # Live browser tests, fixtures, debug scripts
```
