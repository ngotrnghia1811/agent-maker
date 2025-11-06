# Development Logs 1–5 — Problems & Solutions Summary

**universal-agent_v2**  
**Dates:** 2026-03-28 → 2026-03-31  

---

## Table of Contents

- [Development Logs 1–5 — Problems \& Solutions Summary](#development-logs-15--problems--solutions-summary)
  - [Table of Contents](#table-of-contents)
  - [Log 1 — Core Framework \& Claude Provider (2026-03-28)](#log-1--core-framework--claude-provider-2026-03-28)
    - [Progress](#progress)
    - [Problems \& Solutions](#problems--solutions)
    - [Key Architecture](#key-architecture)
  - [Log 2 — Headless Mode \& Camoufox, Gemini Provider (2026-03-29)](#log-2--headless-mode--camoufox-gemini-provider-2026-03-29)
    - [Progress](#progress-1)
    - [Problems \& Solutions](#problems--solutions-1)
    - [Key Decision: Camoufox vs playwright-stealth](#key-decision-camoufox-vs-playwright-stealth)
  - [Log 3 — Thinking Extraction, Gemini Translator, Test Parity (2026-03-29)](#log-3--thinking-extraction-gemini-translator-test-parity-2026-03-29)
    - [Progress](#progress-2)
    - [Problems \& Solutions](#problems--solutions-2)
    - [Gemini File Upload Strategy (4 fallback levels)](#gemini-file-upload-strategy-4-fallback-levels)
  - [Log 4 — Agent Packaging \& Kendo SRT Infrastructure (2026-03-30)](#log-4--agent-packaging--kendo-srt-infrastructure-2026-03-30)
    - [Progress](#progress-3)
    - [Problems \& Solutions](#problems--solutions-3)
    - [Key Architecture Decisions](#key-architecture-decisions)
  - [Log 5 — Long Message Handling, Claude Compiled Agent, SRT Normalization (2026-03-31)](#log-5--long-message-handling-claude-compiled-agent-srt-normalization-2026-03-31)
    - [Progress](#progress-4)
    - [Problems \& Solutions](#problems--solutions-4)
  - [Cumulative Statistics](#cumulative-statistics)
    - [All Problems (28 total)](#all-problems-28-total)

---

## Log 1 — Core Framework & Claude Provider (2026-03-28)

### Progress
- Built entire core framework: `core/` (config, types, history, exceptions, output), `browser/` (BrowserManager, BaseBrowserAgent, DOM helpers, ResponseDetector), `providers/` (Claude chat, data, translator + Gemini, GPT, Perplexity, OpenRouter, Copilot stubs)
- Implemented Claude thinking extraction via 3 strategies: Playwright API intercept, fetch override JS, React state extraction
- Built monitor + dashboard infrastructure (events, registry, MonitoredAgent, reporter)
- Added translator agent with multi-turn conversation, PDF upload, progress state, chunk-based translation
- Model changing feature for Claude.ai via `[data-testid="model-selector-dropdown"]`
- 220 unit + 8 live integration tests passing

### Problems & Solutions

| #   | Problem                                               | Root Cause                                                                            | Solution                                                                          |
| --- | ----------------------------------------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 1   | CJK text (Japanese/Chinese) won't type in ProseMirror | `keyboard.type()` sends individual key presses, incompatible with CJK                 | Added `_has_non_ascii()` detection → use `keyboard.insert_text()` for non-ASCII   |
| 2   | PDF upload: page not navigated                        | `upload_file()` called `browser_mgr.ensure_page()` instead of `_ensure_ready()`       | Changed to `await self._agent._ensure_ready()`                                    |
| 3   | PDF upload: wrong `type_text` API                     | Called `type_text(page, SELECTORS, text)` but signature is `type_text(locator, text)` | Use `find_element()` first to get locator, then `type_text(locator, text)`        |
| 4   | PDF upload: wrong `add_turn` args                     | Passed raw strings instead of `Message` objects                                       | Wrap in `Message(role="user", content=...)`                                       |
| 5   | Cloudflare blocks headless Chromium                   | Even with `--headless=new`, stealth, plugins spoofing — Turnstile still triggers      | Documented as limitation; added retry + backoff as mitigation (full fix in Log 2) |

### Key Architecture
```
BrowserConfig(headless, viewport, storage_state, timeouts)
  └── ClaudeConfig(base_url, extract_thinking)
        └── ClaudeDataConfig(timeout=300)
              └── ClaudeTranslatorConfig(timeout=600, max_turns=20)
```
Thinking sources: `playwright_intercept`, `fetch_override_js`, `react_state_{path}`

---

## Log 2 — Headless Mode & Camoufox, Gemini Provider (2026-03-29)

### Progress
- Tried 3 approaches for headless browser automation, settled on Camoufox
- Rewrote BrowserManager to use Camoufox as primary engine with Chromium fallback
- Implemented Gemini provider (chat, data agents) with Angular-specific handling
- All 10 Claude tests + 5 Gemini tests passing headless

### Problems & Solutions

| #   | Problem                                                   | Root Cause                                                                                                                                          | Solution                                                                                                                 |
| --- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| 1   | Off-screen window positioning fails                       | macOS doesn't render off-screen windows; Playwright can't compute hit points; bounding boxes return (0,0,0,0)                                       | **ABANDONED** — not a viable headless alternative on macOS                                                               |
| 2   | playwright-stealth alone can't bypass Cloudflare          | Chromium headless fingerprint detected by Turnstile despite JS-level evasion patches                                                                | **ABANDONED** — JS-level patches insufficient, need C++ browser patches                                                  |
| 3   | Camoufox (Firefox) doesn't support `storage_state=` kwarg | Firefox/Camoufox persistent context API differs from Chromium                                                                                       | Manual cookie injection via `ctx.add_cookies(state["cookies"])`                                                          |
| 4   | Gemini "No new response" — count stays at 0               | Angular hydration delay (10-15s); selectors fail before app bootstraps                                                                              | Added `page.wait_for_selector("div[contenteditable='true']", state="visible", timeout=30000)` in `_post_navigate()`      |
| 5   | Response text includes "Gemini said" prefix               | `count_responses()` and `wait_for_new_response()` used different selectors independently; broader selector (`model-response`) matched               | `count_responses()` returns `(count, selector_used)` + `wait_for_new_response()` accepts `selector_hint` for consistency |
| 6   | Gemini API interception fails                             | Gemini uses `StreamGenerate` (capital S/G), not `/generate`/`/stream`; `batchexecute` uses protobuf-wrapped JSON that `response.json()` can't parse | Updated URL matching; API thinking extraction remains non-functional (DOM-based approach in Log 3)                       |

### Key Decision: Camoufox vs playwright-stealth
| Aspect       | Camoufox              | playwright-stealth    |
| ------------ | --------------------- | --------------------- |
| Engine       | Firefox (C++ patched) | Chromium (JS patches) |
| Cloudflare   | Silent pass           | Turnstile challenge   |
| Install size | ~300MB Firefox binary | ~50KB Python package  |
**Decision:** Camoufox primary, playwright-stealth as fallback.

---

## Log 3 — Thinking Extraction, Gemini Translator, Test Parity (2026-03-29)

### Progress
- Claude thinking extraction via Playwright API interception (SSE events with `type: "thinking"`)
- Gemini thinking extraction via DOM "Show thinking" button click + `.thinking-content` scraping
- Built `GeminiTranslatorAgent` with file upload, multi-turn management, conversation splitting
- Expanded Gemini test suite from 5 to 10 tests (matching Claude)
- Standardized result folders to `storage/test_results/{provider}/run_{TIMESTAMP}/`
- OpenRouter API integration (chat + data agents)

### Problems & Solutions

| #   | Problem                                  | Root Cause                                                                      | Solution                                                                                                           |
| --- | ---------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 1   | Gemini thinking extraction via API fails | `batchexecute` uses Google's protobuf-wrapped JSON; standard JSON parsing fails | Abandoned API approach; used DOM-based extraction: click "Show thinking" toggle → extract `.thinking-content` text |
| 2   | Gemini file upload before hydration      | Upload button only appears after Angular fully hydrates                         | Added `wait_for_selector('button[aria-label="Open upload file menu"]', timeout=10000)` before upload               |
| 3   | Data BREAK test fails in sequential run  | Selector timing issue when tests run sequentially                               | Passes in isolation; known timing sensitivity in test suite                                                        |
| 4   | Mode picker not in header                | Gemini's model selector is in the input toolbar, not the page header            | Found correct selector: `button[data-test-id="bard-mode-menu-button"]` with `aria-label="Open mode picker"`        |

### Gemini File Upload Strategy (4 fallback levels)
1. Click upload menu → "Upload files" menu item → intercept `file_chooser` → set file
2. Dispatch click on `button[data-test-id="hidden-local-file-upload-button"]`
3. Set input files on `input[type="file"]` elements directly
4. JS-expose hidden file inputs and set files

---

## Log 4 — Agent Packaging & Kendo SRT Infrastructure (2026-03-30)

### Progress
- Built `AgentPackager` — creates self-contained agent directories with `agent.py`, `config.json`, `storage/`, `requirements.txt`, `README.md`, `source_spec.json`
- Built kendo SRT translation infrastructure: dictionary loader (`kendo_context.py`), SRT-specific prompts, batch runner
- Added model selection, rate limit detection, conversation splitting to Gemini translator
- 476 tests passing

### Problems & Solutions

| #   | Problem                                        | Root Cause                                                                  | Solution                                                                                                      |
| --- | ---------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 1   | Orphaned `self.progress.save()` line           | Stray line left outside any method after refactoring                        | Identified and removed the duplicate line                                                                     |
| 2   | SRT "lines" ambiguity                          | User says "400 lines" but SRT has block numbers, timestamps, and text       | Defined "lines" = SRT subtitle blocks (each block = index + timestamp + text + blank separator)               |
| 3   | Rate limit detection without API               | Gemini's browser UI doesn't expose rate limit status                        | After each response, read mode picker button text; if shows "fast" when we requested "pro" → `RateLimitError` |
| 4   | Dictionary context lost at conversation splits | New conversation loses all previous context including 61KB kendo dictionary | `build_kendo_new_conversation_prompt()` embeds full dictionary in every conversation-opening message          |

### Key Architecture Decisions
- **Embed dictionary in every conversation** (61KB inline vs file attachment) — simpler, guaranteed to work, within Gemini Pro's context window
- **Browser-based translation** (free Pro access) vs API (requires billing) — cost-effective for 35 files × ~800 blocks
- **Stop on rate limit** (not auto-retry) — Gemini doesn't expose reset times; save progress + manual resume is more reliable
- **Package directory** (not Docker) — lightweight, editable, portable: `pip install -r requirements.txt && python agent.py`

---

## Log 5 — Long Message Handling, Claude Compiled Agent, SRT Normalization (2026-03-31)

### Progress
- Added `_send_message()` hook to `BaseBrowserAgent` with provider-specific overrides
- Gemini: file upload strategy for messages >100 words (3 fallback strategies)
- Claude: system clipboard paste for messages >1000 words via `pbcopy` + `Cmd+V`
- Built Claude compiled SRT translator agent with login verification, paste input, SRT normalization
- Three iterations of `normalize_srt_text()` fixes for Claude's broken SRT output
- Quality checker script; SRT 002: 225/225 complete, SRT 003: 150/164
- 501 tests passing

### Problems & Solutions

| #   | Problem                                                     | Root Cause                                                                                 | Solution                                                                                          | Iterations                                |
| --- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| 1   | Character-by-character typing too slow for large SRT chunks | `dom.type_text()` types each character; 7167 words = 10+ minutes                           | Added `_send_message()` hook: Gemini uploads as .txt file, Claude pastes via system clipboard     | 1                                         |
| 2   | `navigator.clipboard.writeText()` silently fails            | Browser clipboard API requires permissions unavailable in Camoufox automation context      | Use OS-level `subprocess.run(["pbcopy"])` + `page.keyboard.press("Meta+v")` instead               | 1 (after discovering browser API failure) |
| 3   | Claude SRT: block numbers split across lines                | Claude outputs "1\n\n0" instead of "10" for two-digit block numbers                        | Regex merge before parsing: `re.sub(r"(\S)\n(\d+)\n\n(\d+)\n(\d{1,2}:\d{2}:\d{2})")`              | 1                                         |
| 4   | Claude SRT: trailing standalone digits                      | Claude appends tens digit as trailing text in previous block                               | Post-parse strip: `while block_lines[-1].match(r"^\d+$"): block_lines.pop()`                      | 1                                         |
| 5   | Claude SRT: cycling single-digit block numbers              | Claude loses numbering track after 9 (outputs 0,1,2,3 instead of 10,11,12,13)              | Sequential renumbering after parsing: `block.index = i`                                           | 1                                         |
| 6   | Claude login verification fails                             | ProseMirror editor loads asynchronously; check fails before page ready                     | Navigate + `networkidle` wait + 30-second ProseMirror polling loop                                | 1                                         |
| 7   | Claude file upload unreliable                               | `set_input_files` + event dispatch on hidden input element was intermittent                | Switched to system clipboard paste (3 iterations: set_input_files → navigator.clipboard → pbcopy) | 3                                         |
| 8   | SRT 003 starts at 00:05:44 instead of beginning             | First prompt upload failed silently                                                        | Paste fix resolved the root cause; re-run starts from beginning                                   | 1                                         |
| 9   | Playwright FrameManager crash                               | Internal bug with Node.js v24 + Camoufox: `TypeError: Cannot read properties of undefined` | Intermittent; worked on retry                                                                     | Known issue                               |

---

## Cumulative Statistics

| Metric          | Log 1                   | Log 2                     | Log 3                       | Log 4                       | Log 5                            |
| --------------- | ----------------------- | ------------------------- | --------------------------- | --------------------------- | -------------------------------- |
| Date            | 03-28                   | 03-29                     | 03-29                       | 03-30                       | 03-31                            |
| Unit Tests      | 220                     | 220                       | 220                         | 476                         | 501                              |
| Live Tests      | 8/8 Claude              | 10/10 Claude + 5/5 Gemini | 9/10 Gemini (10-test suite) | —                           | —                                |
| Problems Solved | 5                       | 6                         | 4                           | 4                           | 9                                |
| Key Feature     | Core framework + Claude | Camoufox headless         | Gemini translator           | Agent packaging + kendo SRT | Long msg handling + Claude agent |

### All Problems (28 total)

**Browser Automation (10):**
1. CJK typing in ProseMirror → `insert_text()` for non-ASCII
2. Off-screen window positioning → abandoned (macOS limitation)
3. playwright-stealth vs Cloudflare → Camoufox (C++ Firefox patches)
4. Camoufox `storage_state` kwarg → manual `add_cookies()`
5. Angular hydration delay → explicit `wait_for_selector()` polls
6. Gemini mode picker location → found in input toolbar, not header
7. Gemini file upload timing → hydration wait before upload
8. Claude login async load → networkidle + 30s ProseMirror poll
9. Playwright FrameManager crash → intermittent Node.js v24 bug, retry
10. Claude file upload unreliable → 3 iterations: set_input_files → navigator.clipboard → system pbcopy

**Response Detection (3):**
11. Response includes "Gemini said" prefix → consistent selector hint between count/wait
12. Gemini API interception → StreamGenerate URL + protobuf-wrapped JSON
13. Gemini thinking extraction → abandoned API, used DOM button click

**SRT Translation (8):**
14. Character-by-character typing too slow → `_send_message()` hook (upload/paste)
15. Browser clipboard API silently fails → OS-level `pbcopy`/`xclip`
16. Block numbers split across lines → regex merge
17. Trailing standalone digits → post-parse strip
18. Cycling single-digit block numbers → sequential renumbering
19. SRT "lines" ambiguity → defined as subtitle blocks
20. Dictionary context lost at conversation splits → embed in every opening prompt
21. SRT starts mid-file → paste fix resolved silent upload failure

**Agent Infrastructure (4):**
22. PDF upload wrong APIs (3 bugs) → correct signatures + Message objects
23. Orphaned `self.progress.save()` → removed duplicate
24. Rate limit detection without API → mode picker button text monitoring
25. First chunk hangs (7167 words) → system clipboard paste

**Architecture Decisions (3):**
26. Headless strategy → Camoufox primary, Chromium fallback
27. 61KB dictionary in every prompt → inline text (not file upload)
28. Stop on rate limit → save progress, manual resume (no auto-retry)
