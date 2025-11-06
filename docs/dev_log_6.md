# Development Log 6 — universal-agent_v2

**Date:** 2026-04-01  
**Author:** Development Session Notes  
**Previous commit:** `adc5f58`  

---

## Overview

This log covers the implementation of a compiled kendo **book** translator agent (PDF page-by-page, not SRT) and the critical fix for clipboard contamination that had been silently destroying all translation output. The session started by diagnosing why a full 11-page test run produced garbage output, found the root cause in the response detection clipboard path, implemented a comprehensive fix across three layers, and validated the fix with fresh and resume tests.

Previous state: 501 tests, SRT translation working, book translator concept but no compiled agent.  
Final state: Book translator compiled and tested (11/11 pages), clipboard contamination fixed, resume flow fully operational, JSON-based translation cache replacing fragile markdown parsing.

---

## 1. Kendo Book Translator — New Compiled Agent

### Problem

Needed a page-by-page PDF book translator (different from the existing SRT translator). The book translator:
- Splits a multi-page PDF into individual pages
- Uploads each page as a PDF image to Gemini
- Sends a trilingual translation prompt with kendo dictionary
- Manages multi-turn conversations with conversation splitting
- Supports resume from progress state

### New Modules

#### `src/universal_agents/core/pdf_utils.py` (72 lines)

PDF splitting utility using PyMuPDF (`fitz`):
- `get_page_count(pdf_path)` — returns page count
- `split_pdf_to_pages(pdf_path, output_dir, page_prefix)` — splits multi-page PDF into individual single-page PDFs with zero-padded filenames

#### `src/universal_agents/core/book_prompts.py` (164 lines)

Trilingual book translation prompt builder:
- `load_dictionary(dict_path)` / `load_translation_prompt(prompt_path)` — file loaders
- `build_book_system_prompt(dict_path, prompt_path, book_title)` — first-turn prompt with full dictionary + translation instructions + "Here is the first page"
- `build_book_continue_prompt(page_num, total_pages)` — subsequent page prompts within the same conversation
- `build_book_new_conversation_prompt(dict_path, prompt_path, book_title, last_page, total_pages)` — full re-prompt with dictionary for conversation splits, includes context about previously translated pages
- `_default_translation_prompt()` — fallback prompt if no prompt file provided

#### `scripts/compile_kendo_book_translator.py` (844 lines)

Compile script that generates a self-contained book translator agent package at `compiled_agents/gemini_kendo_book_translator/`. The generated `agent.py` includes:
- PDF splitting (reuses `pdf_utils.split_pdf_to_pages()`)
- Page-by-page upload + translation
- JSON-based translation cache for robust resume
- Progress state tracking
- `--pages` argument for translating subsets
- `--visible` flag for headed browser mode
- Markdown output generation from cached translations

---

## 2. Clipboard Contamination Bug — Root Cause & Fix

### Problem: Garbage Output

A full 11-page test run completed "successfully" (all chunks marked complete) but the output file was 24,589 lines of garbage. Investigation revealed that chunks 2–10 all contained exactly **57,125 characters** — each starting with the system prompt text.

### Root Cause

The response detection pipeline uses two clipboard operations:
1. **Prompt delivery:** `_paste_to_input()` writes the translation prompt to clipboard via `pbcopy`, then `Cmd+V` to paste into Gemini's input
2. **Response extraction:** `_copy_response_via_button()` clicks Gemini's "Copy" button on the response, then reads clipboard via `pbpaste`

The bug: If the copy button click fails silently (button not found, click missed, etc.), `pbpaste` returns the **prompt text** still in the clipboard from step 1 — not the LLM's actual response. The 57,125-character "responses" were actually the system prompt echoed back through the stale clipboard.

### Fix: Sentinel-Based Clipboard Verification

**File:** `src/universal_agents/browser/response_detector.py` (+116 lines)

Added three new methods and rewrote `_copy_response_via_button()`:

| Method                        | Purpose                                                                                                                            |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `_read_clipboard()`           | Static method; reads clipboard via `pbpaste` (macOS) or `xclip -o` (Linux)                                                         |
| `_clear_clipboard()`          | Static method; writes sentinel `"__CLIPBOARD_CLEARED__"` to clipboard                                                              |
| `_copy_response_via_button()` | **Rewritten:** (1) Clear clipboard to sentinel, (2) Click copy button, (3) Verify clipboard changed from sentinel before returning |

