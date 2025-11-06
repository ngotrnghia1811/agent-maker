# Development Log 5 — universal-agent_v2

**Date:** 2026-03-31  
**Author:** Development Session Notes  
**Commits:** `dd9118e` → (this session)  

---

## Overview

This log covers four major areas of work:

1. **Long message handling** — `_send_message()` hook in `BaseBrowserAgent` with provider-specific overrides (Gemini file upload, Claude system clipboard paste)
2. **Claude compiled agent** — New compiled SRT translator agent for Claude, with login verification, paste-based input, and SRT normalization
3. **SRT normalization fixes** — Three iterations of `normalize_srt_text()` to handle split block numbers, trailing digits, and sequential renumbering
4. **SRT quality verification** — Quality checker script and translation results (SRT 002: 225/225 complete, SRT 003: 150/164)

Previous state: 476 tests, `dd9118e`, Gemini kendo SRT translator operational, Claude translator existed but had no compiled agent.  
Final state: 501 tests, long message handling for both providers, Claude compiled agent functional, SRT normalization battle-tested.

---

## 1. Long Message Handling (`_send_message()` Hook)

### Problem

Browser-based agents type messages character-by-character via `dom.type_text()`. For large SRT chunks (1000+ words), this is prohibitively slow — a 7167-word message would take 10+ minutes to type. Each provider needs a different strategy for sending large payloads.

### Solution: `_send_message()` Hook Pattern

**File:** `src/universal_agents/browser/base_browser_agent.py` (130 lines, +16)

Added a `_send_message()` method to `BaseBrowserAgent` that subclasses override:

```python
LONG_MESSAGE_WORD_THRESHOLD = 100

async def _send_message(self, page, message: str) -> None:
    """Send message to chat input. Override for upload/paste strategies."""
    element = await find_element(page, self.SELECTORS.input_selectors)
    await type_text(page, element, message)
```

The `chat()` method now calls `_send_message()` instead of directly calling `find_element` + `type_text`. This lets providers customize how they deliver large messages.

### Gemini: File Upload Strategy

**File:** `src/universal_agents/providers/gemini/data.py` (236 lines, +146)

`GeminiDataAgent` overrides `_send_message()` to upload messages >100 words as `.txt` files via `_upload_file_to_gemini()`. Three fallback strategies:

| Strategy | Method | Selector |
|----------|--------|----------|
| 1. Hidden file button | `set_input_files` on hidden `input[type="file"]` near add-file button | `button[aria-label*="Add file"]` adjacent input |
| 2. Visible file input | `set_input_files` on any visible `input[type="file"]` | Direct DOM query |
| 3. File chooser event | `expect_file_chooser` triggered by clicking the main add-file button | Event-based |

Each strategy writes the message to a `tempfile` `.txt`, uploads it, then falls through to the next on failure.

### Claude: System Clipboard Paste

**File:** `src/universal_agents/providers/claude/data.py` (150 lines, +66)

`ClaudeDataAgent` overrides `_send_message()` to paste messages >1000 words via system clipboard:

```python
LONG_MESSAGE_WORD_THRESHOLD = 1000

async def _paste_long_message(self, page, message: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["pbcopy"], input=message.encode("utf-8"), check=True)
    else:
        subprocess.run(["xclip", "-selection", "clipboard"],
                       input=message.encode("utf-8"), check=True)
    
    input_el = await find_element(page, self.SELECTORS.input_selectors)
    await input_el.click()
    mod_key = "Meta" if sys.platform == "darwin" else "Control"
    await page.keyboard.press(f"{mod_key}+v")
```

**Why not `navigator.clipboard.writeText()`?** Browser clipboard API requires explicit permissions not available in automation contexts (Camoufox). The `navigator.clipboard.writeText()` call silently fails — the paste never happens and the agent hangs waiting for a response.

**Why `LONG_MESSAGE_WORD_THRESHOLD = 1000` (not 100)?** Claude's ProseMirror editor handles typing up to ~1000 words reasonably fast. Only very large SRT chunks need the paste shortcut.

### Test Coverage

**File:** `tests/unit/test_send_message.py` (297 lines, 15 tests) — NEW

| Test Class | Tests | Covers |
|------------|-------|--------|
| `TestBaseSendMessage` | 5 | Default type_text behavior, threshold attribute, short/long routing |
| `TestGeminiSendMessage` | 5 | Upload invocation for long messages, fallback to type for short, threshold=100 |
| `TestClaudeSendMessage` | 5 | Paste invocation for long messages, threshold=1000, platform-specific clipboard |

---

## 2. Claude Compiled Agent

### Problem

The Gemini kendo SRT translator existed as a compiled agent package, but no equivalent existed for Claude. Claude's browser automation has different requirements: ProseMirror input, different selectors, different login verification, and the paste-based input mechanism.

### Solution: Claude Compile Script + Agent Package

**File:** `scripts/compile_kendo_translator_claude.py` (445 lines) — NEW  
**Output:** `compiled_agents/claude_kendo_srt_translator/`

