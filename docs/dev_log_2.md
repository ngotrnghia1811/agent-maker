# Development Log 2 — universal-agent_v2

**Date:** 2026-03-29  
**Author:** Development Session Notes  

---

## Overview

This log documents the implementation progress from the headless mode battle through Camoufox integration and Gemini provider implementation.

---

## Headless Mode — Background Approach (FAILED)

### Problem
macOS doesn't render off-screen browser windows. Playwright can't compute hit points for clicks on elements that aren't physically rendered.

### Attempted Solution
Added `background: bool = True` to `BrowserConfig`. Used `--window-position=-32000,-32000` to move the Chromium window off-screen.

### Result
**FAILED.** Playwright threw errors because element bounding boxes returned `(0, 0, 0, 0)` for off-screen windows on macOS. The browser engine doesn't actually render pixels for windows positioned outside the display bounds.

**Lesson:** Off-screen window positioning is not a viable headless alternative on macOS.

---

## Headless Mode — playwright-stealth Alone (FAILED)

### Problem
`playwright-stealth` v2.x patches navigator.webdriver, Chrome runtime, WebGL, plugins, permissions, and languages at the context level. However, Cloudflare's Turnstile bot detection is more sophisticated.

### Implementation
- Installed `playwright-stealth==2.0.2`
- Applied `Stealth().apply_stealth_async(context)` (v2.x context-level API)
- Removed old page-level `stealth_async(page)` call
- Removed manual init_scripts that conflicted with stealth

### Diagnosis
Created `diagnose_headless.py` to capture screenshots + DOM state in headless mode:
- **URL:** `claude.ai/api/challenge_redirect?to=...`
- **Title:** "Just a moment..."
- **Body:** "Performing security verification"
- **Screenshot:** Cloudflare Turnstile checkbox widget
- **No chat input elements found at all**

### Turnstile Click Attempt
Created `test_turnstile_strategies.py` to try clicking the Turnstile checkbox inside the iframe:
- Found iframe at `challenges.cloudflare.com`
- No checkbox or label elements accessible inside the sandboxed iframe
- `bounding_box()` timed out on the iframe locator
- Challenge NOT resolved

### Result
**FAILED.** `playwright-stealth` alone is insufficient against Cloudflare's Turnstile on claude.ai. The Chromium headless fingerprint is detected despite evasion patches.

**Lesson:** The arms race with Chromium-based stealth against Cloudflare is a losing battle. C++-level browser patches are needed.

---

## Headless Mode — Camoufox Integration (SUCCESS)

### Research
Read both Cloudflare bypass research documents:
- `docs/Bypassing Cloudflare with Playwright 2026.md`
- `docs/Bypassing Cloudflare Playwright Research 2026.md`

Key findings:
- **Camoufox** is the strongest open-source option for Playwright-based Cloudflare bypass
- It patches Firefox at the C++ level with anti-fingerprinting modifications
- Provides isolated Playwright sandbox, native input handling
- Compatible with standard Playwright API (Browser, Context, Page)

### V1 Comparison
V1 used SeleniumBase UC (undetectable Chrome) mode which was **detected and terminated by ALL providers** (Claude, Gemini, Perplexity, GPT). V1's own recommendation was to migrate to Playwright.

### Camoufox Setup
```bash
pip install 'camoufox[geoip]'  # 0.4.11 + 29 dependencies
python -m camoufox fetch       # 298MB Firefox binary download
```

### Verification Test
Created `test_camoufox.py`:
```python
async with AsyncCamoufox(headless=True, humanize=True) as browser:
    ctx = await browser.new_context(viewport={'width': 1920, 'height': 1080})
    await ctx.add_cookies(storage_state["cookies"])
    page = await ctx.new_page()
    await page.goto("https://claude.ai/new")
```

**Result: SUCCESS**
- URL: `https://claude.ai/new` (no challenge redirect!)
- Title: "Claude"
- Body shows sidebar, chat history
- Chat input found: `div.ProseMirror[contenteditable="true"]`
- **No Cloudflare challenge at all — passed silently**

### Browser Manager Rewrite

Rewrote `browser_manager.py._launch()` to use Camoufox as primary engine:

**Architecture:**
- `_launch()` → tries `_launch_camoufox()` first, falls back to `_launch_chromium()`
- `_launch_camoufox()`: Uses `AsyncCamoufox(headless=True, humanize=True)`, creates Playwright Firefox context, injects cookies from storage_state JSON via `ctx.add_cookies()`
- `_launch_chromium()`: Original Chromium + `playwright-stealth` path, kept as fallback
- `close()`: Updated to handle Camoufox context manager cleanup via `__aexit__`