The sentinel approach guarantees that if the copy button click fails, the method returns `None` (falling back to `text_content()`) instead of returning stale clipboard data.

### Before vs After

| Scenario                   | Before                                  | After                                                    |
| -------------------------- | --------------------------------------- | -------------------------------------------------------- |
| Copy button works          | Returns response via `pbpaste` ✅        | Returns response via `pbpaste` (verified not sentinel) ✅ |
| Copy button fails silently | Returns **prompt text** via `pbpaste` ❌ | Returns `None`, falls back to `text_content()` ✅         |
| Clipboard not supported    | Crashes or returns empty                | Returns `None`, falls back ✅                             |

---

## 3. Gemini Data Agent — Clipboard Paste for Long Messages

### Problem

The previous `_send_message()` uploaded long messages as `.txt` files via Gemini's file upload mechanism. This was unreliable — the file upload had 3 fallback strategies and still failed intermittently.

### Solution

**File:** `src/universal_agents/providers/gemini/data.py` (+45 lines, -4)

Replaced `_upload_file_to_gemini()` as the primary long-message strategy with `_paste_to_input()`:
- Uses `pbcopy` (macOS) or `xclip` (Linux) to write message to OS clipboard
- Clicks the input element
- Presses `Cmd+V` / `Ctrl+V` to paste
- Falls back to `type_text()` on failure

The file upload method `_upload_file_to_gemini()` is kept but no longer called by default — clipboard paste is simpler and more reliable.

---

## 4. Translator Agent — `@Model` Prefix & Resume Fixes

### Problem

Three issues in the Gemini translator agent:
1. **Model selection via dropdown was unreliable** — the mode picker DOM sometimes changed, selectors broke
2. **Resume didn't reset turn counter** — on resume, `turn_in_conversation` kept the old value, but the browser session is new. This caused the system prompt to not be sent (model thought it wasn't the first turn)
3. **File upload prompt text was typed character-by-character** — slow for the 8900-word system prompt

### Solution

**File:** `src/universal_agents/providers/gemini/translator.py` (+61 lines, -11)

#### `_type_model_prefix(page)` — New Method
Instead of clicking through the mode picker dropdown, type `@Pro` (or `@Thinking`) character-by-character into the input field:
```python
prefix = f"@{model_name.capitalize()}"
await input_el.press_sequentially(prefix, delay=80)
await page.wait_for_timeout(1500)  # Wait for autocomplete popup
await page.keyboard.press(" ")     # Confirm selection
```
This triggers Gemini's built-in `@mention` autocomplete, which is more reliable than navigating the DOM dropdown.

Called on `turn_in_conversation == 0` in both `translate_text()` and `translate_file()`.

#### Resume Turn Counter Reset
`init_progress()` now resets `turn_in_conversation = 0` and `lines_in_conversation = 0` on resume. The old values from the progress file are irrelevant because the browser session is fresh — there's no existing conversation to continue.

#### Clipboard Paste for Upload Prompts
In `upload_file()`, prompts >100 words are now pasted via `_agent._paste_to_input()` instead of typed character-by-character. The 8900-word system prompt now loads in ~1 second instead of 10+ minutes.

---

## 5. Compiled Agent — JSON Translation Cache

### Problem

The previous resume approach parsed the markdown output file with regex to recover existing translations. This was fragile:
- Regex could fail on unexpected formatting
- If the output had garbage data (from the clipboard bug), resume loaded garbage
- No separation between "source of truth" and "display format"

### Solution

The compiled agent's `translate_book()` now uses a dedicated JSON translation cache:

```python
# Cache path: progress/Men 0_translations.json
# Format: {"1": "Page 1\n\n...\n=== END OF PAGE 1 ===", "2": "..."}

def _load_translation_cache(cache_path):
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    return {}

def _save_translation_cache(cache_path, translations):
    cache_path.write_text(json.dumps(translations, ensure_ascii=False, indent=2))
```

- Cache is saved after **every page** for crash resilience
- Cache is the source of truth for resume — not the markdown output
- Output markdown is regenerated from cache at the end
- `_load_existing_translations()` (the fragile markdown parser) was removed entirely

