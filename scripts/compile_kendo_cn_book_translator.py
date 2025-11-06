#!/usr/bin/env python3
"""Compile a self-contained Gemini Chinese Kendo Book Translator agent package.

This script uses the agent compiler to create a distributable package
for the kendo book (PDF) translation task where the source is Chinese
and the output is trilingual (ZH / JA / EN).

- agent.py: Executable translation script
- config.json: Modifiable configuration
- storage/: Auth state (gemini_storage_state.json)
- kendo_dict.md: Kendo dictionary
- translation_prompt.md: Translation prompt template
- requirements.txt: Python dependencies
- source_spec.json: Recompilation spec
- README.md: Usage instructions

Usage:
    python scripts/compile_kendo_cn_book_translator.py [--output-dir DIR]
"""

import argparse
import json
import shutil
import sys
import textwrap
from pathlib import Path

# Add project root for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from universal_agents.compiler import (
    AgentCompiler,
    AgentPackager,
    CapabilityResolver,
    CompiledAgent,
    ConfigBuilder,
    AgentAssembler,
    ResolvedComponents,
    UserRequirements,
)


def compile_kendo_cn_book_translator(output_dir: Path) -> Path:
    """Compile and package the Gemini Chinese kendo book translator agent."""

    # 1. Define requirements
    req = UserRequirements(
        use_case="translation",
        needs_file_upload=True,
        needs_thinking=False,
        needs_json_output=False,
        cost_sensitivity="free",
        provider_preference="gemini",
        output_format="package",
        package_dir=str(output_dir),
        package_name="gemini_kendo_cn_book_translator",
        auth_available={"gemini_storage": True},
    )
    req.apply_use_case_defaults()

    # 2. Resolve components
    resolver = CapabilityResolver()
    components = resolver.resolve(req)

    # 3. Override config for Chinese kendo book task
    config_kwargs = {
        "headless": True,
        "timeout": 600,
        "max_turns_per_conversation": 15,
        "source_language": "zh",
        "target_language": "ja,en",
        "translation_mode": "book",
        "chunk_size": 2000,
        "overlap_chars": 0,
        "required_model": "pro",
        "storage_state": "",  # Empty — fresh login on each compilation
    }

    # 4. Create compiled agent
    compiled = CompiledAgent(
        provider="gemini",
        agent_class_name=components.agent_class_name,
        config_class_name=components.config_class_name,
        config_kwargs=config_kwargs,
        capabilities=["translation", "file_upload", "model_selection", "rate_limit_detection", "pdf_splitting"],
        script="# Replaced by custom script below",
    )

    # 5. Package it
    packager = AgentPackager(project_root=PROJECT_ROOT)
    pkg_dir = packager.package(compiled, components, req, output_dir, "gemini_kendo_cn_book_translator")

    # 6. Copy the kendo dictionary into the package
    dict_src = PROJECT_ROOT / "storage" / "test_srt_files" / "Trilingual Kendo Dictionary (1).md"
    if dict_src.exists():
        shutil.copy2(dict_src, pkg_dir / "kendo_dict.md")
    else:
        dict_alt = PROJECT_ROOT / "storage" / "test_srt_files" / "Trilingual Kendo Dictionary.md"
        if dict_alt.exists():
            shutil.copy2(dict_alt, pkg_dir / "kendo_dict.md")

    # 7. Write the CN-specific translation prompt template
    _write_translation_prompt(pkg_dir)

    # 8. Write the custom production run script (replaces generic agent.py)
    _write_run_script(pkg_dir)

    # 9. Write custom README
    _write_readme(pkg_dir)

    # 10. Update config.json with book-specific fields
    config_path = pkg_dir / "config.json"
    config = json.loads(config_path.read_text())
    config["book"] = {
        "dictionary_file": "kendo_dict.md",
        "translation_prompt_file": "translation_prompt.md",
        "pages_per_conversation": 15,
        "pdf_input_dir": "books/",
        "pages_dir": "pages/",
        "output_dir": "translated/",
        "progress_dir": "progress/",
    }
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    # 11. Create input/output directories with .gitkeep
    for d in ("books", "pages", "translated", "progress", "storage"):
        (pkg_dir / d).mkdir(exist_ok=True)
        gitkeep = pkg_dir / d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

    print(f"\n✅ Package created at: {pkg_dir}")
    print(f"   Files: {list(p.name for p in sorted(pkg_dir.iterdir()))}")
    print(f"\n   To use:")
    print(f"   1. Copy Chinese PDF files into: {pkg_dir / 'books/'}")
    print(f"   2. First login: python {pkg_dir / 'agent.py'} --login")
    print(f"   3. Translate: python {pkg_dir / 'agent.py'} books/BOOK.pdf")
    return pkg_dir


