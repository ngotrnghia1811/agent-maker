# Development Log 4 — universal-agent_v2

**Date:** 2026-03-30  
**Author:** Development Session Notes  
**Commits:** `83b606a` → `7d197e0`  

---

## Overview

This log covers two major features:

1. **Self-contained agent packaging** — extending the compiler pipeline so compiled agents are distributable, executable, modifiable, and recompilable
2. **Production SRT translation infrastructure** — kendo domain context, model selection, rate limit detection, conversation splitting, and a batch translation runner for 35 Japanese kendo video SRT files

Previous state: 444 tests, agent compiler complete (Phase 1–4 + CompilerLLM), SRT utilities and translation prompts added.  
Final state: 476 tests, self-contained packaging pipeline, production-grade Gemini SRT translation runner.

---

## 1. Self-Contained Agent Packaging

### Problem

Compiled agents (`CompiledAgent`) were either live in-memory instances or in-memory script strings. There was no way to:
- Distribute a compiled agent as a standalone directory
- Edit configuration without touching generated code
- Recompile from a saved specification

### Solution: `AgentPackager`

**File:** `src/universal_agents/compiler/agent_packager.py` (248 lines)

The packager creates a self-contained directory from a `CompiledAgent`:

```
my_agent/
├── agent.py           # Executable script — reads config.json at runtime
├── config.json        # User-modifiable configuration (edit without touching code)
├── storage/           # Auth state (cookies, storage state files)
├── requirements.txt   # pip-installable dependencies
├── README.md          # Quick start + details
└── source_spec.json   # Original compilation spec (for recompilation)
```

### Design Decisions

**Config-driven execution:** `agent.py` reads `config.json` at startup rather than having config hardcoded. This means users can change timeouts, models, visibility, etc. without regenerating code.

**Storage state portability:** If the compiled agent has a `storage_state` path (browser auth), the file is copied into `storage/` and the generated script resolves it relative to the package directory.

**Recompilation via `source_spec.json`:** Stores the original `UserRequirements` fields plus a `_compiled` section with provider/transport metadata. The compiler's `compile_from_json()` strips `_`-prefixed keys and recompiles.

**Use-case-specific scripts:** The generated `agent.py` includes different `main()` blocks based on `use_case`:
- `chat`: Interactive REPL loop with `agent.chat()`
- `translation`: Reads stdin, translates, prints result
- `data`: Prompt-based query loop
- default: Single-shot `agent.chat("Hello!")`

**Dependency-aware `requirements.txt`:** Includes `playwright`, `httpx`, `pyyaml`, `rich` as base. Adds `playwright-stealth` for browser transport and `camoufox` for Gemini.

### Integration into Compiler Pipeline

| Change                | File                 | Details                                                                                                |
| --------------------- | -------------------- | ------------------------------------------------------------------------------------------------------ |
| New output format     | `requirements.py`    | Added `output_format="package"`, `package_dir`, `package_name` fields to `UserRequirements`            |
| Assembler integration | `agent_assembler.py` | `assemble()` now handles `output_format="package"`: generates script + calls `AgentPackager.package()` |
| `CompiledAgent` field | `agent_assembler.py` | Added `package_dir: str \| None` field                                                                 |
| Recompilation         | `compiler.py`        | `compile_from_json()` now strips `_`-prefixed keys from source_spec.json                               |
| Exports               | `__init__.py`        | Added `AgentPackager` to `__all__`                                                                     |

### Test Coverage

**File:** `tests/unit/test_agent_packager.py` (195 lines, 21 tests)

| Test Class                     | Tests | Covers                                                           |
| ------------------------------ | ----- | ---------------------------------------------------------------- |
| `TestPackageCreation`          | 3     | Directory creation, all expected files, auto-name generation     |
| `TestConfigJson`               | 2     | Required keys + metadata                                         |
| `TestAgentScript`              | 4     | Executable permission, config reading, imports, `__main__` block |
| `TestRequirements`             | 2     | Playwright dep, Gemini-specific camoufox                         |
| `TestSourceSpec`               | 2     | Round-trip, compiled metadata                                    |
| `TestReadme`                   | 2     | Quick start instructions, provider mention                       |
| `TestStorageCopy`              | 2     | State file copy, missing file graceful handling                  |
| `TestUseCaseScripts`           | 3     | Chat/translation/data script variants                            |
| `TestAssemblerPackagePipeline` | 1     | End-to-end assembler → packager integration                      |

---

## 2. Kendo SRT Translation Infrastructure

### Problem

35 kendo video SRT subtitle files (Japanese, 463–1418 blocks each, ~141K total lines) need to be translated to English using Gemini via browser automation, with:
- A specialized kendo dictionary (61KB, 2395 lines) for terminology consistency
- Conversation limits (400 lines max per conversation, 50 lines per turn)
- Pro model requirement with rate limit detection
- Progress persistence for resume after rate limits

### Solution: Three-Layer Architecture

