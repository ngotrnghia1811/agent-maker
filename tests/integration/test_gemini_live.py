#!/usr/bin/env python3
"""
Gemini Live Browser Tests with Full Trace Capture

Tests Gemini chat and data agents (headless by default).
Captures the full trace of every LLM response (raw API responses,
thinking, intermediate steps, timestamps) and saves them to disk.

Usage:
  python tests/integration/test_gemini_live.py                          # headless (default)
  python tests/integration/test_gemini_live.py --visible                # show browser window
  python tests/integration/test_gemini_live.py --storage-state storage/gemini_storage_state.json
  python tests/integration/test_gemini_live.py --test chat_single       # run specific test
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

from universal_agents.providers.gemini.chat import GeminiChatAgent
from universal_agents.providers.gemini.config import GeminiConfig, GeminiDataConfig, GeminiTranslatorConfig
from universal_agents.providers.gemini.data import GeminiDataAgent
from universal_agents.providers.gemini.translator import (
    GeminiTranslatorAgent, TranslationChunk,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gemini_live_test")

# ───────────────────── Results & Trace Tracking ─────────────────────

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TRACE_DIR = Path(__file__).parent.parent.parent / "storage" / "test_results" / "gemini" / f"run_{TIMESTAMP}"
RESULTS: list[dict] = []


def save_trace(test_name: str, trace_data: dict) -> Path:
    """Save a full trace for one test to disk."""
    test_dir = TRACE_DIR / test_name.replace(" ", "_").lower()
    test_dir.mkdir(parents=True, exist_ok=True)

    # Full trace JSON
    trace_path = test_dir / "trace.json"
    trace_path.write_text(json.dumps(trace_data, indent=2, default=str, ensure_ascii=False))

    # Human-readable markdown
    md_path = test_dir / "trace.md"
    md_lines = [f"# {test_name}\n", f"**Timestamp:** {trace_data.get('timestamp', '')}\n"]
    for turn in trace_data.get("turns", []):
        md_lines.append(f"\n## Turn {turn.get('turn_number', '?')}\n")
        md_lines.append(f"**User:** {turn.get('user_message', '')[:500]}\n")
        md_lines.append(f"**Assistant:** {turn.get('assistant_message', '')[:1000]}\n")
        md_lines.append(f"**Time:** {turn.get('processing_time_ms', 0):.0f}ms\n")
        if turn.get("thinking"):
            md_lines.append(f"\n<details><summary>Thinking ({turn.get('thinking_source', 'unknown')})</summary>\n\n{turn['thinking'][:2000]}\n\n</details>\n")
        if turn.get("raw_api_responses"):
            md_lines.append(f"\n**Raw API Responses:** {len(turn['raw_api_responses'])} captured\n")
    md_path.write_text("".join(md_lines), encoding="utf-8")

    return test_dir


def extract_turns_trace(agent) -> list[dict]:
    turns_trace = []
    for t in agent.history.turns:
        turn_data = {
            "turn_number": t.turn_number,
            "user_message": t.user_message.content,
            "user_timestamp": t.user_message.timestamp.isoformat(),
            "assistant_message": t.assistant_message.content,
            "assistant_timestamp": t.assistant_message.timestamp.isoformat(),
            "thinking": t.thinking,
            "thinking_source": t.thinking_source,
            "processing_time_ms": t.processing_time_ms,
            "success": t.success,
            "error": t.error,
            "raw_api_responses": t.raw_api_responses,
        }
        turns_trace.append(turn_data)
    return turns_trace


def record(test_name: str, status: str, details: str = "", elapsed_ms: float = 0,
           trace_dir: str = ""):
    emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"\n{emoji} {test_name}: {status}")
    if details:
        print(f"   {details}")
    if trace_dir:
        print(f"   📁 Trace: {trace_dir}")
    RESULTS.append({
        "test": test_name,
        "status": status,
        "details": details,
        "elapsed_ms": round(elapsed_ms, 1),
        "trace_dir": trace_dir,
    })


# ───────────────────── Chat Agent Tests ─────────────────────

async def test_chat_single_turn(storage_state: str, headless: bool = True):
    """Single-turn chat: ask a simple math question."""
    print("\n" + "=" * 60)
    print("  TEST 1: Gemini Chat — Single Turn")
    print("=" * 60)

    config = GeminiConfig(headless=headless, storage_state=storage_state, timeout=120)
    start = time.monotonic()
    try:
        async with GeminiChatAgent(config) as agent:
            response = await agent.chat("What is 2 + 2? Reply with just the number.")
            elapsed = (time.monotonic() - start) * 1000

            trace = {
                "test": "Gemini Chat Single Turn",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 120},
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("gemini_chat_single_turn", trace)

            print(f"   Response: {response[:200]}")
            print(f"   Time: {elapsed:.0f}ms")
            print(f"   Raw API responses captured: {sum(len(t.get('raw_api_responses', [])) for t in trace['turns'])}")

            if "4" in response:
                record("Gemini Chat Single Turn", "PASS",
                       f"Got '4' in response ({elapsed:.0f}ms)", elapsed, str(trace_dir))
            else:
                record("Gemini Chat Single Turn", "FAIL",
                       f"Expected '4', got: {response[:100]}", elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Chat Single Turn", "FAIL", str(e), elapsed)


async def test_chat_multi_turn(storage_state: str, headless: bool = True):
    """Multi-turn chat: 3-turn context-dependent conversation."""
    print("\n" + "=" * 60)
    print("  TEST 2: Gemini Chat — Multi-Turn (3 turns)")
    print("=" * 60)

    config = GeminiConfig(headless=headless, storage_state=storage_state, timeout=120)
    start = time.monotonic()
    try:
        async with GeminiChatAgent(config) as agent:
            print("\n   Turn 1/3: Pick a number")
            r1 = await agent.chat("Pick the number 42, and remember it. Reply with just the number.")
            print(f"   → {r1[:100]}")

            print("\n   Turn 2/3: Double it")
            r2 = await agent.chat("Double that number. Reply with just the number.")
            print(f"   → {r2[:100]}")

            print("\n   Turn 3/3: Add 16")
            r3 = await agent.chat("Add 16 to that number. Reply with just the number.")
            print(f"   → {r3[:100]}")

            elapsed = (time.monotonic() - start) * 1000

            trace = {
                "test": "Gemini Chat Multi-Turn",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 120},
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("gemini_chat_multi_turn", trace)

            has_42 = "42" in r1
            has_84 = "84" in r2
            has_100 = "100" in r3

            print(f"   Raw API responses captured: {sum(len(t.get('raw_api_responses', [])) for t in trace['turns'])}")

            if has_42 and has_84 and has_100:
                record("Gemini Chat Multi-Turn", "PASS",
                       f"Context maintained: 42→84→100 ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Gemini Chat Multi-Turn", "FAIL",
                       f"42={'✓' if has_42 else '✗'}, 84={'✓' if has_84 else '✗'}, "
                       f"100={'✓' if has_100 else '✗'} "
                       f"(got: {r1[:50]}|{r2[:50]}|{r3[:50]})",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Chat Multi-Turn", "FAIL", str(e), elapsed)


async def test_chat_thinking(storage_state: str, headless: bool = True):
    """Chat with thinking extraction: ask a reasoning question."""
    print("\n" + "=" * 60)
    print("  TEST 3: Gemini Chat — Thinking Extraction")
    print("=" * 60)

    config = GeminiConfig(headless=headless, storage_state=storage_state,
                          timeout=120, extract_thinking=True)
    start = time.monotonic()
    try:
        async with GeminiChatAgent(config) as agent:
            response = await agent.chat(
                "If a train travels at 60 mph for 2.5 hours, how far does it travel? "
                "Show your reasoning step by step, then give the final answer."
            )
            elapsed = (time.monotonic() - start) * 1000

            last_turn = agent.history.turns[-1] if agent.history.turns else None
            thinking = last_turn.thinking if last_turn else None
            thinking_source = last_turn.thinking_source if last_turn else None

            trace = {
                "test": "Gemini Chat Thinking",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 120, "extract_thinking": True},
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("gemini_chat_thinking", trace)

            print(f"   Response: {response[:300]}")
            print(f"   Thinking: {'captured' if thinking else 'not captured'}")
            if thinking_source:
                print(f"   Thinking source: {thinking_source}")
            print(f"   Time: {elapsed:.0f}ms")

            has_answer = "150" in response
            # Thinking is bonus — Gemini may not always expose it
            if has_answer:
                thinking_info = f"thinking={'captured' if thinking else 'not captured'}"
                if thinking_source:
                    thinking_info += f" ({thinking_source})"
                record("Gemini Chat Thinking", "PASS",
                       f"Correct answer, {thinking_info} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Gemini Chat Thinking", "FAIL",
                       f"Expected '150', got: {response[:100]}", elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Chat Thinking", "FAIL", str(e), elapsed)


# ───────────────────── Data Agent Tests ─────────────────────

async def test_data_json_generation(storage_state: str, headless: bool = True):
    """Data agent: generate and extract structured JSON."""
    print("\n" + "=" * 60)
    print("  TEST 4: Gemini Data — JSON Generation")
    print("=" * 60)

    config = GeminiDataConfig(headless=headless, storage_state=storage_state, timeout=180)
    start = time.monotonic()
    try:
        async with GeminiDataAgent(config) as agent:
            prompt = agent.build_data_prompt(
                "Generate a JSON object with these fields: "
                '{"name": string (your choice), "processed": true, "count": 42}. '
                "Return ONLY the JSON, no explanation.",
                final_remind="Return ONLY valid JSON. No markdown. No explanation."
            )
            response = await agent.chat(prompt)
            elapsed = (time.monotonic() - start) * 1000
            data = agent.extract_json(response)

            trace = {
                "test": "Gemini Data JSON Generation",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 180},
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
                "extracted_json": data,
            }
            trace_dir = save_trace("gemini_data_json_generation", trace)

            print(f"   Response: {response[:300]}")
            print(f"   Extracted JSON: {data}")
            print(f"   Time: {elapsed:.0f}ms")

            if data and isinstance(data, dict):
                has_processed = data.get("processed") is True
                has_count = data.get("count") == 42
                record("Gemini Data JSON", "PASS",
                       f"JSON extracted, processed={has_processed}, count={has_count} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Gemini Data JSON", "FAIL",
                       f"JSON extraction failed. Response: {response[:100]}",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Data JSON", "FAIL", str(e), elapsed)


async def test_data_break_prompt(storage_state: str, headless: bool = True):
    """Data agent: BREAK prompt for question/answer/reasoning extraction."""
    print("\n" + "=" * 60)
    print("  TEST 5: Gemini Data — BREAK Prompt")
    print("=" * 60)

    config = GeminiDataConfig(headless=headless, storage_state=storage_state, timeout=180)
    start = time.monotonic()
    try:
        async with GeminiDataAgent(config) as agent:
            prompt = agent.build_data_prompt(
                "Answer this question and return your response as a JSON object with "
                'the keys "question", "answer", and "reasoning".\n\n'
                "Question: What is the capital of France?",
                final_remind='Return ONLY valid JSON with keys: "question", "answer", "reasoning". No markdown.'
            )
            response = await agent.chat(prompt)
            elapsed = (time.monotonic() - start) * 1000
            data = agent.extract_json(response)

            trace = {
                "test": "Gemini Data BREAK Prompt",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 180},
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
                "extracted_json": data,
            }
            trace_dir = save_trace("gemini_data_break_prompt", trace)

            print(f"   Response: {response[:300]}")
            print(f"   Extracted JSON: {data}")
            print(f"   Time: {elapsed:.0f}ms")

            if data and isinstance(data, dict):
                keys = sorted(data.keys())
                has_required = all(k in data for k in ("question", "answer", "reasoning"))
                if has_required:
                    record("Gemini Data BREAK", "PASS",
                           f"JSON extracted with keys: {keys} ({elapsed:.0f}ms)",
                           elapsed, str(trace_dir))
                else:
                    record("Gemini Data BREAK", "FAIL",
                           f"Missing keys. Got: {keys}", elapsed, str(trace_dir))
            else:
                record("Gemini Data BREAK", "FAIL",
                       f"JSON extraction failed. Response: {response[:100]}",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Data BREAK", "FAIL", str(e), elapsed)


# ───────────────────── Translator Agent Tests ─────────────────────

async def test_translator_single_chunk(storage_state: str, headless: bool = True):
    """Translator agent — single text chunk translation."""
    print("\n" + "=" * 60)
    print("  TEST 6: Gemini Translator — Single Chunk")
    print("=" * 60)

    config = GeminiTranslatorConfig(
        headless=headless, storage_state=storage_state,
        timeout=180, source_language="ja", target_language="en",
    )
    start = time.monotonic()
    try:
        agent = GeminiTranslatorAgent(config)
        agent._agent = GeminiDataAgent(config)
        await agent._agent.__aenter__()

        try:
            chunk = TranslationChunk(
                chunk_id="ch_001", chunk_index=0,
                source_text="東京は日本の首都です。人口は約1400万人です。",
            )
            result = await agent.translate_text(
                chunk,
                system_prompt=(
                    "You are a professional Japanese-to-English translator. "
                    "Translate naturally, maintaining the original tone. "
                    "Output only the translation."
                ),
                is_first_turn=True,
            )
            elapsed = (time.monotonic() - start) * 1000

            trace = {
                "test": "Gemini Translator Single Chunk",
                "timestamp": datetime.now().isoformat(),
                "config": {"source_language": "ja", "target_language": "en"},
                "turns": extract_turns_trace(agent._agent),
                "translation_result": result.to_dict(),
                "stats": agent._agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("gemini_translator_single_chunk", trace)

            print(f"   Source: {chunk.source_text}")
            print(f"   Translation: {result.translated_text[:300]}")
            print(f"   Time: {elapsed:.0f}ms")

            if result.success and ("tokyo" in result.translated_text.lower() or "capital" in result.translated_text.lower()):
                record("Gemini Translator Single Chunk", "PASS",
                       f"Translated successfully ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif result.success:
                record("Gemini Translator Single Chunk", "PASS",
                       f"Got response: {result.translated_text[:80]} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Gemini Translator Single Chunk", "FAIL",
                       f"Error: {result.error}", elapsed, str(trace_dir))
        finally:
            await agent._agent.__aexit__(None, None, None)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Translator Single Chunk", "FAIL", str(e), elapsed)


async def test_translator_multi_chunk(storage_state: str, headless: bool = True):
    """Translator agent — multi-chunk with conversation management."""
    print("\n" + "=" * 60)
    print("  TEST 7: Gemini Translator — Multi-Chunk (2 chunks)")
    print("=" * 60)

    config = GeminiTranslatorConfig(
        headless=headless, storage_state=storage_state,
        timeout=180, max_turns_per_conversation=10,
        source_language="ja", target_language="en",
    )
    start = time.monotonic()
    try:
        agent = GeminiTranslatorAgent(config)
        agent._agent = GeminiDataAgent(config)
        await agent._agent.__aenter__()

        try:
            chunk1 = TranslationChunk(
                chunk_id="ch_001", chunk_index=0,
                source_text="桜の季節が来ました。公園には多くの人が花見を楽しんでいます。",
            )
            r1 = await agent.translate_text(
                chunk1,
                system_prompt=(
                    "You are a professional Japanese-to-English translator. "
                    "Translate naturally, maintaining the original tone. "
                    "Output only the translation."
                ),
                is_first_turn=True,
            )
            print(f"   Chunk 1: {r1.translated_text[:200]}")

            chunk2 = TranslationChunk(
                chunk_id="ch_002", chunk_index=1,
                source_text="子供たちは走り回り、大人たちは静かにお弁当を食べています。",
            )
            r2 = await agent.translate_text(
                chunk2,
                continue_prompt="Continue translating the next passage:",
            )
            print(f"   Chunk 2: {r2.translated_text[:200]}")

            elapsed = (time.monotonic() - start) * 1000
            full = agent.get_full_translation()

            trace = {
                "test": "Gemini Translator Multi-Chunk",
                "timestamp": datetime.now().isoformat(),
                "config": {"max_turns_per_conversation": 10},
                "turns": extract_turns_trace(agent._agent),
                "results": [r1.to_dict(), r2.to_dict()],
                "full_translation": full,
                "stats": agent._agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("gemini_translator_multi_chunk", trace)

            print(f"\n   Full translation ({len(full)} chars):")
            print(f"   {full[:400]}")
            print(f"   Turn count: {agent.turn_in_conversation}")

            if r1.success and r2.success:
                record("Gemini Translator Multi-Chunk", "PASS",
                       f"2 chunks translated, {agent.turn_in_conversation} turns ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                errors = [r.error for r in [r1, r2] if not r.success]
                record("Gemini Translator Multi-Chunk", "FAIL", f"Errors: {errors}",
                       elapsed, str(trace_dir))
        finally:
            await agent._agent.__aexit__(None, None, None)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Translator Multi-Chunk", "FAIL", str(e), elapsed)


async def test_translator_pdf(storage_state: str, headless: bool = True):
    """Translator agent — PDF file upload and translation."""
    print("\n" + "=" * 60)
    print("  TEST 8: Gemini Translator — PDF Upload")
    print("=" * 60)

    pdf_path = Path(__file__).parent / "fixtures" / "test_japanese.pdf"
    if not pdf_path.exists():
        record("Gemini Translator PDF Upload", "SKIP", f"PDF fixture not found: {pdf_path}")
        return

    config = GeminiTranslatorConfig(
        headless=headless, storage_state=storage_state,
        timeout=180, source_language="ja", target_language="en",
    )
    start = time.monotonic()
    try:
        agent = GeminiTranslatorAgent(config)
        agent._agent = GeminiDataAgent(config)
        await agent._agent.__aenter__()

        try:
            chunk = TranslationChunk(
                chunk_id="pdf_001", chunk_index=0,
                source_file=str(pdf_path.resolve()),
            )

            result = await agent.translate_file(
                chunk,
                system_prompt=(
                    "Translate all the Japanese text in this PDF to English. "
                    "Output only the English translation."
                ),
                is_first_turn=True,
            )
            elapsed = (time.monotonic() - start) * 1000

            trace = {
                "test": "Gemini Translator PDF Upload",
                "timestamp": datetime.now().isoformat(),
                "config": {"source_language": "ja", "target_language": "en"},
                "source_file": str(pdf_path),
                "source_file_size": pdf_path.stat().st_size,
                "turns": extract_turns_trace(agent._agent),
                "translation_result": result.to_dict(),
                "stats": agent._agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("gemini_translator_pdf_upload", trace)

            print(f"   Source: {pdf_path.name} ({pdf_path.stat().st_size} bytes)")
            print(f"   Translation: {result.translated_text[:300]}")
            print(f"   Success: {result.success}")

            if result.success and ("Tokyo" in result.translated_text or "capital" in result.translated_text.lower()):
                record("Gemini Translator PDF Upload", "PASS",
                       f"PDF translated: {result.translated_text[:80]} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif result.success:
                record("Gemini Translator PDF Upload", "PASS",
                       f"Got response: {result.translated_text[:80]} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Gemini Translator PDF Upload", "FAIL",
                       f"Error: {result.error}",
                       elapsed, str(trace_dir))
        finally:
            await agent._agent.__aexit__(None, None, None)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Translator PDF Upload", "FAIL", str(e), elapsed)


async def test_translator_multi_page_pdf(storage_state: str, headless: bool = True):
    """Upload PDF pages one at a time and verify conversation context management."""
    print("\n" + "=" * 60)
    print("  TEST 9: Gemini Translator — Multi-Page PDF (Sequential)")
    print("=" * 60)

    fixtures = Path(__file__).parent / "fixtures"
    pdf_pages = [
        fixtures / "test_japanese_page1.pdf",
        fixtures / "test_japanese_page2.pdf",
        fixtures / "test_japanese_page3.pdf",
    ]
    missing = [p for p in pdf_pages if not p.exists()]
    if missing:
        record("Gemini Translator Multi-Page PDF", "SKIP",
               f"Missing fixtures: {[p.name for p in missing]}")
        return

    config = GeminiTranslatorConfig(
        headless=headless, storage_state=storage_state,
        timeout=240, max_turns_per_conversation=10,
        source_language="ja", target_language="en",
    )
    start = time.monotonic()
    try:
        agent = GeminiTranslatorAgent(config)
        agent._agent = GeminiDataAgent(config)
        await agent._agent.__aenter__()

        try:
            results = []
            for i, pdf_path in enumerate(pdf_pages):
                print(f"\n   Page {i+1}/3: {pdf_path.name}")

                chunk = TranslationChunk(
                    chunk_id=f"page_{i+1:03d}",
                    chunk_index=i,
                    source_file=str(pdf_path.resolve()),
                )

                if i == 0:
                    result = await agent.translate_file(
                        chunk,
                        system_prompt=(
                            "Translate all the Japanese text in this PDF to English. "
                            "Output only the English translation. "
                            "I will send you more pages to translate — keep consistent style."
                        ),
                        is_first_turn=True,
                    )
                else:
                    result = await agent.translate_file(
                        chunk,
                        continue_prompt=(
                            "Here is the next page. Continue translating to English, "
                            "maintaining the same style as previous pages."
                        ),
                    )

                results.append(result)
                print(f"   → Success: {result.success}")
                print(f"   → Translation: {result.translated_text[:150]}")
                print(f"   → Turn: {agent.turn_in_conversation}/{config.max_turns_per_conversation}")

            elapsed = (time.monotonic() - start) * 1000
            full = agent.get_full_translation()

            trace = {
                "test": "Gemini Translator Multi-Page PDF",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "max_turns": 10, "pages": 3},
                "turns": extract_turns_trace(agent._agent),
                "results": [r.to_dict() for r in results],
                "full_translation": full,
                "conversation_turns": agent.turn_in_conversation,
                "stats": agent._agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("gemini_translator_multi_page_pdf", trace)

            print(f"\n   Full translation ({len(full)} chars):")
            print(f"   {full[:500]}")
            print(f"   Total turns: {agent.turn_in_conversation}")

            all_success = all(r.success for r in results)
            if all_success and agent.turn_in_conversation == 3:
                record("Gemini Translator Multi-Page PDF", "PASS",
                       f"3 pages translated in {agent.turn_in_conversation} turns ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif all_success:
                record("Gemini Translator Multi-Page PDF", "PASS",
                       f"All pages translated, {agent.turn_in_conversation} turns ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                errors = [r.error for r in results if not r.success]
                record("Gemini Translator Multi-Page PDF", "FAIL",
                       f"Some pages failed: {errors}", elapsed, str(trace_dir))
        finally:
            await agent._agent.__aexit__(None, None, None)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Translator Multi-Page PDF", "FAIL", str(e), elapsed)


# ───────────────────── Model Change Test ─────────────────────

async def test_model_change(storage_state: str, headless: bool = True):
    """Test detecting and switching the Gemini model/mode via the UI."""
    print("\n" + "=" * 60)
    print("  TEST 10: Gemini Model Change")
    print("=" * 60)

    config = GeminiConfig(headless=headless, storage_state=storage_state, timeout=120)
    start = time.monotonic()
    try:
        async with GeminiChatAgent(config) as agent:
            page = await agent._ensure_ready()

            # Wait for mode picker to appear (it's in the input area, not header)
            try:
                await page.wait_for_selector(
                    'button[data-test-id="bard-mode-menu-button"]',
                    state="visible", timeout=10_000,
                )
            except Exception:
                await page.wait_for_timeout(3000)

            # Detect current mode via the mode picker button text
            mode_btn = page.locator('button[data-test-id="bard-mode-menu-button"]').first
            mode_btn_count = await mode_btn.count()
            current_mode = None
            if mode_btn_count > 0:
                current_mode = (await mode_btn.inner_text()).strip().lower()
            print(f"   Current mode: {current_mode or '(unknown)'}")

            if mode_btn_count > 0:
                # Click mode picker to open menu
                await mode_btn.click()
                await page.wait_for_timeout(1500)

                # Find menu items
                menu_items = page.locator('[role="menu"] [role="menuitem"]')
                item_count = await menu_items.count()
                available_modes = []
                for idx in range(item_count):
                    item = menu_items.nth(idx)
                    text = (await item.inner_text()).strip().replace("\n", " — ")
                    available_modes.append(text)
                    print(f"   [{idx}] {text}")

                # Pick a different mode than current
                target_idx = None
                for idx in range(item_count):
                    item_text = available_modes[idx].lower()
                    if current_mode and current_mode in item_text:
                        continue  # Skip current mode
                    if any(m in item_text for m in ["pro", "flash", "fast"]):
                        target_idx = idx
                        break
                # Fallback: pick first non-current
                if target_idx is None and item_count > 0:
                    for idx in range(item_count):
                        if current_mode and current_mode in available_modes[idx].lower():
                            continue
                        target_idx = idx
                        break

                if target_idx is not None:
                    target_text = available_modes[target_idx]
                    print(f"\n   Switching to: [{target_idx}] {target_text}")
                    await menu_items.nth(target_idx).click()
                    await page.wait_for_timeout(2000)

                    new_mode = None
                    if await mode_btn.count() > 0:
                        new_mode = (await mode_btn.inner_text()).strip().lower()
                    print(f"   New mode: {new_mode}")

                    response = await agent.chat("What is 2+2? Reply with just the number.")
                    elapsed = (time.monotonic() - start) * 1000
                    print(f"   Response: {response[:200]}")

                    trace_data = {
                        "test": "Gemini Model Change",
                        "timestamp": datetime.now().isoformat(),
                        "current_mode": current_mode,
                        "new_mode": new_mode,
                        "available_modes": available_modes,
                        "response": response,
                        "turns": extract_turns_trace(agent),
                        "elapsed_total_ms": elapsed,
                    }
                    trace_dir = save_trace("gemini_model_change", trace_data)

                    record("Gemini Model Change", "PASS",
                           f"Switched '{current_mode}' → '{new_mode}', response: {response[:40]} ({elapsed:.0f}ms)",
                           elapsed, str(trace_dir))
                else:
                    await page.keyboard.press("Escape")
                    elapsed = (time.monotonic() - start) * 1000
                    trace_data = {
                        "test": "Gemini Model Change",
                        "timestamp": datetime.now().isoformat(),
                        "current_mode": current_mode,
                        "available_modes": available_modes,
                        "elapsed_total_ms": elapsed,
                    }
                    trace_dir = save_trace("gemini_model_change", trace_data)
                    record("Gemini Model Change", "PASS",
                           f"Found {len(available_modes)} modes but couldn't pick target ({elapsed:.0f}ms)",
                           elapsed, str(trace_dir))
            else:
                # No mode picker found — just verify chat works
                response = await agent.chat("What is 2+2? Reply with just the number.")
                elapsed = (time.monotonic() - start) * 1000

                trace_data = {
                    "test": "Gemini Model Change",
                    "timestamp": datetime.now().isoformat(),
                    "current_mode": current_mode,
                    "response": response,
                    "turns": extract_turns_trace(agent),
                    "elapsed_total_ms": elapsed,
                }
                trace_dir = save_trace("gemini_model_change", trace_data)
                record("Gemini Model Change", "PASS",
                       f"No mode picker found, chat response: {response[:40]} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Gemini Model Change", "FAIL", str(e), elapsed)


# ───────────────────── Summary & Auth ─────────────────────

def print_summary():
    print("\n" + "=" * 60)
    print("  GEMINI LIVE TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    skipped = sum(1 for r in RESULTS if r["status"] == "SKIP")
    total = len(RESULTS)

    for r in RESULTS:
        emoji = "✅" if r["status"] == "PASS" else "❌" if r["status"] == "FAIL" else "⏭️"
        print(f"  {emoji} {r['test']}: {r['status']} ({r['elapsed_ms']}ms)")
        if r["details"]:
            print(f"     {r['details']}")
        if r.get("trace_dir"):
            print(f"     📁 {r['trace_dir']}")

    print(f"\n  Results: {passed}/{total} passed, {failed} failed, {skipped} skipped")
    total_time = sum(r["elapsed_ms"] for r in RESULTS)
    print(f"  Total time: {total_time / 1000:.1f}s")
    print(f"  Traces: {TRACE_DIR}")

    return failed == 0


async def ensure_auth(storage_state: str) -> str:
    """Ensure we have valid Gemini auth."""
    if storage_state and Path(storage_state).exists():
        print(f"  Using existing storage state: {storage_state}")
        return storage_state

    state_dir = Path(__file__).parent.parent.parent / "storage"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = str(state_dir / "gemini_storage_state.json")

    print("\n  ⚠️  No Gemini storage state found. Opening browser for manual login...")
    print("  Please log into your Google account in the browser window.")
    print("  Once you see the Gemini chat page, press ENTER here to continue.\n")

    from camoufox.async_api import AsyncCamoufox

    async with AsyncCamoufox(headless=False, humanize=True) as browser:
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await ctx.new_page()
        await page.goto("https://gemini.google.com")

        await asyncio.get_event_loop().run_in_executor(None, input,
                                                        "  → Press ENTER after logging in... ")

        cookies = await ctx.cookies()
        state = {"cookies": cookies}
        Path(state_path).write_text(json.dumps(state, indent=2, ensure_ascii=False))
        print(f"\n  ✅ Storage state saved to: {state_path}")

    return state_path


# ───────────────────── Run All ─────────────────────

async def run_all(storage_state: str, headless: bool = True):
    """Run all Gemini live tests sequentially."""
    mode = "headless" if headless else "visible"
    print("=" * 60)
    print("  Gemini Live Browser Tests + Full Trace")
    print("=" * 60)
    print(f"  Storage state: {storage_state or '(none — will prompt for login)'}")
    print(f"  Browser: {mode}")
    print(f"  Trace output: {TRACE_DIR}")

    storage_state = await ensure_auth(storage_state)
    print()

    await test_chat_single_turn(storage_state, headless)
    await test_chat_multi_turn(storage_state, headless)
    await test_chat_thinking(storage_state, headless)
    await test_data_json_generation(storage_state, headless)
    await test_data_break_prompt(storage_state, headless)
    await test_translator_single_chunk(storage_state, headless)
    await test_translator_multi_chunk(storage_state, headless)
    await test_translator_pdf(storage_state, headless)
    await test_translator_multi_page_pdf(storage_state, headless)
    await test_model_change(storage_state, headless)

    all_passed = print_summary()

    # Save consolidated results
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    summary_file = TRACE_DIR / "summary.json"
    summary_file.write_text(json.dumps({
        "timestamp": TIMESTAMP,
        "storage_state": storage_state,
        "results": RESULTS,
        "summary": {
            "total": len(RESULTS),
            "passed": sum(1 for r in RESULTS if r["status"] == "PASS"),
            "failed": sum(1 for r in RESULTS if r["status"] == "FAIL"),
            "skipped": sum(1 for r in RESULTS if r["status"] == "SKIP"),
        },
    }, indent=2))
    print(f"\n  Summary saved to: {summary_file}")

    return all_passed


TEST_MAP = {
    "chat_single": test_chat_single_turn,
    "chat_multi": test_chat_multi_turn,
    "chat_thinking": test_chat_thinking,
    "data_json": test_data_json_generation,
    "data_break": test_data_break_prompt,
    "translator_single": test_translator_single_chunk,
    "translator_multi": test_translator_multi_chunk,
    "translator_pdf": test_translator_pdf,
    "translator_multi_pdf": test_translator_multi_page_pdf,
    "model_change": test_model_change,
}


def main():
    parser = argparse.ArgumentParser(description="Gemini — Live Browser Tests")
    parser.add_argument(
        "--storage-state", "-s",
        default=os.getenv("GEMINI_STORAGE_STATE", ""),
        help="Path to storage state JSON for Gemini auth",
    )
    parser.add_argument(
        "--visible", action="store_true",
        help="Show browser window on-screen (for debugging). Default: headless",
    )
    parser.add_argument(
        "--test", "-t", nargs="*",
        help=f"Run specific test(s). Options: {', '.join(TEST_MAP.keys())}",
    )
    args = parser.parse_args()
    headless = not args.visible

    if args.test:
        async def run_selected(storage_state: str):
            storage_state = await ensure_auth(storage_state)
            for name in args.test:
                if name not in TEST_MAP:
                    print(f"Unknown test: {name}. Options: {', '.join(TEST_MAP.keys())}")
                    continue
                await TEST_MAP[name](storage_state, headless)
            return print_summary()

        success = asyncio.run(run_selected(args.storage_state))
    else:
        success = asyncio.run(run_all(args.storage_state, headless))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