### Resume Flow (Fixed)
1. Load progress JSON → get `completed_chunks`
2. Load translation cache JSON → get existing translations dict
3. `is_first_turn_in_convo = True` always at start
4. Skip completed pages
5. First non-skipped page gets full system prompt + dictionary
6. After each page: save translation to cache + update progress

---

## 6. Problems and Solutions Summary

| #   | Problem                                   | Root Cause                                                                                                   | Solution                                                                                                    | Impact                                      |
| --- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| 1   | 11-page run produces 24K lines of garbage | `_copy_response_via_button()` reads stale clipboard (prompt text from `pbcopy`) when copy button click fails | Sentinel-based clipboard clearing: write `"__CLIPBOARD_CLEARED__"` before clicking, verify it changed after | **CRITICAL** — all translations were broken |
| 2   | Resume doesn't send system prompt         | `turn_in_conversation` preserved from old session, but browser session is new                                | Reset `turn_in_conversation = 0` on resume                                                                  | Resume produced untranslated output         |
| 3   | Resume loads garbage translations         | Markdown parser regex extracted from garbage output file                                                     | JSON translation cache replaces markdown parsing                                                            | Resume propagated garbage from broken runs  |
| 4   | Model selection via dropdown unreliable   | Mode picker DOM selectors changed                                                                            | `@Pro` typed into input → autocomplete popup → Space to confirm                                             | More robust than DOM navigation             |
| 5   | 8900-word prompt typed char-by-char       | `type_text()` is the default for all prompt text                                                             | Clipboard paste via `pbcopy` + `Cmd+V` for prompts >100 words                                               | ~1s vs 10+ minutes                          |
| 6   | File upload strategy unreliable           | 3-strategy fallback still fails intermittently                                                               | Clipboard paste as primary strategy for long messages                                                       | Simpler and more reliable                   |

---

## 7. Test Results

### Fresh Test (Pages 1-2, `--visible`)
| Page | Time  | Response Chars                  | Method                                        |
| ---- | ----- | ------------------------------- | --------------------------------------------- |
| 1    | 57.1s | 516 (formatted via copy button) | `@Pro` → file upload → clipboard paste prompt |
| 2    | 41.9s | 109 (formatted via copy button) | file upload → type prompt                     |

- Model confirmed: `pro`
- Sentinel clipboard approach verified working

### Resume Test (Pages 1-4, `--visible`)
| Event        | Detail                                                          |
| ------------ | --------------------------------------------------------------- |
| Cache loaded | 2 cached page translations                                      |
| Pages 1-2    | Skipped (already completed)                                     |
| Page 3       | `@Pro` typed, system prompt sent (8900 words), 50.1s, 250 chars |
| Page 4       | Continued in same conversation (turn 2), 62.4s, 869 chars       |
| Output       | 4 pages written correctly                                       |

### Full Run (Pages 5-11, headless)
- All 7 remaining pages translated via `@Thinking` model
- Page times: 44.0s–51.6s each
- Response sizes: 3710–4145 chars
- 11/11 pages complete

---

## 8. Files Changed

### New Files
| File                                        | Lines | Purpose                                           |
| ------------------------------------------- | ----- | ------------------------------------------------- |
| `src/universal_agents/core/pdf_utils.py`    | 72    | PDF splitting via PyMuPDF                         |
| `src/universal_agents/core/book_prompts.py` | 164   | Trilingual book translation prompts               |
| `scripts/compile_kendo_book_translator.py`  | 844   | Book translator compile script                    |
| `docs/compiled-agent-dev-guideline.md`      | —     | Guideline for compiled agent development          |
| `docs/dev_log_1-5.md`                       | —     | Combined problems/solutions summary from logs 1-5 |

### Modified Files
| File                                                  | Lines Changed | Change                                                                                            |
| ----------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------- |
| `src/universal_agents/browser/response_detector.py`   | +116          | Sentinel clipboard (`_read_clipboard`, `_clear_clipboard`, rewritten `_copy_response_via_button`) |
| `src/universal_agents/providers/gemini/data.py`       | +45, -4       | `_paste_to_input()` replaces file upload as primary long-message strategy                         |
| `src/universal_agents/providers/gemini/translator.py` | +61, -11      | `_type_model_prefix()`, resume turn counter reset, clipboard paste for upload prompts             |