def _write_translation_prompt(pkg_dir: Path) -> None:
    """Write the CN-specific translation prompt template."""
    # Use the default prompt from cn_book_prompts as the template file
    from universal_agents.core.cn_book_prompts import _default_cn_translation_prompt
    prompt = _default_cn_translation_prompt()
    (pkg_dir / "translation_prompt.md").write_text(prompt, encoding="utf-8")


def _write_run_script(pkg_dir: Path) -> None:
    """Write the production agent.py for Chinese kendo book translation."""
    script = textwrap.dedent('''\
        #!/usr/bin/env python3
        """Chinese Kendo Book Translator — Self-contained Gemini translation agent.

        Translates Chinese kendo book PDFs to trilingual (ZH/JA/EN) format
        using Gemini Pro via browser automation, page by page.

        Generated by universal-agents compiler.
        Edit config.json to change behavior.

        Usage:
            python agent.py BOOK.pdf                    # Translate one book
            python agent.py BOOK.pdf --visible          # Show browser
            python agent.py BOOK.pdf --resume           # Resume after rate limit
            python agent.py --login                     # Capture fresh login session
            python agent.py BOOK.pdf --pages 10-25      # Translate specific page range
            python agent.py BOOK.pdf --redo 27-40        # Redo specific pages (clears cache)
            python agent.py BOOK.pdf --redo 27-40        # Redo specific pages (clears cache)
        """

        import argparse
        import asyncio
        import json
        import logging
        import sys
        import time
        from datetime import datetime
        from pathlib import Path

        SCRIPT_DIR = Path(__file__).resolve().parent

        # ---------------------------------------------------------------------------
        # Load config
        # ---------------------------------------------------------------------------
        with open(SCRIPT_DIR / "config.json", encoding="utf-8") as f:
            CONFIG = json.load(f)

        _kwargs = dict(CONFIG["config_kwargs"])

        # Resolve storage state relative to package
        _state_name = Path(_kwargs.get("storage_state", "")).name if _kwargs.get("storage_state") else ""
        _state = SCRIPT_DIR / "storage" / "gemini_storage_state.json"
        if _state.exists():
            _kwargs["storage_state"] = str(_state)
        elif _state_name:
            _s = SCRIPT_DIR / "storage" / _state_name
            if _s.exists():
                _kwargs["storage_state"] = str(_s)

        _book_cfg = CONFIG.get("book", {})
        DICT_FILE = SCRIPT_DIR / _book_cfg.get("dictionary_file", "kendo_dict.md")
        PROMPT_FILE = SCRIPT_DIR / _book_cfg.get("translation_prompt_file", "translation_prompt.md")
        PAGES_PER_CONVO = _book_cfg.get("pages_per_conversation", 15)
        PDF_INPUT_DIR = SCRIPT_DIR / _book_cfg.get("pdf_input_dir", "books/")
        PAGES_DIR = SCRIPT_DIR / _book_cfg.get("pages_dir", "pages/")
        OUTPUT_DIR = SCRIPT_DIR / _book_cfg.get("output_dir", "translated/")
        PROGRESS_DIR = SCRIPT_DIR / _book_cfg.get("progress_dir", "progress/")

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        logger = logging.getLogger(__name__)

        # ---------------------------------------------------------------------------
        # Imports (universal_agents must be on sys.path or installed)
        # ---------------------------------------------------------------------------
        from universal_agents.providers.gemini.config import GeminiTranslatorConfig
        from universal_agents.providers.gemini.translator import (
            GeminiTranslatorAgent,
            ProgressState,
            RateLimitError,
            TranslationChunk,
        )
        from universal_agents.core.pdf_utils import split_pdf_to_pages, get_page_count
        from universal_agents.core.cn_book_prompts import (
            build_cn_book_system_prompt,
            build_cn_book_continue_prompt,
            build_cn_book_new_conversation_prompt,
        )


        # ---------------------------------------------------------------------------
        # Login helpers
        # ---------------------------------------------------------------------------

        async def capture_login() -> bool:
            """Open a visible browser, navigate to Google login, then verify on Gemini."""
            logger.info("Opening browser for Google login...")
            config = GeminiTranslatorConfig(**{**_kwargs, "headless": False})
            agent = GeminiTranslatorAgent(config)

            try:
                async with agent:
                    page = await agent._agent.browser_mgr.ensure_page()

                    # Check if already logged in to Gemini
                    if await agent.check_logged_in():
                        logger.info("Already logged in!")
                        await _save_cookies(page)
                        return True

                    # Navigate to Google login page
                    await page.goto("https://accounts.google.com/signin")
                    await page.wait_for_timeout(2000)

                    print("\\n" + "=" * 60)
                    print("  GOOGLE LOGIN")
                    print("=" * 60)
                    print("  Please log in to your Google account in the browser window.")
                    print("  After login, the agent will navigate to Gemini automatically.")
                    print("  Waiting for login (checking every 5s)...")
                    print("=" * 60 + "\\n")

                    # Wait for Google login to complete by checking URL changes
                    for attempt in range(120):  # 10 minutes
                        await asyncio.sleep(5)
                        url = page.url
                        if "accounts.google.com/signin" not in url and "accounts.google.com/v3/signin" not in url:
                            logger.info("Google login appears complete (URL: %s)", url[:80])
                            break
                        if attempt % 12 == 11:
                            print(f"  Still waiting for Google login... ({(attempt + 1) * 5}s)")
                    else:
                        logger.error("Google login timeout after 10 minutes")
                        return False

                    # Now navigate to Gemini to verify and capture cookies
                    logger.info("Navigating to Gemini...")
                    await page.goto("https://gemini.google.com")
                    try:
                        await page.wait_for_selector(
                            "div[contenteditable='true']", state="visible", timeout=30_000,
                        )
                    except Exception:
                        await page.wait_for_timeout(5000)

                    if await agent.check_logged_in():
                        logger.info("Gemini login verified!")
                        await _save_cookies(page)
                        print("\\n  Login successful! Cookies saved.\\n")
                        return True

                    # Give extra time if Gemini still shows sign-in
                    logger.warning("Gemini not yet authenticated, waiting...")
                    for retry in range(12):
                        await asyncio.sleep(5)
                        if await agent.check_logged_in():
                            await _save_cookies(page)
                            print("\\n  Login successful! Cookies saved.\\n")
                            return True

                    logger.error("Logged into Google but Gemini auth failed")
                    return False
            except Exception as e:
                logger.error("Login capture failed: %s", e)
                return False


        async def _save_cookies(page) -> None:
            """Save browser cookies to storage/gemini_storage_state.json."""
            storage_dir = SCRIPT_DIR / "storage"
            storage_dir.mkdir(parents=True, exist_ok=True)
            state_file = storage_dir / "gemini_storage_state.json"

            ctx = page.context
            state = await ctx.storage_state()
            state_file.write_text(
                json.dumps(state, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Storage state saved: %s", state_file)

            # Update config to point to new storage state
            _kwargs["storage_state"] = str(state_file)


        async def verify_login(agent: GeminiTranslatorAgent, visible: bool) -> bool:
            """Verify login, optionally redirecting to Google login in visible mode."""
            logged_in = await agent.check_logged_in()
            if logged_in:
                return True

            if not visible:
                logger.error(
                    "Not logged in to Gemini. Run with --login first, "
                    "or use --visible to log in manually."
                )
                return False

            page = await agent._agent.browser_mgr.ensure_page()
            logger.info("Not logged in — redirecting to Google login...")
            await page.goto("https://accounts.google.com/signin")
            await page.wait_for_timeout(2000)

            print("\\n  Not logged in. Please log in to Google in the browser window.")
            print("  After login, the agent will navigate back to Gemini.")
            print("  Waiting for login (checking every 5s)...\\n")

            for attempt in range(60):
                await asyncio.sleep(5)
                url = page.url
                if "accounts.google.com/signin" not in url and "accounts.google.com/v3/signin" not in url:
                    logger.info("Google login complete (URL: %s)", url[:80])
                    await page.goto("https://gemini.google.com")
                    try:
                        await page.wait_for_selector(
                            "div[contenteditable='true']", state="visible", timeout=30_000,
                        )
                    except Exception:
                        await page.wait_for_timeout(5000)
                    if await agent.check_logged_in():
                        await _save_cookies(page)
                        return True
                    for retry in range(6):
                        await asyncio.sleep(5)
                        if await agent.check_logged_in():
                            await _save_cookies(page)
                            return True
                    logger.error("Google login succeeded but Gemini auth failed")
                    return False
                if attempt % 6 == 5:
                    print(f"  Still waiting... ({(attempt + 1) * 5}s)")

            logger.error("Login timeout after 5 minutes")
            return False


        # ---------------------------------------------------------------------------
        # PDF preparation
        # ---------------------------------------------------------------------------

        def prepare_book(pdf_path: Path, book_id: str) -> list[Path]:
            """Split a book PDF into individual page PDFs."""
            book_pages_dir = PAGES_DIR / book_id
            book_pages_dir.mkdir(parents=True, exist_ok=True)

            existing = sorted(book_pages_dir.glob("page_*.pdf"))
            if existing:
                expected_count = get_page_count(pdf_path)
                if len(existing) == expected_count:
                    logger.info(
                        "Pages already split for '%s': %d pages in %s",
                        book_id, expected_count, book_pages_dir,
                    )
                    return existing
                else:
                    logger.warning(
                        "Found %d existing pages but PDF has %d — re-splitting",
                        len(existing), expected_count,
                    )

            logger.info("Splitting %s into individual pages...", pdf_path.name)
            pages = split_pdf_to_pages(pdf_path, book_pages_dir, page_prefix="page")
            logger.info("Split into %d pages → %s", len(pages), book_pages_dir)
            return pages


        def parse_page_range(range_str: str, total_pages: int) -> tuple[int, int]:
            """Parse a page range string like '10-25' into (start, end) 1-indexed."""
            if "-" in range_str:
                parts = range_str.split("-", 1)
                start = int(parts[0])
                end = int(parts[1]) if parts[1] else total_pages
            else:
                start = int(range_str)
                end = start
            return max(1, start), min(end, total_pages)


        # ---------------------------------------------------------------------------
        # Translation cache — JSON-based persistence for resume support
        # ---------------------------------------------------------------------------

        def _load_translation_cache(cache_path: Path) -> dict[int, str]:
            """Load page translations from a JSON cache file.

            Returns dict mapping page_num (1-indexed) → translated_text.
            """
            if not cache_path.exists():
                return {}
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                # Keys in JSON are strings; convert to int
                return {int(k): v for k, v in data.items()}
            except (json.JSONDecodeError, ValueError, KeyError):
                logger.warning("Failed to load translation cache: %s", cache_path)
                return {}


        def _save_translation_cache(
            cache_path: Path, translations: dict[int, str]
        ) -> None:
            """Save page translations to a JSON cache file."""
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(translations, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )


        # ---------------------------------------------------------------------------
        # Main translation loop
        # ---------------------------------------------------------------------------

        async def translate_book(
            pdf_path: Path,
            visible: bool = False,
            page_range: tuple[int, int] | None = None,
        ) -> Path | None:
            """Translate a complete Chinese book PDF, page by page."""
            book_id = pdf_path.stem
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            PROGRESS_DIR.mkdir(parents=True, exist_ok=True)

            output_path = OUTPUT_DIR / f"{book_id}_trilingual.md"
            progress_path = PROGRESS_DIR / f"{book_id}_progress.json"
            results_path = PROGRESS_DIR / f"{book_id}_results.json"
            cache_path = PROGRESS_DIR / f"{book_id}_translations.json"

            # Step 1: Split PDF into pages
            page_files = prepare_book(pdf_path, book_id)
            total_pages = len(page_files)
            logger.info("Book: %s — %d pages", pdf_path.name, total_pages)

            if page_range:
                start_page, end_page = page_range
            else:
                start_page, end_page = 1, total_pages

            # Step 2: Create agent config
            config = GeminiTranslatorConfig(**_kwargs)
            if visible:
                config.headless = False

            agent = GeminiTranslatorAgent(config)

            try:
                async with agent:
                    if not await verify_login(agent, visible):
                        return None

                    # Initialize progress tracking
                    agent.init_progress(book_id, total_pages, str(progress_path))

                    # Load existing translations from JSON cache (reliable resume)
                    all_translations: dict[int, str] = _load_translation_cache(cache_path)
                    if all_translations:
                        logger.info(
                            "Resumed: loaded %d cached page translations",
                            len(all_translations),
                        )

                    pages_in_conversation = 0
                    # Always True at start — ensures system prompt is sent
                    # on the very first non-skipped page of this session
                    is_first_turn_in_convo = True

                    for page_num in range(start_page, end_page + 1):
                        page_idx = page_num - 1

                        # Skip completed pages
                        if agent.progress and agent.progress.is_chunk_completed(page_idx):
                            logger.info("Page %d/%d — already completed, skipping", page_num, total_pages)
                            continue

                        # Check if we need a new conversation (page limit reached)
                        if pages_in_conversation >= PAGES_PER_CONVO:
                            logger.info(
                                "Conversation limit (%d pages) — starting new conversation",
                                PAGES_PER_CONVO,
                            )
                            await agent.start_new_conversation()
                            is_first_turn_in_convo = True
                            pages_in_conversation = 0

                        # ---- Build prompts ----
                        if is_first_turn_in_convo:
                            last_completed = page_num - 1
                            if last_completed == 0:
                                system_prompt = build_cn_book_system_prompt(
                                    str(DICT_FILE),
                                    str(PROMPT_FILE) if PROMPT_FILE.exists() else None,
                                    book_title=pdf_path.stem,
                                )
                            else:
                                system_prompt = build_cn_book_new_conversation_prompt(
                                    str(DICT_FILE),
                                    str(PROMPT_FILE) if PROMPT_FILE.exists() else None,
                                    book_title=pdf_path.stem,
                                    last_page=last_completed,
                                    total_pages=total_pages,
                                )
                            is_first_turn_in_convo = False
                        else:
                            system_prompt = None

                        continue_prompt = build_cn_book_continue_prompt(page_num, total_pages)

                        page_file = page_files[page_idx]
                        chunk = TranslationChunk(
                            chunk_id=f"{book_id}_page_{page_num}",
                            chunk_index=page_idx,
                            source_file=str(page_file),
                        )

                        logger.info(
                            "Translating page %d/%d (conversation %d, turn %d)...",
                            page_num, total_pages,
                            agent.conversation_index + 1,
                            pages_in_conversation + 1,
                        )

                        try:
                            result = await agent.translate_file(
                                chunk,
                                system_prompt=system_prompt,
                                continue_prompt=continue_prompt,
                                is_first_turn=(system_prompt is not None),
                            )
                        except RateLimitError:
                            logger.warning(
                                "Rate limit hit at page %d/%d — saving progress",
                                page_num, total_pages,
                            )
                            _save_translation_cache(cache_path, all_translations)
                            _write_output(output_path, all_translations, book_id, total_pages)
                            agent.export_results(str(results_path))
                            print(f"\\n  Rate limited at page {page_num}/{total_pages}.")
                            print(f"  Progress saved. Resume with: python agent.py {pdf_path.name} --resume\\n")
                            return None

                        if result.success:
                            all_translations[page_num] = result.translated_text
                            pages_in_conversation += 1

                            if agent.progress:
                                agent.progress.mark_completed(page_idx)
                                agent._save_progress()

                            # Save translation cache after each page for robustness
                            _save_translation_cache(cache_path, all_translations)

                            if await agent.check_rate_limit():
                                logger.warning(
                                    "Rate limit detected after page %d/%d — saving progress",
                                    page_num, total_pages,
                                )
                                _write_output(output_path, all_translations, book_id, total_pages)
                                agent.export_results(str(results_path))
                                print(f"\\n  Rate limited after page {page_num}/{total_pages}.")
                                print(f"  Progress saved. Resume with: python agent.py {pdf_path.name} --resume\\n")
                                return None

                            logger.info(
                                "Page %d/%d done (%.1fs)",
                                page_num, total_pages, result.processing_time_ms / 1000,
                            )
                        else:
                            logger.error(
                                "Page %d failed: %s", page_num, result.error,
                            )

                    # Write final output
                    _save_translation_cache(cache_path, all_translations)
                    _write_output(output_path, all_translations, book_id, total_pages)
                    agent.export_results(str(results_path))

                    completed = len(all_translations)
                    logger.info(
                        "Translation complete: %d/%d pages, output: %s",
                        completed, total_pages, output_path,
                    )
                    return output_path

            except Exception as e:
                logger.error("Translation failed: %s", e, exc_info=True)
                return None


        def _write_output(
            output_path: Path,
            translations: dict[int, str],
            book_id: str,
            total_pages: int,
        ) -> None:
            """Write all completed translations to a markdown file."""
            if not translations:
                return

            output_path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                f"# {book_id} — Trilingual Translation (ZH → JA / EN)",
                f"",
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"**Pages translated:** {len(translations)}/{total_pages}",
                f"**Source language:** Chinese",
                f"**Target languages:** Japanese, English",
                f"",
                f"---",
                f"",
            ]

            for page_num in sorted(translations.keys()):
                lines.append(translations[page_num])
                lines.append("")
                lines.append("")

            output_path.write_text("\\n".join(lines), encoding="utf-8")
            logger.info("Output written: %s (%d pages)", output_path, len(translations))


        # ---------------------------------------------------------------------------
        # CLI
        # ---------------------------------------------------------------------------

        async def main():
            parser = argparse.ArgumentParser(
                description="Chinese Kendo Book Translator — Gemini Trilingual Translation",
                formatter_class=argparse.RawDescriptionHelpFormatter,
                epilog="""
        Examples:
            python agent.py --login                    # First-time login
            python agent.py mybook.pdf                 # Translate entire book
            python agent.py mybook.pdf --visible       # Show browser
            python agent.py mybook.pdf --resume        # Resume after rate limit
            python agent.py mybook.pdf --pages 10-25   # Translate pages 10-25
            python agent.py mybook.pdf --redo 27-40    # Redo pages 27-40 (clears cache first)
                """,
            )
            parser.add_argument("file", nargs="?", help="PDF file to translate")
            parser.add_argument("--login", action="store_true", help="Capture fresh Gemini login")
            parser.add_argument("--resume", action="store_true", help="Resume from progress")
            parser.add_argument("--visible", action="store_true", help="Show browser")
            parser.add_argument("--pages", type=str, help="Page range (e.g., 10-25)")
            parser.add_argument("--redo", type=str, help="Redo page range (e.g., 27-40): clears cache for those pages then re-translates")
            args = parser.parse_args()

            if args.login:
                success = await capture_login()
                sys.exit(0 if success else 1)

            if not args.file:
                parser.print_help()
                sys.exit(1)

            pdf_path = Path(args.file)
            if not pdf_path.exists():
                pdf_path = PDF_INPUT_DIR / args.file
            if not pdf_path.exists():
                logger.error("PDF file not found: %s", args.file)
                sys.exit(1)

            state_path = SCRIPT_DIR / "storage" / "gemini_storage_state.json"
            if not state_path.exists():
                print("\\n  No login session found. Running login first...\\n")
                success = await capture_login()
                if not success:
                    sys.exit(1)

            page_range = None
            if args.redo:
                total = get_page_count(pdf_path)
                redo_start, redo_end = parse_page_range(args.redo, total)
                logger.info("Redo: clearing cache for pages %d-%d", redo_start, redo_end)

                # Clear cached translations and progress for redo pages
                book_id = pdf_path.stem
                cache_path = PROGRESS_DIR / f"{book_id}_translations.json"
                progress_path = PROGRESS_DIR / f"{book_id}_progress.json"

                if cache_path.exists():
                    translations = _load_translation_cache(cache_path)
                    before = len(translations)
                    for pg in range(redo_start, redo_end + 1):
                        translations.pop(pg, None)
                    _save_translation_cache(cache_path, translations)
                    logger.info(
                        "Cleared %d pages from translation cache (%d → %d)",
                        before - len(translations), before, len(translations),
                    )

                if progress_path.exists():
                    try:
                        prog = json.loads(progress_path.read_text(encoding="utf-8"))
                        completed = prog.get("completed_chunks", [])
                        before = len(completed)
                        completed = [c for c in completed if c < (redo_start - 1) or c > (redo_end - 1)]
                        prog["completed_chunks"] = completed
                        progress_path.write_text(
                            json.dumps(prog, indent=2, ensure_ascii=False), encoding="utf-8",
                        )
                        logger.info(
                            "Cleared %d pages from progress (%d → %d)",
                            before - len(completed), before, len(completed),
                        )
                    except Exception as e:
                        logger.warning("Could not update progress file: %s", e)

                page_range = (redo_start, redo_end)
                print(f"\\n  Redo: pages {redo_start}-{redo_end} cleared. Re-translating...\\n")
            elif args.pages:
                total = get_page_count(pdf_path)
                page_range = parse_page_range(args.pages, total)
                logger.info("Translating pages %d-%d of %d", page_range[0], page_range[1], total)

            result = await translate_book(
                pdf_path,
                visible=args.visible,
                page_range=page_range,
            )

            if result:
                print(f"\\n  Translation complete: {result}\\n")
            else:
                print("\\n  Translation incomplete (rate limited or error). Use --resume to continue.\\n")
                sys.exit(1)


        if __name__ == "__main__":
            asyncio.run(main())
    ''')
    agent_path = pkg_dir / "agent.py"
    agent_path.write_text(script, encoding="utf-8")
    agent_path.chmod(0o755)


