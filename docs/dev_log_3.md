# Development Log 3 — universal-agent_v2

**Date:** 2026-03-29  
**Author:** Development Session Notes  

---

## Overview

This log documents the implementation of thinking extraction for Claude and Gemini, the Gemini translator agent with PDF upload, Gemini model change, expansion of Gemini tests to 10-test parity with Claude, result folder standardization, and OpenRouter integration testing.

---

## Thinking Extraction

### Claude — Playwright API Interception (`playwright_intercept`)

Claude's streaming responses use the `text/event-stream` content type via their API. Thinking content is embedded in SSE events with `type: "thinking"`.

**Implementation:**
- `BrowserManager._on_response()` captures raw API responses matching `"/api/"`
- `ClaudeChatAgent._extract_thinking()` parses SSE events from raw responses
- Looks for `content_block_start` events with `type: "thinking"` and `content_block_delta` with `type: "thinking_delta"`
- Falls back to `completion` events if block-level events aren't found

**Result:** Thinking text extracted reliably from Claude's streaming API. Source tagged as `playwright_intercept`.

### Gemini — DOM Button Click (`dom_button_click`)

Gemini's `batchexecute` API uses Google's protobuf-wrapped JSON that standard JSON parsing can't handle. API interception was abandoned in favor of DOM-based extraction.

**Implementation:**
- `GeminiChatAgent._extract_thinking()` clicks the "Show thinking" toggle in the response DOM
- Uses `_JS_CLICK_AND_EXTRACT_THINKING` — JS that finds buttons matching "Show thinking" text, clicks to expand, then extracts the `.thinking-content` container text
- Falls back to `_JS_EXTRACT_THINKING_TEXT` which scans for already-expanded thinking containers

**Result:** Thinking text extracted by toggling the UI. Works only for models that produce thinking (Gemini 2.0 Flash Thinking). Source tagged as `dom_button_click`.

---

## Gemini Translator Agent

### Architecture

`GeminiTranslatorAgent` wraps `GeminiDataAgent` to provide:
- Multi-turn conversation management with turn counting
- PDF/image file upload via Playwright file chooser
- Chunk-based text and file translation
- Conversation splitting after N turns

**File:** `src/universal_agents/providers/gemini/translator.py` (~340 lines)

### Data Classes

- `TranslationChunk` — source text or file reference with chunk_id and metadata
- `TranslationResult` — success/failure, translated text, thinking, timing, serializable via `.to_dict()`

### File Upload Strategy (Gemini-Specific)

Gemini uses Angular Material components for file upload. The upload mechanism was discovered via DOM exploration:

1. **Primary:** Click `button[aria-label="Open upload file menu"]` → opens Material menu → click "Upload files" menu item → intercept `file_chooser` event → set file
2. **Fallback:** Directly dispatch click on `button[data-test-id="hidden-local-file-upload-button"]` 
3. **Fallback:** Set input files on `input[type="file"]` elements
4. **Fallback:** JS-expose hidden file inputs and set files

**Key Discovery:** The upload button only appears after Angular fully hydrates. Added `wait_for_selector('button[aria-label="Open upload file menu"]', timeout=10000)` before attempting upload to handle the timing gap.

### Text Translation

Uses the data agent's existing `chat()` method with structured prompts:
- First turn: system prompt + source text
- Subsequent turns: continue prompt + source text

---

## Gemini Model/Mode Change

### DOM Discovery

Gemini's model selector is not in the header — it's in the input area toolbar:
- **Mode picker:** `button[data-test-id="bard-mode-menu-button"]` with `aria-label="Open mode picker"`
- Shows current mode (e.g., "Fast", "Thinking", "Pro")
- Opens a `[role="menu"]` with `[role="menuitem"]` options

### Available Modes (2026-03)

| Mode     | Description                         |
| -------- | ----------------------------------- |
| Fast     | Answers quickly                     |
| Thinking | Solves complex problems             |
| Pro      | Advanced math and code with 3.1 Pro |