#### Layer 1: Kendo Context (`core/kendo_context.py`)

**File:** `src/universal_agents/core/kendo_context.py` (122 lines)

Functions that load the Trilingual Kendo Dictionary and build SRT-specific prompts:

| Function                                               | Purpose                                                                                                                                            |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `load_kendo_dictionary(path)`                          | Load dictionary markdown file                                                                                                                      |
| `build_kendo_srt_system_prompt(dict_path, ...)`        | Full initial prompt: translator role + SRT rules + kendo terminology rules (rōmaji, macrons, first-occurrence annotation) + full dictionary inline |
| `build_kendo_continue_prompt(chunk_num, total_chunks)` | Short continuation prompt for subsequent chunks in same conversation                                                                               |
| `build_kendo_new_conversation_prompt(dict_path, ...)`  | Full prompt for new conversation when 400-line limit reached — includes dictionary + context about where previous conversation left off            |

**Key design:** The entire dictionary (61KB) is embedded inline in every conversation-opening prompt. This ensures Gemini always has the complete terminology reference regardless of conversation splitting.

**Translation rules enforced in prompt:**
- Preserve SRT structure (block numbers, timestamps, blank line separators)
- Keep original Japanese text + English translation in parentheses
- Use rōmaji with macrons for kendo terms (dōjō, chūdan, jōdan)
- First occurrence annotation: *rōmaji* (漢字 — English gloss)
- Translate every block without commentary

#### Layer 2: Translator Agent Enhancements (`providers/gemini/translator.py`)

**Changes to `GeminiTranslatorAgent`** (+130 lines):

| Feature                                                             | Implementation                                                                                                                            |
| ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **`RateLimitError`**                                                | New exception class raised when Gemini auto-switches from pro to fast model                                                               |
| **`_MODE_BTN_SEL`, `_MODE_MENU_SEL`**                               | Class-level CSS selectors for Gemini's mode picker (`button[data-test-id="bard-mode-menu-button"]` and `[role="menu"] [role="menuitem"]`) |
| **`lines_in_conversation`**                                         | New tracking field, starts at 0, reset on `start_new_conversation()`                                                                      |
| **`detect_current_model()`**                                        | Reads mode picker button text to get current model name                                                                                   |
| **`select_model(target)`**                                          | Opens mode picker, clicks matching menu item, verifies switch. Called on `__aenter__()` and `start_new_conversation()`                    |
| **`check_rate_limit()`**                                            | After each response, checks if model switched from required to "fast" — indicates rate limiting                                           |
| **`should_split_for_line_limit(next_chunk_blocks, max_lines=400)`** | Checks if adding the next chunk would exceed the per-conversation line limit                                                              |
| **`translate_text()` updates**                                      | New `num_blocks` parameter; increments `lines_in_conversation`; calls `check_rate_limit()` after each response                            |
| **`ProgressState` updates**                                         | New `current_lines_in_conversation` field persisted in `to_dict()`/`from_dict()`/`save()`/`load()`                                        |

**Model selection flow:**
1. `__aenter__()` → calls `select_model("pro")` if `config.required_model` is set
2. `start_new_conversation()` → resets line counter, calls `select_model("pro")`  
3. After each `translate_text()` response → `check_rate_limit()` detects if Gemini switched to "fast"
4. If rate-limited → raises `RateLimitError` → caller saves progress and stops

#### Layer 3: Production Runner (`tests/integration/run_srt_translation.py`)

**File:** `tests/integration/run_srt_translation.py` (~350 lines)

Full-featured CLI tool for batch SRT translation:

```bash
# Single file
python run_srt_translation.py storage/test_srt_files/001*.srt

# All files
python run_srt_translation.py --all

# Resume after rate limit
python run_srt_translation.py --resume

# With options
python run_srt_translation.py --visible --lines-per-turn 30 --lines-per-conversation 300 FILE
```

**Key features:**
- **Batch processing:** `--all` iterates through all `.ja.srt` files in `storage/test_srt_files/`
- **Conversation splitting:** When `lines_in_conversation` + next chunk blocks > 400, starts a new conversation with full dictionary context
- **First turn optimization:** First turn of each conversation sends full kendo system prompt + dictionary
- **Rate limit handling:** Catches `RateLimitError` → saves progress → stops batch (resume with `--resume`)
- **Progress persistence:** Per-file progress files at `storage/translation_progress/{stem}_progress.json`
- **Trace saving:** Full JSON + Markdown traces per file in `storage/translated_srt/traces/`
- **Output:** Final translated SRT at `storage/translated_srt/{stem}.en.srt`
- **CLI options:** `--visible`, `--lines-per-turn`, `--lines-per-conversation`, `--storage-state`

---

## 3. Problems and Solutions

### Problem: Orphaned `self.progress.save()` Line

After adding `check_rate_limit()` and `_save_progress()` methods to `translator.py`, a stray `self.progress.save(self._progress_path)` line was left orphaned outside any method — causing an `IndentationError`.