def _write_readme(pkg_dir: Path) -> None:
    """Write the README.md for the CN book translator package."""
    readme = textwrap.dedent("""\
        # Gemini Chinese Kendo Book Translator

        Self-contained compiled agent that translates **Chinese** kendo book PDFs into
        trilingual (ZH / JA / EN) format using **Gemini Pro** via browser automation.

        ## Quick Start

        ```bash
        # 1. First-time login (opens browser for Google sign-in)
        python agent.py --login

        # 2. Place your Chinese PDF in books/
        cp mybook.pdf books/

        # 3. Translate
        python agent.py books/mybook.pdf
        ```

        ## Usage

        ```
        python agent.py FILE.pdf                    # Translate entire book
        python agent.py FILE.pdf --visible          # Show browser window
        python agent.py FILE.pdf --resume           # Resume after rate limit
        python agent.py FILE.pdf --pages 10-25      # Translate specific page range
        python agent.py --login                     # Capture fresh login session
        ```

        ## How It Works

        1. **PDF Splitting** — The book PDF is split into individual page PDFs using PyMuPDF
        2. **Login** — On first run (no saved session), opens a visible browser for manual Google login
        3. **Model Selection** — Verifies Gemini Pro is selected; switches if needed
        4. **Page-by-Page Translation** — Each page PDF is uploaded to Gemini with the translation prompt
        5. **Conversation Splitting** — After 15 pages (configurable), starts a new conversation with full context re-sent
        6. **Rate Limit Handling** — Detects when Gemini switches from Pro to Fast; saves progress for resume
        7. **Checkpoint/Resume** — Progress is saved after each page; use `--resume` to continue

        ## Output Format

        Trilingual sentence-by-sentence format (Chinese source → Japanese + English):

        ```
        Page [#]

        [Chinese sentence (original)]
        [Japanese translation]
        [English translation]

        ---

        === END OF PAGE [#] ===
        ```

        Output files are written to `translated/{book_stem}_trilingual.md`.

        ## Directory Structure

        ```
        agent.py                    # Main executable
        config.json                 # Agent configuration
        kendo_dict.md              # Kendo terminology dictionary
        translation_prompt.md       # Translation prompt template
        books/                      # Place input PDFs here
        pages/                      # Split single-page PDFs (auto-generated)
        translated/                 # Output translations
        progress/                   # Checkpoint files for resume
        storage/                    # Browser session cookies
        ```

        ## Configuration

        Edit `config.json` to change:

        - `max_turns_per_conversation` — Pages per Gemini conversation (default: 15)
        - `required_model` — Target model (default: "pro")
        - `headless` — Run headless by default (default: true)

        ## Requirements

        - Python 3.11+
        - `universal_agents` package (parent project)
        - PyMuPDF (`pip install PyMuPDF`)
        - Playwright with Chromium

        ## Recompilation

        Generated by the universal-agents compiler. To recompile:

        ```bash
        python scripts/compile_kendo_cn_book_translator.py
        ```
    """)
    (pkg_dir / "README.md").write_text(readme, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Compile Chinese Kendo Book Translator agent")
    parser.add_argument(
        "--output-dir", "-o",
        default=str(PROJECT_ROOT / "compiled_agents"),
        help="Output directory for the package (default: compiled_agents/)",
    )
    args = parser.parse_args()
    compile_kendo_cn_book_translator(Path(args.output_dir))


if __name__ == "__main__":
    main()