The compile script generates a self-contained Claude SRT translator agent with:
- Claude-specific selectors and configuration  
- Login verification via ProseMirror editor detection
- System clipboard paste for long messages
- SRT normalization via `normalize_srt_text()`
- Conversation line tracking for splitting

### Key Implementation Challenges

#### Login Verification Fix

**Problem:** The initial `verify_login()` checked for ProseMirror editor presence immediately after page load. On Claude, the editor loads asynchronously — the check failed before the page was ready.

**Solution:** Added explicit navigation + `networkidle` wait + 30-second ProseMirror polling:

```python
async def verify_login(self):
    page = await self._ensure_ready()
    await page.goto("https://claude.ai/new", wait_until="networkidle")
    # Poll for ProseMirror editor up to 30s
    for _ in range(30):
        editor = await page.query_selector('[contenteditable="true"].ProseMirror')
        if editor:
            return True
        await asyncio.sleep(1)
    return False
```

#### First Chunk Hang (7167 Words)

**Problem:** The first SRT chunk was 7167 words. Even with word-by-word typing, this took 10+ minutes and sometimes caused timeouts or browser instability.

**Solution:** Implemented paste-based input (see §1 Claude section). The 7167-word message now loads instantly via system clipboard.

#### File Upload → System Clipboard Migration

**Problem (iteration 1):** Initially implemented file upload using `set_input_files` on a hidden `<input type="file">` element + dispatching change/input events. This worked for SRT 002 but failed intermittently for SRT 003's first prompt.

**Problem (iteration 2):** Switched to `navigator.clipboard.writeText()` + `Cmd+V`. The clipboard API silently failed in Camoufox — clipboard permissions aren't available in automation contexts. The paste never happened; agent hung waiting for a response for 10+ minutes.

**Solution (iteration 3):** System clipboard via `subprocess.run(["pbcopy"])` + `page.keyboard.press("Meta+v")`. This bypasses browser permissions entirely by using the OS-level clipboard. Confirmed working: "Long message pasted via system clipboard (7167 words)".

---

## 3. SRT Normalization Fixes

### Problem

Claude's SRT output had several formatting issues not seen with Gemini:
- Block numbers after 9 split across lines (e.g., "1\n\n0" instead of "10")
- Single-digit cycling (0, 1, 2, 3... instead of 10, 11, 12, 13...)
- Trailing standalone digits appended to previous block's text
- Stray `+N` markers from continuation prompts

### Solution: `normalize_srt_text()` Enhancements

**File:** `src/universal_agents/core/srt_utils.py` (259 lines, +62)

Three iterations of fixes, all in `normalize_srt_text()`:

#### Iteration 1: Split Block Numbers with Blank Line

Claude outputs block number 10 as:
```
(end of block 9 text)
1

0
00:01:23,456 --> 00:01:25,789
```

**Regex fix:** Merge the split digits back together:
```python
re.sub(
    r"(\S)\n(\d+)\n\n(\d+)\n(\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->)",
    r"\1\n\n\2\3\n\4",
    text
)
```

#### Iteration 2: Trailing Standalone Digits

A different variant where Claude appends the tens digit as a trailing line in the previous block's text. Block 9's text ends with a lone "1" before block 0 (which should be block 10):

```
Block 9 text here
1

0
00:01:23,456 --> ...
```

**Post-parse fix:** After SRT parsing, strip trailing standalone-digit lines from each block's text:
```python
while block_lines and re.match(r"^\d+$", block_lines[-1].strip()):
    block_lines.pop()
```

#### Iteration 3: Sequential Renumbering

Even after fixing split digits, Claude sometimes outputs cycling single digits (0, 1, 2, 3 instead of 10, 11, 12, 13).

**Post-parse fix:** After parsing, forcibly renumber all blocks sequentially:
```python
for i, block in enumerate(blocks, 1):
    block.index = i
```

### Test Coverage

**File:** `tests/unit/test_srt_utils.py` (320 lines, +133) — 5 new tests added

| Test | Covers |
|------|--------|
| `test_split_block_numbers_two_digit` | "1\n\n0" → "10" merge for blocks 10-12 |
| `test_split_block_numbers_larger` | Three-digit splits (e.g., "1\n\n00" for block 100) |
| `test_single_digit_cycling` | 0,1,2 cycling renumbered to 10,11,12 |
| `test_renumber_sequential` | Non-sequential numbers (5,10,15) → (1,2,3) |
| `test_trailing_digit_strip` | Lone digits at end of block text stripped |

Total `test_srt_utils.py`: 38 tests (was ~12).

---

## 4. SRT Quality Verification

### Quality Checker Script

**File:** `scripts/check_srt_quality.py` (98 lines) — NEW

CLI tool that validates translated SRT files:
- Block count and sequential numbering
- Timestamp ordering and gap detection
- Empty block detection
- Stray digit detection

### Translation Results

| SRT File | Provider | Blocks Translated | Total Blocks | Status |
|----------|----------|-------------------|--------------|--------|
| SRT 002 | Claude | 225 | 225 | ✅ COMPLETE |
| SRT 003 | Claude | 150 | 164 | ⚠️ 14 missing (end, conversation limit) |