### Implementation

The test waits for the mode picker button, reads current mode text, clicks to open menu, selects a different mode, verifies the change, and sends a test message.

---

## Gemini 10-Test Suite

Expanded from 5 to 10 tests to match Claude's test set:

### New Tests Added

| #   | Test                      | Description                          | Status |
| --- | ------------------------- | ------------------------------------ | ------ |
| 6   | Translator Single Chunk   | Japanese→English text translation    | ✅ PASS |
| 7   | Translator Multi-Chunk    | 2 chunks with conversation context   | ✅ PASS |
| 8   | Translator PDF Upload     | Single PDF file upload + translation | ✅ PASS |
| 9   | Translator Multi-Page PDF | 3 sequential PDF pages               | ✅ PASS |
| 10  | Model Change              | Detect mode, switch, verify response | ✅ PASS |

### Full 10-Test Results

| #   | Test                      | Status | Time   |
| --- | ------------------------- | ------ | ------ |
| 1   | Chat Single Turn          | ✅      | 22.6s  |
| 2   | Chat Multi-Turn           | ✅      | 66.9s  |
| 3   | Chat Thinking             | ✅      | 33.3s  |
| 4   | Data JSON                 | ✅      | 34.1s  |
| 5   | Data BREAK                | ❌      | 32.7s  |
| 6   | Translator Single Chunk   | ✅      | 29.4s  |
| 7   | Translator Multi-Chunk    | ✅      | 48.8s  |
| 8   | Translator PDF Upload     | ✅      | 69.4s  |
| 9   | Translator Multi-Page PDF | ✅      | 124.0s |
| 10  | Model Change              | ✅      | 27.0s  |

**Result:** 9/10 passed. Test 5 (Data BREAK) failed due to selector timing in sequential run — passes in isolation. Total: 488s.

---

## Result Folder Standardization

### Before
```
storage/live_test_results/run_YYYYMMDD_HHMMSS/     (Claude)
storage/gemini_test_results/run_YYYYMMDD_HHMMSS/    (Gemini)
```

### After
```
storage/test_results/claude/run_YYYYMMDD_HHMMSS/
storage/test_results/gemini/run_YYYYMMDD_HHMMSS/
storage/test_results/openrouter/run_YYYYMMDD_HHMMSS/   (future)
```

Updated `.gitignore` to cover `storage/test_results/` and legacy paths.

---

## OpenRouter Integration

### Architecture

OpenRouter uses API-based agents (not browser automation):
- `OpenRouterChatAgent(BaseAPIAgent)` — HTTP chat completions with model fallback
- `OpenRouterDataAgent(BaseAPIAgent)` — data extraction with extended thinking for Claude models
- Config: `OpenRouterConfig(APIConfig)` with `OPENROUTER_API_KEY` env var

### Key Differences from Browser Agents

| Feature        | Browser (Claude/Gemini)   | API (OpenRouter)      |
| -------------- | ------------------------- | --------------------- |
| Authentication | Storage state cookies     | API key               |
| File upload    | DOM file chooser          | N/A                   |
| Model change   | DOM picker                | Config parameter      |
| Thinking       | API intercept / DOM click | Extended thinking API |
| Rate limiting  | Browser-implicit          | Explicit retry logic  |

---

## Files Changed

### New Files
- `src/universal_agents/providers/gemini/translator.py` — GeminiTranslatorAgent (~340 lines)
- `tests/integration/_debug_gemini_upload.py` — DOM exploration debug script (temporary)
- `tests/integration/_debug_gemini_upload2.py` — Upload mechanism debug script (temporary)
- `docs/dev_log_3.md` — This file

### Modified Files
- `src/universal_agents/providers/gemini/config.py` — Added `GeminiTranslatorConfig`
- `tests/integration/test_gemini_live.py` — Expanded from 5 to 10 tests, standardized result path
- `tests/integration/test_v1_claude_jobs_live.py` — Standardized result path
- `.gitignore` — Updated storage ignore patterns