### Generated (compiled agent)
| Directory                                       | Contents                                                                                                                                                  |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `compiled_agents/gemini_kendo_book_translator/` | `agent.py`, `config.json`, `requirements.txt`, `README.md`, `source_spec.json`, `kendo_dict.md`, translation prompt, storage, progress, pages, translated |

---

## 9. Architecture Notes

### Clipboard Flow (After Fix)
```
Prompt Delivery:
  pbcopy(prompt) → Cmd+V paste → prompt in input + clipboard = prompt

Response Extraction:
  pbcopy("__CLIPBOARD_CLEARED__") → click Copy button → pbpaste()
  ├── If clipboard ≠ sentinel → return response text ✅
  └── If clipboard = sentinel → copy failed → return None → fallback to text_content()
```

### Translation Cache vs Output
```
Source of truth:    progress/{book_id}_translations.json  (JSON, page-keyed)
Display output:     translated/{book_id}_trilingual.md   (Markdown, generated from cache)
Progress tracking:  progress/{book_id}_progress.json     (completed chunks, conversation state)
```

### `@Model` Prefix vs Dropdown
```
Old: Click mode picker button → open menu → find matching menuitem → click → verify
New: Type "@Pro" char-by-char → Gemini autocomplete popup → Space to confirm
```
The `@mention` approach is more robust because it uses Gemini's built-in autocomplete rather than relying on specific DOM selectors for the mode picker UI.

---

## 10. Headless Paste Fix — Silent Failure in Camoufox (`154bef2`)

### Problem

The full 66-page headless run (Men 1) completed, but the first test of a new headless run showed the system prompt was **not being delivered** to Gemini. The translation output was produced without kendo dictionary context, resulting in generic translations.

### Root Cause

`_paste_to_input()` uses `pbcopy` (writes to macOS clipboard) + `Meta+v` (Cmd+V) to paste into the input field. In **visible** Camoufox, this works because the browser has access to the system clipboard. In **headless** Camoufox, `Meta+v` silently does nothing — the clipboard paste fails without any error or exception. The prompt text is written to the OS clipboard, but the headless browser cannot read it.

This is different from the clipboard contamination bug (Section 2): that bug was about *reading* stale clipboard data back. This bug is about the *write* side — the text never reaches the input field.

### Solution

**File:** `src/universal_agents/providers/gemini/data.py` (+84 lines)

Three layers of defense:

#### Layer 1: `_verify_input_has_content(page, min_chars=50)`
After any text entry attempt, reads back the input field's `text_content` and checks it has at least `min_chars` characters. Returns `True` if content is present, `False` if empty/too short.

```python
async def _verify_input_has_content(self, page, min_chars: int = 50) -> bool:
    input_el = page.locator("div[contenteditable='true']").first
    content = await input_el.text_content()
    return bool(content and len(content.strip()) >= min_chars)
```

#### Layer 2: `_paste_to_input()` — Now Returns `bool`
After pasting via `pbcopy` + `Meta+v`, calls `_verify_input_has_content()`. Returns `False` if verification fails (input still empty), allowing the caller to try alternative methods.

#### Layer 3: `_js_insert_text(page, message)` — New JS Fallback
Uses `document.execCommand('insertText')` to insert text directly into the input field via JavaScript — bypasses the OS clipboard entirely. Works reliably in both visible and headless modes.

```python
async def _js_insert_text(self, page, message: str) -> bool:
    input_el = page.locator("div[contenteditable='true']").first
    await input_el.focus()
    await page.evaluate("(text) => document.execCommand('insertText', false, text)", message)
    return await self._verify_input_has_content(page, min_chars=50)
```

#### Updated `_send_message()` Chain
```
1. Try _paste_to_input() (pbcopy + Meta+v)
2. Verify input has content
3. If empty → try _js_insert_text() (document.execCommand)
4. Verify input has content
5. If still empty → fall back to type_text() (character-by-character)
```

**File:** `src/universal_agents/providers/gemini/translator.py` (+19 lines)

#### Pre-Submit Assertion in `translate_file()`
Before clicking Send on the first turn (where system prompt + dictionary is sent), verifies the input field contains the expected prompt text. Raises `RuntimeError` if the input is empty, preventing blank-prompt submissions.