**Key API detail:** Camoufox (Firefox) doesn't support Playwright's `storage_state=` kwarg in context constructor. Cookies must be injected manually via `ctx.add_cookies(state["cookies"])`.

### Removed Features
- Removed `background: bool` field entirely from `BrowserConfig`
- Removed all `background` parameter references from test file (10 functions + CLI)
- Simplified CLI to `--visible` flag only

### Test Results
- **220 unit tests:** ALL PASSING
- **10/10 live integration tests:** ALL PASSING HEADLESS

| Test                      | Status | Time  |
| ------------------------- | ------ | ----- |
| Chat Single Turn          | PASS   | 22.1s |
| Chat Multi-Turn           | PASS   | 54.2s |
| Chat Thinking             | PASS   | 28.2s |
| Data JSON Generation      | PASS   | 38.6s |
| Data BREAK Prompt         | PASS   | 50.0s |
| Translator Single Chunk   | PASS   | 30.5s |
| Translator Multi-Chunk    | PASS   | 42.3s |
| Translator PDF Upload     | PASS   | 36.8s |
| Translator Multi-Page PDF | PASS   | 94.9s |
| Model Change              | PASS   | 41.2s |

**Total run time:** 438.8s (all headless, zero Cloudflare challenges)

---

## Key Technical Decisions

### Camoufox vs playwright-stealth
| Aspect              | Camoufox                                | playwright-stealth            |
| ------------------- | --------------------------------------- | ----------------------------- |
| Engine              | Firefox (C++ patched)                   | Chromium (JS patches)         |
| Fingerprint evasion | C++ level (WebGL, Canvas, AudioContext) | JS level (navigator, plugins) |
| Cloudflare bypass   | ✅ Silent pass                           | ❌ Turnstile challenge         |
| Install size        | ~300MB Firefox binary                   | ~50KB Python package          |
| API                 | Standard Playwright Browser             | Standard Playwright Context   |

**Decision:** Camoufox as primary, playwright-stealth as fallback for environments where Camoufox isn't installed.

### Cookie Injection (Firefox vs Chromium)
- **Chromium path:** `browser.new_context(storage_state="path/to/state.json")` works natively
- **Firefox/Camoufox path:** Must use `ctx.add_cookies(json.loads(state_file)["cookies"])` since Camoufox's persistent context doesn't accept `storage_state` kwarg
- Both paths produce the same result (authenticated session)

### Response Interception
- `BrowserManager._on_response()` captures API responses matching `/api/organizations/.../chat_conversations`
- Works identically on both Camoufox (Firefox) and Chromium paths since response interception is a Playwright-level feature, not browser-engine specific

---

## Files Modified

| File                                              | Changes                                                                                                                                 |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `src/universal_agents/core/config.py`             | Removed `background: bool` field                                                                                                        |
| `src/universal_agents/browser/browser_manager.py` | Complete `_launch()` rewrite: Camoufox primary + Chromium fallback, `close()` updated for Camoufox cleanup, added `_camoufox` attribute |
| `tests/integration/test_v1_claude_jobs_live.py`   | Removed all `background` params, 10 functions + CLI simplified                                                                          |

## Files Created

| File                                             | Purpose                                                      |
| ------------------------------------------------ | ------------------------------------------------------------ |
| `tests/integration/diagnose_headless.py`         | Diagnostic: capture URL, title, body, screenshot in headless |
| `tests/integration/test_turnstile_strategies.py` | Attempted Turnstile checkbox click (failed)                  |
| `tests/integration/test_camoufox.py`             | Camoufox headless verification against claude.ai             |

---

## Dependencies Added

| Package              | Version | Purpose                                   |
| -------------------- | ------- | ----------------------------------------- |
| `camoufox[geoip]`    | 0.4.11  | Anti-detect Firefox browser               |
| `playwright-stealth` | 2.0.2   | Context-level stealth (Chromium fallback) |

---

## Gemini Provider Implementation

### Research — V1 Architecture
V1 Gemini agent used SeleniumBase with UC mode:
- **URL:** `https://gemini.google.com`
- **Auth:** Copied Chrome profile directory for Google login
- **Input:** `div[contenteditable='true']` (word-by-word typing with delays)
- **Submit:** `button[aria-label*='Send']`
- **Response:** `.markdown.markdown-main-panel` (count-based multi-turn detection)
- **Thinking:** 3 strategies — API interception (`/generate`, `/stream`), UI button click, pattern matching
- **V1 test results:** 9/9 comprehensive (100%), 17/18 realistic (94.4%)
- **V1 known issue:** Long/complex responses can exceed 120s timeout