**Solution:** Identified the duplicate line and removed it. The save is correctly called inside `_save_progress()`.

### Problem: SRT "Lines" Ambiguity

The user says "400 lines" and "50 dialog lines" — but an SRT file has multiple line types: block numbers, timestamps, and text. What counts as a "line"?

**Solution:** Defined "lines" as SRT subtitle **blocks** (each block = index number + timestamp + text lines + blank separator). Counted via regex `grep -c "^[0-9]+$"` or the existing `count_srt_blocks()` function. This maps naturally to "dialog lines" since each block represents one subtitle entry.

### Problem: Rate Limit Detection Without API Access

Gemini's browser interface doesn't expose rate limit status through the DOM or API responses. When rate-limited, it silently switches from the "Pro" model to "Fast".

**Solution:** After each translation response, read the mode picker button text via `detect_current_model()`. If the button shows "fast" when we requested "pro", that's a rate limit. Raise `RateLimitError` so the caller can save progress and pause.

### Problem: Dictionary Context Lost at Conversation Splits

When the 400-line limit forces a new conversation, Gemini loses all previous context including the kendo dictionary.

**Solution:** `build_kendo_new_conversation_prompt()` embeds the full 61KB dictionary in every conversation-opening message. Also includes context about which block number the previous conversation ended at, so the model knows where to resume.

---

## 4. Test Results

| Metric         | Before | After | Delta |
| -------------- | ------ | ----- | ----- |
| Unit tests     | 455    | 476   | +21   |
| Test files     | ~25    | 27    | +2    |
| Pass rate      | 100%   | 100%  | —     |
| Execution time | ~0.5s  | ~0.6s | +0.1s |

**New test files:**
- `tests/unit/test_agent_packager.py` — 21 tests for self-contained packaging
- Previous session: `tests/unit/test_translator.py` — 11 tests added for line tracking, RateLimitError, kendo context

---

## 5. Files Changed

### New Files
| File                                                            | Lines | Purpose                                 |
| --------------------------------------------------------------- | ----- | --------------------------------------- |
| `src/universal_agents/compiler/agent_packager.py`               | 248   | Self-contained agent packaging          |
| `src/universal_agents/core/kendo_context.py`                    | 122   | Kendo dictionary loader + SRT prompts   |
| `tests/integration/run_srt_translation.py`                      | ~350  | Production batch SRT translation runner |
| `tests/unit/test_agent_packager.py`                             | 195   | 21 packager unit tests                  |
| `requirements.txt`                                              | 47    | Project-level pip requirements          |
| `storage/test_srt_files/*.ja.srt`                               | ~141K | 35 Japanese kendo SRT files             |
| `storage/test_srt_files/Trilingual Kendo Dictionary.md`         | 2395  | JP→EN→ZH kendo dictionary               |
| `storage/test_srt_files/Trilingual Kendo Translation Prompt.md` | 314   | Original translation prompt template    |

### Modified Files
| File                                                  | Change                                                    |
| ----------------------------------------------------- | --------------------------------------------------------- |
| `src/universal_agents/compiler/__init__.py`           | Export `AgentPackager`                                    |
| `src/universal_agents/compiler/agent_assembler.py`    | `package_dir` field, `output_format="package"` handling   |
| `src/universal_agents/compiler/compiler.py`           | `compile_from_json()` strips `_`-prefixed keys            |
| `src/universal_agents/compiler/requirements.py`       | `package_dir`, `package_name`, `output_format="package"`  |
| `src/universal_agents/providers/gemini/translator.py` | +130 lines: model selection, line tracking, rate limiting |
| `tests/unit/test_translator.py`                       | +98 lines: line tracking, kendo context tests             |

---

## 6. Architecture Decisions

### Why Embed Dictionary in Every Conversation?

**Alternative considered:** Upload dictionary as a file attachment.  
**Why rejected:** Gemini's file upload adds complexity and unreliable Angular hydration timing. Inline text in the prompt is simpler, guaranteed to work, and the 61KB dictionary is well within Gemini Pro's context window.

### Why Not Use API for Translation?

**Reason:** Gemini's browser interface provides free Pro model access. The API (Vertex AI or AI Studio) requires billing. For 35 files × ~800 blocks average, browser automation is the cost-effective path.

### Why Stop on Rate Limit Instead of Waiting?

**Reason:** Gemini doesn't expose rate limit reset times. Automatic retry would burn time polling. Better to save progress, stop, and let the user resume manually when the limit resets. The `ProgressState` persistence ensures zero lost work.

### Why Package Instead of Docker?

**Reason:** Docker is heavy for single-agent distribution. A Python directory with `config.json` + `agent.py` + `requirements.txt` is lightweight, editable, and portable. Users can `pip install -r requirements.txt && python agent.py` immediately.

---

## 7. Git History

```
7d197e0 Self-contained agent packaging, kendo SRT translation runner, 476 tests
83b606a SRT utils, translation prompts, ProgressState persistence, 444 tests
```
