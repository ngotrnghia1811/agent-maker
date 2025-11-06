#!/usr/bin/env python3
"""
Gemini SRT Translation — Live Integration Test

Translates a Japanese SRT subtitle file using the Gemini translator agent
via browser automation. Captures full trace, terminal CLI interaction,
and translation results.

Usage:
  python tests/integration/test_gemini_srt_translation.py
  python tests/integration/test_gemini_srt_translation.py --visible
  python tests/integration/test_gemini_srt_translation.py --storage-state storage/gemini_storage_state.json
  python tests/integration/test_gemini_srt_translation.py --chunks-per-batch 5
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from universal_agents.providers.gemini.config import GeminiTranslatorConfig
from universal_agents.providers.gemini.translator import (
    GeminiTranslatorAgent,
    TranslationChunk,
)
from universal_agents.core.srt_utils import (
    chunk_srt_text,
    detect_srt_format,
    get_srt_line_range,
    add_overlap,
)
from universal_agents.core.translation_prompts import (
    get_system_prompt,
    get_continue_prompt,
    get_new_conversation_prompt,
)

# ─────────────────────── Logging ───────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gemini_srt_test")

# ─────────────────────── Paths ───────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SRT_FILE = FIXTURES_DIR / "test_kendo_transcript.srt"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RESULTS_DIR = PROJECT_ROOT / "storage" / "test_results" / "gemini_srt" / f"run_{TIMESTAMP}"


# ─────────────────────── Auth ───────────────────────

async def ensure_auth(storage_state: str) -> str:
    """Verify storage state file exists for Gemini auth."""
    if storage_state and Path(storage_state).exists():
        logger.info("Using storage state: %s", storage_state)
        return storage_state

    # Check common locations
    candidates = [
        PROJECT_ROOT / "storage" / "gemini_storage_state.json",
        Path.home() / ".universal-agents" / "gemini_storage_state.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            logger.info("Found storage state: %s", candidate)
            return str(candidate)

    logger.error(
        "No Gemini storage state found. "
        "Log into Gemini first and save the storage state."
    )
    sys.exit(1)


# ─────────────────────── Trace Helpers ───────────────────────

def save_trace(trace_data: dict) -> Path:
    """Save full trace to disk."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Full JSON trace
    trace_path = RESULTS_DIR / "trace.json"
    trace_path.write_text(
        json.dumps(trace_data, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    # Human-readable markdown
    md_path = RESULTS_DIR / "trace.md"
    md_lines = [
        f"# Gemini SRT Translation Test\n",
        f"**Timestamp:** {trace_data.get('timestamp', '')}\n",
        f"**SRT File:** {trace_data.get('srt_file', '')}\n",
        f"**Total Chunks:** {trace_data.get('total_chunks', 0)}\n",
        f"**Successful:** {trace_data.get('successful_chunks', 0)}\n\n",
    ]

    for result in trace_data.get("results", []):
        status = "✅" if result.get("success") else "❌"
        md_lines.append(f"## Chunk {result.get('chunk_index', '?')} {status}\n")
        md_lines.append(f"**Time:** {result.get('processing_time_ms', 0):.0f}ms\n")
        if result.get("source_text"):
            md_lines.append(f"\n**Source (first 300 chars):**\n```\n{result['source_text'][:300]}\n```\n")
        if result.get("translated_text"):
            md_lines.append(f"\n**Translation (first 500 chars):**\n```\n{result['translated_text'][:500]}\n```\n")
        if result.get("thinking"):
            md_lines.append(f"\n<details><summary>Thinking</summary>\n\n{result['thinking'][:1000]}\n\n</details>\n")
        if result.get("error"):
            md_lines.append(f"\n**Error:** {result['error']}\n")
        md_lines.append("\n---\n\n")

    md_path.write_text("".join(md_lines), encoding="utf-8")
    return RESULTS_DIR


# ─────────────────────── Main Test ───────────────────────

async def run_srt_translation(
    storage_state: str,
    headless: bool = True,
    blocks_per_chunk: int = 10,
    overlap_chars: int = 0,
) -> bool:
    """Run the SRT translation test."""
    print("\n" + "=" * 70)
    print("  GEMINI SRT TRANSLATION TEST")
    print("=" * 70)

    # ── 1. Load and parse SRT ──
    if not SRT_FILE.exists():
        print(f"❌ SRT file not found: {SRT_FILE}")
        return False

    srt_text = SRT_FILE.read_text(encoding="utf-8")
    if not detect_srt_format(srt_text):
        print("❌ File does not appear to be SRT format")
        return False

    chunks_raw = chunk_srt_text(srt_text, blocks_per_chunk=blocks_per_chunk)
    if overlap_chars > 0:
        chunks_raw = add_overlap(chunks_raw, overlap_chars)

    print(f"\n   📄 SRT file: {SRT_FILE.name}")
    print(f"   📏 Total size: {len(srt_text):,} chars")
    print(f"   🧩 Chunks: {len(chunks_raw)} (blocks_per_chunk={blocks_per_chunk})")

    # ── 2. Build prompts ──
    system_prompt = get_system_prompt(
        source_lang="Japanese",
        target_lang="English",
        mode="transcript",
        title="Kendo Basics",
    )
    continue_prompt_tmpl = lambda n: get_continue_prompt(mode="transcript", chunk_num=n)

    # ── 3. Create translation chunks ──
    chunks = [
        TranslationChunk(
            chunk_id=f"chunk_{i:03d}",
            chunk_index=i,
            source_text=text,
        )
        for i, text in enumerate(chunks_raw)
    ]

    # ── 4. Configure agent ──
    config = GeminiTranslatorConfig(
        headless=headless,
        storage_state=storage_state,
        timeout=300,
        max_turns_per_conversation=15,
        source_language="ja",
        target_language="en",
        translation_mode="transcript",
    )

    # ── 5. Translate ──
    start_total = time.monotonic()
    progress_path = RESULTS_DIR / "progress.json"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        async with GeminiTranslatorAgent(config) as agent:
            agent.init_progress(
                document_id=SRT_FILE.stem,
                total_chunks=len(chunks),
                progress_path=progress_path,
            )

            for i, chunk in enumerate(chunks):
                is_first = i == 0 and agent.conversation_index == 0

                # Check if we need a new conversation
                if agent.should_split_conversation() and i > 0:
                    first_line, last_line = get_srt_line_range(chunks[i - 1].source_text)
                    new_convo_prompt = get_new_conversation_prompt(
                        source_lang="Japanese",
                        target_lang="English",
                        mode="transcript",
                        title="Kendo Basics",
                        last_line=last_line,
                    )
                    print(f"\n   🔄 Starting new conversation (after line {last_line})")
                    await agent.start_new_conversation()
                    is_first = True
                    system_prompt_used = new_convo_prompt
                else:
                    system_prompt_used = system_prompt if is_first else None

                cont_prompt = None if is_first else continue_prompt_tmpl(i + 1)

                print(f"\n   📝 Translating chunk {i + 1}/{len(chunks)}...")
                result = await agent.translate_text(
                    chunk,
                    system_prompt=system_prompt_used,
                    continue_prompt=cont_prompt,
                    is_first_turn=is_first,
                )

                if result.success:
                    preview = result.translated_text[:120].replace("\n", " ")
                    print(f"   ✅ Done ({result.processing_time_ms:.0f}ms): {preview}...")
                else:
                    print(f"   ❌ Failed: {result.error}")

            elapsed_total = (time.monotonic() - start_total) * 1000

            # ── 6. Save results ──
            full_translation = agent.get_full_translation()

            # Save full translation
            translation_path = RESULTS_DIR / "full_translation.txt"
            translation_path.write_text(full_translation, encoding="utf-8")

            # Save results JSON
            agent.export_results(RESULTS_DIR / "results.json")

            # Save trace
            trace_data = {
                "timestamp": datetime.now().isoformat(),
                "srt_file": str(SRT_FILE),
                "config": {
                    "headless": headless,
                    "blocks_per_chunk": blocks_per_chunk,
                    "overlap_chars": overlap_chars,
                    "max_turns_per_conversation": config.max_turns_per_conversation,
                },
                "total_chunks": len(chunks),
                "successful_chunks": sum(1 for r in agent.results if r.success),
                "elapsed_total_ms": elapsed_total,
                "results": [r.to_dict() for r in agent.results],
            }
            trace_dir = save_trace(trace_data)

            # ── 7. Print summary ──
            successful = sum(1 for r in agent.results if r.success)
            failed = sum(1 for r in agent.results if not r.success)

            print("\n" + "=" * 70)
            print("  RESULTS SUMMARY")
            print("=" * 70)
            print(f"   ✅ Successful: {successful}/{len(chunks)}")
            print(f"   ❌ Failed: {failed}")
            print(f"   ⏱️  Total time: {elapsed_total / 1000:.1f}s")
            print(f"   📁 Results: {trace_dir}")
            print(f"   📄 Translation: {translation_path}")
            print(f"   📊 Trace: {trace_dir / 'trace.json'}")

            if full_translation:
                print(f"\n   --- First 500 chars of translation ---")
                print(f"   {full_translation[:500]}")

            return failed == 0

    except Exception as e:
        elapsed_total = (time.monotonic() - start_total) * 1000
        logger.error("Translation failed: %s", e, exc_info=True)
        print(f"\n   ❌ Fatal error after {elapsed_total / 1000:.1f}s: {e}")
        return False


# ─────────────────────── CLI ───────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gemini SRT Translation Test")
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
        "--blocks-per-chunk", type=int, default=10,
        help="SRT blocks per translation chunk (default: 10)",
    )
    parser.add_argument(
        "--overlap-chars", type=int, default=0,
        help="Characters of overlap between chunks (default: 0)",
    )
    args = parser.parse_args()

    headless = not args.visible

    async def run(ss: str):
        ss = await ensure_auth(ss)
        return await run_srt_translation(
            ss, headless,
            blocks_per_chunk=args.blocks_per_chunk,
            overlap_chars=args.overlap_chars,
        )

    success = asyncio.run(run(args.storage_state))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