**SRT 002:** Perfect translation — all 225 blocks, sequential numbering, no stray digits, no empty blocks.

**SRT 003:** 150/164 blocks starting from the beginning (00:00:04,680). The 14 missing blocks are from the end due to Claude's conversation length limits — not from the beginning (which was the previous bug when file upload failed and translation started mid-file at 00:05:44).

---

## 5. Utility Scripts

Several probe/test scripts created during debugging:

| Script | Purpose |
|--------|---------|
| `scripts/compile_kendo_translator_claude.py` | Claude SRT translator compile script |
| `scripts/check_srt_quality.py` | SRT quality validation CLI tool |
| `scripts/probe_claude.py` | Claude UI element probing |
| `scripts/probe_claude_upload.py` | Claude file upload mechanism testing |
| `scripts/probe_gemini_login.py` | Gemini login state probing |
| `scripts/probe_gemini_ui.py` | Gemini UI structure probing |
| `scripts/probe_gemini_upload.py` | Gemini file upload testing |
| `scripts/test_claude_upload.py` | Claude upload end-to-end test |
| `scripts/test_gemini_auth.py` | Gemini auth verification |
| `scripts/test_gemini_upload.py` | Gemini upload end-to-end test |

---

## 6. Problems and Solutions Summary

| # | Problem | Root Cause | Solution | Iterations |
|---|---------|-----------|----------|------------|
| 1 | Claude file upload unreliable | `set_input_files` + event dispatch intermittent | System clipboard paste via `pbcopy` | 3 |
| 2 | `navigator.clipboard.writeText()` fails | Browser clipboard API requires permissions unavailable in automation | Use OS-level `subprocess.run(["pbcopy"])` instead | 1 |
| 3 | Split block numbers (variant A) | Claude outputs digits with blank line between ("1\n\n0" for 10) | Regex merge before parsing | 1 |
| 4 | Split block numbers (variant B) | Claude appends tens digit as trailing text in previous block | Post-parse strip of standalone trailing digits | 1 |
| 5 | Cycling single-digit block numbers | Claude loses track of numbering after 9 | Sequential renumbering after parsing | 1 |
| 6 | Login verification fails | ProseMirror editor loads asynchronously | Navigate + networkidle + 30s polling | 1 |
| 7 | First chunk hangs (7167 words) | Character-by-character typing too slow | Paste via system clipboard | 1 |
| 8 | SRT 003 starts at 00:05:44 | First prompt upload failed silently | Paste fix resolved; re-run starts from beginning | 1 |
| 9 | Playwright FrameManager crash | `TypeError: Cannot read properties of undefined` — internal bug with Node.js v24 + Camoufox | Intermittent; worked on retry | Known issue |

---

## 7. Test Results

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Unit tests | 476 | 501 | +25 |
| Test files | 27 | 29 | +2 |
| Pass rate | 100% | 100% | — |
| Execution time | ~0.6s | ~0.8s | +0.2s |

**New test files:**
- `tests/unit/test_send_message.py` — 15 tests for `_send_message()` hook (Base, Gemini, Claude)
- `tests/unit/test_srt_utils.py` — 10 new tests added (5 normalize + 5 earlier additions)

**Source metrics:**
- Source lines (src/): 7,127 (was 6,798)
- Test lines (tests/): 10,743 (was 10,313)
- Total Python files: 138 (58 src + 50 tests + 30 scripts/misc)

---

## 8. Files Changed

### Modified (tracked)
| File | Lines | Change |
|------|-------|--------|
| `src/universal_agents/browser/base_browser_agent.py` | 130 | +`_send_message()` hook, `LONG_MESSAGE_WORD_THRESHOLD` |
| `src/universal_agents/core/srt_utils.py` | 259 | +`normalize_srt_text()` split-number merge, trailing-digit strip, renumbering |
| `src/universal_agents/providers/claude/data.py` | 150 | +System clipboard paste, `_paste_long_message()`, threshold=1000 |
| `src/universal_agents/providers/gemini/data.py` | 236 | +`_upload_file_to_gemini()` 3-strategy file upload |
| `src/universal_agents/providers/gemini/translator.py` | 723 | +Model check enhancements |
| `scripts/compile_kendo_translator.py` | — | Updated Gemini compile script |
| `tests/unit/test_srt_utils.py` | 320 | +10 new normalize/renumber tests |

### New (untracked)
| File | Lines | Purpose |
|------|-------|---------|
| `scripts/compile_kendo_translator_claude.py` | 445 | Claude SRT translator compile script |
| `scripts/check_srt_quality.py` | 98 | SRT quality validation tool |
| `tests/unit/test_send_message.py` | 297 | 15 tests for `_send_message()` |
| `scripts/probe_*.py` (5 files) | ~100 each | UI probing/debugging scripts |
| `scripts/test_*.py` (3 files) | ~80 each | Upload/auth test scripts |

### Storage Changes
- 35 old `storage/test_srt_files/*.ja.srt` files → renamed to `*.ja-orig.srt` with full Japanese filenames