### V2 Adaptation
The v2 Gemini provider was already stubbed out with the correct architecture:
- `GeminiChatAgent` extends `BaseBrowserAgent` (shared chat flow)
- `GeminiConfig` extends `BrowserConfig` with Gemini-specific fields
- `GEMINI_SELECTORS` defined in `selectors.py` with selectors from v1
- `gemini_fetch_override.js` for thinking extraction via API interception

Key differences from Claude:
- Gemini uses `contenteditable div` instead of ProseMirror editor
- Response selector: `.markdown.markdown-main-panel` instead of `.standard-markdown`
- API interception: `/generate` and `/stream` endpoints instead of `/chat_conversations`
- Auth: Google account cookies instead of Anthropic session cookies
- No Cloudflare challenge (Google handles its own bot detection differently)

### Implementation Details

#### DOM Discovery & Hydration Wait
The initial Gemini test (chat_single) failed with "No new response appeared within 120s (count stayed at 0)". Diagnosis revealed:

1. **Angular hydration delay.** Gemini's UI takes ~10-15s to hydrate after `domcontentloaded`. Standard CSS selectors fail until the Angular app finishes bootstrapping:
   - Before hydration: raw `<textarea>` element appears
   - After hydration: Angular replaces it with `<div contenteditable="true" aria-label="Enter a prompt for Gemini">`

2. **Send button is hidden.** `button[aria-label='Send message']` only becomes visible after text is entered. The `click_submit()` fallback to Enter key works as a backup.

3. **Response elements are standard CSS.** No shadow DOM — contrary to initial diagnosis (which ran before hydration completed). Working selectors:
   - `.response-container-content .markdown` → pure response text
   - `.markdown.markdown-main-panel` → equivalent
   - `model-response` → includes "Gemini said" prefix
   - `message-content` → body text

**Fix applied:** Added `page.wait_for_selector("div[contenteditable='true']", state="visible", timeout=30_000)` in `_post_navigate()` for both `GeminiChatAgent` and `GeminiDataAgent`.

#### Response Selector Consistency
The `ResponseDetector` had a bug: `count_responses()` and `wait_for_new_response()` each called `_find_working_selector()` independently. Between these calls, a broader selector (`model-response`) could match while the specific one (`.response-container-content .markdown`) hadn't rendered yet, causing "Gemini said" and "Show thinking" prefixes in extracted text.

**Fix applied:** `count_responses()` now returns `(count, selector_used)` and `wait_for_new_response()` accepts a `selector_hint` parameter to ensure the same selector is used throughout the turn.

#### API URL Matching
Gemini's API endpoint is `StreamGenerate` (capital S/G), not `/generate`/`/stream` as assumed from v1. The `_on_response()` handler was updated to match `"StreamGenerate"` and `"batchexecute"` URL patterns. Note: Gemini's `batchexecute` responses use Google's custom protobuf-wrapped JSON format, which `response.json()` cannot parse — thinking extraction via API interception remains non-functional for now.

#### Updated Selectors (2025-06 Angular UI)
```python
input:    ["div[contenteditable='true'][aria-label*='prompt']", ...]
submit:   ["button[aria-label='Send message']", ...]
response: [".response-container-content .markdown", ".markdown.markdown-main-panel", ...]
```

### Test Results — 5/5 PASS

| #   | Test                      | Status | Time  | Details                                              |
| --- | ------------------------- | ------ | ----- | ---------------------------------------------------- |
| 1   | Chat Single Turn          | ✅ PASS | 22.2s | Response: "4" (clean)                                |
| 2   | Chat Multi-Turn (3 turns) | ✅ PASS | 66.3s | Context: 42 → 84 → 100                               |
| 3   | Chat Thinking             | ✅ PASS | 34.6s | Answer: 150, thinking not captured                   |
| 4   | Data JSON                 | ✅ PASS | 39.9s | `{"name":"DataPayload","processed":true,"count":42}` |
| 5   | Data BREAK                | ✅ PASS | 38.1s | Full Q/A/reasoning JSON extracted                    |

**Total:** 201s across 5 tests, all headless via Camoufox.

### Known Limitations
- **Thinking extraction:** 0 raw API responses captured. Gemini uses `batchexecute` with Google's protobuf-wrapped JSON that `response.json()` can't parse. The fetch override JS also fails to intercept — Gemini's Angular app may use XHR or a different fetch mechanism.
- **Response timing:** Each test takes 22-40s due to Angular hydration (~3-4s) + response generation (~10-14s) + stabilization checks (3 × 2s intervals).
