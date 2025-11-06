#!/usr/bin/env python3
"""
Production SRT Translation Runner — Kendo Video Subtitles

Translates Japanese SRT subtitle files to English using Gemini (Pro model)
with kendo terminology dictionary context. Handles:

- 400 dialog lines per conversation limit
- 50 dialog lines per turn limit
- Dictionary + prompt context at each conversation start
- Rate limit detection (pro → fast model switch)
- Progress persistence for resume after rate limits
- Full trace saving (thinking, responses, timing)
- Concatenation of all translated segments into final output

Usage:
  # Translate a single file
  python tests/integration/run_srt_translation.py storage/test_srt_files/001*.srt

  # Translate all files in directory
  python tests/integration/run_srt_translation.py --all

  # Resume after rate limit
  python tests/integration/run_srt_translation.py --resume

  # Options
  python tests/integration/run_srt_translation.py --visible --lines-per-turn 30 FILE
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from universal_agents.providers.gemini.config import GeminiTranslatorConfig
from universal_agents.providers.gemini.translator import (
    GeminiTranslatorAgent,
    ProgressState,
    RateLimitError,
    TranslationChunk,
)
from universal_agents.core.srt_utils import (
    chunk_srt_text,
    detect_srt_format,
    get_srt_line_range,
    parse_srt_blocks,
)
from universal_agents.core.kendo_context import (
    build_kendo_srt_system_prompt,
    build_kendo_continue_prompt,
    build_kendo_new_conversation_prompt,
)

# ─────────────────────── Constants ───────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRT_DIR = PROJECT_ROOT / "storage" / "test_srt_files"
DICT_PATH = SRT_DIR / "Trilingual Kendo Dictionary.md"
OUTPUT_DIR = PROJECT_ROOT / "storage" / "translated_srt"
PROGRESS_DIR = PROJECT_ROOT / "storage" / "translation_progress"

DEFAULT_LINES_PER_TURN = 50
DEFAULT_LINES_PER_CONVERSATION = 400

# ─────────────────────── Logging ───────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("srt_runner")


# ─────────────────────── Auth ───────────────────────

def find_storage_state() -> str:
    """Find Gemini storage state file."""
    candidates = [
        PROJECT_ROOT / "storage" / "gemini_storage_state.json",
        Path.home() / ".universal-agents" / "gemini_storage_state.json",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    logger.error("No Gemini storage state found. Run capture_gemini_auth.py first.")
    sys.exit(1)


# ─────────────────────── SRT Helpers ───────────────────────

def count_srt_blocks(text: str) -> int:
    """Count the number of SRT subtitle blocks in text."""
    return len(re.findall(r"^\d+\s*$", text, re.MULTILINE))


def get_srt_files(directory: Path) -> list[Path]:
    """Get all .srt files in directory, sorted by name."""
    files = sorted(directory.glob("*.srt"))
    return files


def get_output_path(srt_path: Path) -> Path:
    """Generate output path for a translated SRT file."""
    stem = srt_path.stem
    # Replace .ja suffix if present
    if stem.endswith(".ja"):
        stem = stem[:-3]
    return OUTPUT_DIR / f"{stem}.en.srt"


def get_progress_path(srt_path: Path) -> Path:
    """Get progress file path for a given SRT file."""
    return PROGRESS_DIR / f"{srt_path.stem}_progress.json"


# ─────────────────────── Trace Saving ───────────────────────

def save_file_trace(srt_path: Path, trace_data: dict) -> Path:
    """Save translation trace for a single SRT file."""
    trace_dir = OUTPUT_DIR / "traces" / srt_path.stem
    trace_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Full JSON trace
    trace_path = trace_dir / f"trace_{timestamp}.json"
    trace_path.write_text(
        json.dumps(trace_data, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    # Markdown summary
    md_path = trace_dir / f"trace_{timestamp}.md"
    md_lines = [
        f"# Translation Trace: {srt_path.name}\n",
        f"**Timestamp:** {trace_data.get('timestamp', '')}\n",
        f"**Total Blocks:** {trace_data.get('total_blocks', 0)}\n",
        f"**Conversations Used:** {trace_data.get('conversations_used', 0)}\n",
        f"**Total Time:** {trace_data.get('elapsed_total_ms', 0) / 1000:.1f}s\n\n",
    ]

    for result in trace_data.get("results", []):
        status = "✅" if result.get("success") else "❌"
        md_lines.append(f"## Chunk {result.get('chunk_index', '?')} {status}\n")
        md_lines.append(f"- **Conversation:** {result.get('conversation_index', 0)}\n")
        md_lines.append(f"- **Time:** {result.get('processing_time_ms', 0):.0f}ms\n")

        if result.get("source_text"):
            preview = result["source_text"][:200].replace("\n", " ")
            md_lines.append(f"- **Source preview:** {preview}\n")

        if result.get("translated_text"):
            preview = result["translated_text"][:300].replace("\n", " ")
            md_lines.append(f"- **Translation preview:** {preview}\n")

        if result.get("thinking"):
            md_lines.append(
                f"\n<details><summary>Thinking ({len(result['thinking'])} chars)</summary>\n\n"
                f"{result['thinking'][:2000]}\n\n</details>\n"
            )

        if result.get("error"):
            md_lines.append(f"- **Error:** {result['error']}\n")

        md_lines.append("\n---\n\n")

    md_path.write_text("".join(md_lines), encoding="utf-8")
    return trace_dir


# ─────────────────────── Translation Logic ───────────────────────

async def translate_srt_file(
    srt_path: Path,
    storage_state: str,
    headless: bool = True,
    lines_per_turn: int = DEFAULT_LINES_PER_TURN,
    lines_per_conversation: int = DEFAULT_LINES_PER_CONVERSATION,
) -> bool:
    """Translate a single SRT file with conversation splitting and progress tracking.

    Returns True if fully translated, False if stopped (rate limit, error).
    """
    print(f"\n{'=' * 70}")
    print(f"  TRANSLATING: {srt_path.name}")
    print(f"{'=' * 70}")

    # ── 1. Load and validate SRT ──
    srt_text = srt_path.read_text(encoding="utf-8")
    if not detect_srt_format(srt_text):
        print(f"   ❌ Not a valid SRT file: {srt_path.name}")
        return False

    total_blocks = count_srt_blocks(srt_text)
    print(f"   📄 File: {srt_path.name}")
    print(f"   📏 Total blocks: {total_blocks}")

    # ── 2. Chunk into turns (lines_per_turn blocks each) ──
    chunks_raw = chunk_srt_text(srt_text, blocks_per_chunk=lines_per_turn)
    chunk_block_counts = [count_srt_blocks(c) for c in chunks_raw]
    total_chunks = len(chunks_raw)

    # Calculate conversations needed
    conversations_needed = 1
    running_lines = 0
    for bc in chunk_block_counts:
        if running_lines + bc > lines_per_conversation:
            conversations_needed += 1
            running_lines = 0
        running_lines += bc

    print(f"   🧩 Chunks: {total_chunks} (max {lines_per_turn} blocks/turn)")
    print(f"   💬 Conversations needed: ~{conversations_needed} "
          f"(max {lines_per_conversation} blocks/convo)")

    # ── 3. Check for existing progress ──
    progress_path = get_progress_path(srt_path)
    output_path = get_output_path(srt_path)

    # ── 4. Configure agent ──
    config = GeminiTranslatorConfig(
        headless=headless,
        storage_state=storage_state,
        timeout=600,
        max_turns_per_conversation=50,  # High — we manage splitting via line count
        source_language="ja",
        target_language="en",
        translation_mode="transcript",
        required_model="pro",
    )

    # ── 5. Build translation chunks ──
    chunks = [
        TranslationChunk(
            chunk_id=f"{srt_path.stem}_chunk_{i:03d}",
            chunk_index=i,
            source_text=text,
        )
        for i, text in enumerate(chunks_raw)
    ]

    # ── 6. Translate ──
    start_total = time.monotonic()
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rate_limited = False

    try:
        async with GeminiTranslatorAgent(config) as agent:
            agent.init_progress(
                document_id=srt_path.stem,
                total_chunks=total_chunks,
                progress_path=progress_path,
            )

            # Check how many already completed (resume)
            already_done = len(agent.progress.completed_chunks) if agent.progress else 0
            if already_done > 0:
                print(f"   🔄 Resuming: {already_done}/{total_chunks} chunks already done")

            for i, chunk in enumerate(chunks):
                # Skip already-completed
                if agent.progress and agent.progress.is_chunk_completed(i):
                    continue

                num_blocks = chunk_block_counts[i]

                # Check if we need a new conversation (line limit)
                needs_new_convo = (
                    i > 0
                    and agent.lines_in_conversation > 0
                    and agent.should_split_for_line_limit(num_blocks, lines_per_conversation)
                )

                # Also split if turn limit reached
                if not needs_new_convo and i > 0 and agent.should_split_conversation():
                    needs_new_convo = True

                is_first = (i == 0 and agent.conversation_index == 0 and already_done == 0)

                if needs_new_convo:
                    # Get last block number from previous chunk for context
                    prev_chunk_text = chunks_raw[i - 1] if i > 0 else ""
                    _, last_block = get_srt_line_range(prev_chunk_text)

                    print(f"\n   🔄 New conversation (after block {last_block}, "
                          f"lines used: {agent.lines_in_conversation})")

                    await agent.start_new_conversation()
                    is_first = True

                # Build prompts
                if is_first:
                    # First turn: send full dictionary + prompt context
                    _, last_block = get_srt_line_range(chunks_raw[i - 1]) if i > 0 else (0, 0)
                    if last_block > 0:
                        # Continuing in new conversation
                        system_prompt = build_kendo_new_conversation_prompt(
                            dict_path=DICT_PATH,
                            title=srt_path.stem,
                            last_block_num=last_block,
                            lines_per_turn=lines_per_turn,
                        )
                    else:
                        # Very first turn
                        system_prompt = build_kendo_srt_system_prompt(
                            dict_path=DICT_PATH,
                            title=srt_path.stem,
                            lines_per_turn=lines_per_turn,
                        )
                    continue_prompt = None
                else:
                    system_prompt = None
                    continue_prompt = build_kendo_continue_prompt(
                        chunk_num=i + 1,
                        total_chunks=total_chunks,
                    )

                print(f"   📝 Chunk {i + 1}/{total_chunks} "
                      f"({num_blocks} blocks, convo lines: {agent.lines_in_conversation})...")

                try:
                    result = await agent.translate_text(
                        chunk,
                        system_prompt=system_prompt,
                        continue_prompt=continue_prompt,
                        is_first_turn=is_first,
                        num_blocks=num_blocks,
                    )
                except RateLimitError as e:
                    print(f"\n   ⚠️  {e}")
                    print(f"   💾 Progress saved. Resume with --resume flag.")
                    rate_limited = True
                    break

                if result.success:
                    preview = result.translated_text[:100].replace("\n", " ")
                    print(f"   ✅ Done ({result.processing_time_ms:.0f}ms): {preview}...")
                else:
                    print(f"   ❌ Failed: {result.error}")

            elapsed_total = (time.monotonic() - start_total) * 1000

            # ── 7. Assemble final output ──
            if not rate_limited:
                # Collect all results (including previously completed ones)
                all_translations = []
                for r in agent.results:
                    if r.success and r.translated_text != "[previously completed]":
                        all_translations.append(r.translated_text)

                # Also load any previously saved partial translations
                if already_done > 0 and output_path.exists():
                    # We have partial output from previous run — need to rebuild
                    pass  # Results from this run include all turns

                full_translation = "\n\n".join(all_translations)

                # Save output
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(full_translation, encoding="utf-8")

                # Clean up progress file on completion
                if progress_path.exists():
                    progress_path.unlink()

            # ── 8. Save trace ──
            trace_data = {
                "timestamp": datetime.now().isoformat(),
                "srt_file": str(srt_path),
                "srt_file_name": srt_path.name,
                "total_blocks": total_blocks,
                "total_chunks": total_chunks,
                "lines_per_turn": lines_per_turn,
                "lines_per_conversation": lines_per_conversation,
                "conversations_used": agent.conversation_index + 1,
                "successful_chunks": sum(1 for r in agent.results if r.success),
                "rate_limited": rate_limited,
                "elapsed_total_ms": elapsed_total,
                "results": [r.to_dict() for r in agent.results],
            }
            trace_dir = save_file_trace(srt_path, trace_data)

            # ── 9. Print summary ──
            successful = sum(1 for r in agent.results if r.success)
            failed = sum(1 for r in agent.results if not r.success)

            print(f"\n   {'─' * 50}")
            if rate_limited:
                print(f"   ⚠️  RATE LIMITED — {successful} chunks translated so far")
            else:
                print(f"   ✅ Successful: {successful}/{total_chunks}")
            print(f"   ❌ Failed: {failed}")
            print(f"   💬 Conversations: {agent.conversation_index + 1}")
            print(f"   ⏱️  Total time: {elapsed_total / 1000:.1f}s")
            print(f"   📁 Trace: {trace_dir}")
            if not rate_limited:
                print(f"   📄 Output: {output_path}")

            return not rate_limited and failed == 0

    except Exception as e:
        elapsed_total = (time.monotonic() - start_total) * 1000
        logger.error("Translation failed: %s", e, exc_info=True)
        print(f"\n   ❌ Fatal error after {elapsed_total / 1000:.1f}s: {e}")
        return False


async def translate_all_files(
    storage_state: str,
    headless: bool = True,
    lines_per_turn: int = DEFAULT_LINES_PER_TURN,
    lines_per_conversation: int = DEFAULT_LINES_PER_CONVERSATION,
    resume_only: bool = False,
) -> None:
    """Translate all SRT files in the test directory."""
    srt_files = get_srt_files(SRT_DIR)
    if not srt_files:
        print("No SRT files found in", SRT_DIR)
        return

    print(f"\n{'=' * 70}")
    print(f"  BATCH SRT TRANSLATION — {len(srt_files)} files")
    print(f"{'=' * 70}")

    completed = []
    failed = []
    rate_limited = []

    for idx, srt_path in enumerate(srt_files):
        output_path = get_output_path(srt_path)
        progress_path = get_progress_path(srt_path)

        # Skip already-translated files (unless they have pending progress)
        if output_path.exists() and not progress_path.exists():
            print(f"\n   ⏭️  [{idx + 1}/{len(srt_files)}] Already translated: {srt_path.name}")
            completed.append(srt_path.name)
            continue

        # If resume_only, skip files without progress
        if resume_only and not progress_path.exists():
            continue

        success = await translate_srt_file(
            srt_path,
            storage_state,
            headless=headless,
            lines_per_turn=lines_per_turn,
            lines_per_conversation=lines_per_conversation,
        )

        if success:
            completed.append(srt_path.name)
        elif get_progress_path(srt_path).exists():
            rate_limited.append(srt_path.name)
            print(f"\n   ⚠️  Rate limited on {srt_path.name}. Stopping batch.")
            print(f"   💡 Resume later with: python {__file__} --resume")
            break
        else:
            failed.append(srt_path.name)

    # Final summary
    print(f"\n{'=' * 70}")
    print(f"  BATCH SUMMARY")
    print(f"{'=' * 70}")
    print(f"   ✅ Completed: {len(completed)}/{len(srt_files)}")
    print(f"   ❌ Failed: {len(failed)}")
    print(f"   ⚠️  Rate limited: {len(rate_limited)}")
    if failed:
        for f in failed:
            print(f"      - {f}")
    if rate_limited:
        for f in rate_limited:
            print(f"      - {f} (resume with --resume)")


# ─────────────────────── CLI ───────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Production SRT Translation Runner — Kendo Video Subtitles"
    )
    parser.add_argument(
        "srt_files", nargs="*",
        help="SRT file(s) to translate",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Translate all SRT files in test directory",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume translation for files with saved progress",
    )
    parser.add_argument(
        "--storage-state", "-s",
        default=os.getenv("GEMINI_STORAGE_STATE", ""),
        help="Path to Gemini storage state JSON",
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="Show browser window (for debugging)",
    )
    parser.add_argument(
        "--lines-per-turn", type=int, default=DEFAULT_LINES_PER_TURN,
        help=f"Max SRT blocks per turn (default: {DEFAULT_LINES_PER_TURN})",
    )
    parser.add_argument(
        "--lines-per-conversation", type=int, default=DEFAULT_LINES_PER_CONVERSATION,
        help=f"Max SRT blocks per conversation (default: {DEFAULT_LINES_PER_CONVERSATION})",
    )
    args = parser.parse_args()

    storage_state = args.storage_state or find_storage_state()
    headless = not args.visible

    if args.all or args.resume:
        asyncio.run(translate_all_files(
            storage_state,
            headless=headless,
            lines_per_turn=args.lines_per_turn,
            lines_per_conversation=args.lines_per_conversation,
            resume_only=args.resume,
        ))
    elif args.srt_files:
        for srt_file in args.srt_files:
            path = Path(srt_file)
            if not path.exists():
                print(f"File not found: {srt_file}")
                continue
            asyncio.run(translate_srt_file(
                path,
                storage_state,
                headless=headless,
                lines_per_turn=args.lines_per_turn,
                lines_per_conversation=args.lines_per_conversation,
            ))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