```python
# CRITICAL PRE-SUBMIT CHECK — first turn must have system prompt in input
if is_first_turn:
    has_content = await self._agent._verify_input_has_content(page, min_chars=50)
    if not has_content:
        raise RuntimeError("System prompt not in input field — refusing to submit")
```

### Headless Detection Flow
```
Headless mode:
  _paste_to_input() → pbcopy OK → Meta+v silently fails → verify → EMPTY!
  ↓
  _js_insert_text() → document.execCommand('insertText') → verify → Content present ✅
  ↓
  Continue with translation

Visible mode:
  _paste_to_input() → pbcopy OK → Meta+v works → verify → Content present ✅
  ↓
  Continue directly (JS fallback not needed)
```

---

## 11. Translation Output Quality Review

### Men 0 (11 pages, visible mode, `@Pro`)
- **Format:** Mixed — early pages (1-4) have compact paragraphs without clean triplet separation; later pages (5-11) have proper sentence-by-sentence JA/EN/ZH triplets with `---` separators
- **Quality:** Good terminology use, kendo terms preserved
- **Artifacts:** Minimal — no citation markers

### Men 1 (66 pages, headless, `@Thinking`)
- **Format:** Good sentence-by-sentence triplets with `---` separators between each set
- **Artifacts identified for cleanup:**

| Artifact | Example | Frequency |
| --- | --- | --- |
| `[cite_start]` / `[cite: N]` markers | `[cite_start]剣道[cite: 1]` | Throughout all 66 pages |
| `+1` / `+2` source markers | `+1` appearing on its own line | Occasional |
| `Export to Sheets` text | Gemini UI artifact leaking into copy | Rare |

### Cleanup Needed for Triplet Extraction
To reliably extract (JA, EN, ZH) triplets from the output:
1. Strip `[cite_start]` and `[cite: N]` regex patterns
2. Strip `+1`/`+2` source markers (standalone lines matching `^\+\d+$`)
3. Strip `Export to Sheets` UI artifacts
4. Normalize `---` separators between triplets
5. Validate each triplet has exactly 3 groups (JA, EN, ZH)

---

## 12. SRT Translator — Infrastructure Update

Ported key improvements from the book translator compile script to the SRT translator compile script (`scripts/compile_kendo_translator.py`).

### Changes Ported

| Feature | Before | After |
| --- | --- | --- |
| `--login` command | Not available | `capture_login()` with Google accounts redirect |
| `_save_cookies()` | Inline try/except in verify_login | Dedicated helper using `ctx.storage_state()` |
| `verify_login()` | Waited on Gemini page only | Redirects to Google accounts, then navigates to Gemini |
| Translation cache | `all_translations` list, lost on crash | JSON cache (`_load_translation_cache` / `_save_translation_cache`), saved after each chunk |
| Rate limit handling | `return None` silently | Saves translation cache + prints resume instructions |
| Storage state resolution | Simple `Path.name` lookup | Multi-path fallback matching book translator |

### Library-Level Fixes (Inherited Automatically)
The SRT translator calls `agent.translate_text()` → `self._agent.chat()` → `_send_message()`, so the following library fixes from commit `154bef2` are inherited without any changes to the SRT script:
- Paste verification (`_verify_input_has_content`)
- JS fallback (`_js_insert_text` via `document.execCommand`)
- Updated `_send_message()` chain (paste → verify → JS → verify → type_text)

### Recompilation
Recompiled the SRT translator package at `compiled_agents/gemini_kendo_srt_translator/` with all updates.

---

## 13. Files Changed (Continued)

### Modified Files (this session)
| File | Change |
| --- | --- |
| `src/universal_agents/providers/gemini/data.py` | +84 lines: `_verify_input_has_content()`, `_js_insert_text()`, updated `_paste_to_input()` to return bool, updated `_send_message()` chain |
| `src/universal_agents/providers/gemini/translator.py` | +19 lines: Pre-submit assertion in `translate_file()`, paste verification in `upload_file()` |
| `scripts/compile_kendo_translator.py` | Major rewrite of agent.py template: `--login`, `capture_login()`, `_save_cookies()`, updated `verify_login()`, JSON translation cache, better resume flow |

### Regenerated (compiled agent)
| Directory | Contents |
| --- | --- |
| `compiled_agents/gemini_kendo_srt_translator/` | Recompiled with updated agent.py template, config.json, kendo_dict.md |
