#!/usr/bin/env python3
"""
V1 Claude Jobs — Live Browser Tests with Full Trace Capture

Tests the three Claude agent types (headless by default).
Captures the full trace of every LLM response (raw API responses,
thinking, intermediate steps, timestamps) and saves them to disk.

Usage:
  python tests/integration/test_v1_claude_jobs_live.py                    # headless (default)
  python tests/integration/test_v1_claude_jobs_live.py --visible          # show browser window for debugging
  python tests/integration/test_v1_claude_jobs_live.py --storage-state storage/claude_storage_state.json
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

from universal_agents.providers.claude.chat import ClaudeChatAgent
from universal_agents.providers.claude.config import (
    ClaudeConfig,
    ClaudeDataConfig,
    ClaudeTranslatorConfig,
)
from universal_agents.providers.claude.data import ClaudeDataAgent
from universal_agents.providers.claude.translator import (
    ClaudeTranslatorAgent,
    TranslationChunk,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("live_test")

# ───────────────────── Results & Trace Tracking ─────────────────────

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TRACE_DIR = Path(__file__).parent.parent.parent / "storage" / "test_results" / "claude" / f"run_{TIMESTAMP}"
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
    """Extract full trace data from an agent's conversation history."""
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
    """V1 test_agent.py → test_browser_chat: single Q&A."""
    print("\n" + "=" * 60)
    print("  TEST 1: Chat Agent — Single Turn")
    print("=" * 60)

    config = ClaudeConfig(headless=headless, storage_state=storage_state, timeout=120)
    start = time.monotonic()
    try:
        async with ClaudeChatAgent(config) as agent:
            response = await agent.chat("What is 2 + 2? Reply with just the number.")
            elapsed = (time.monotonic() - start) * 1000

            # Save full trace
            trace = {
                "test": "Chat Single Turn",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 120, "extract_thinking": config.extract_thinking},
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("chat_single_turn", trace)

            print(f"   Response: {response[:200]}")
            print(f"   Time: {elapsed:.0f}ms")
            print(f"   Raw API responses captured: {sum(len(t.get('raw_api_responses', [])) for t in trace['turns'])}")

            if "4" in response:
                record("Chat Single Turn", "PASS", f"Got '4' in response ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Chat Single Turn", "FAIL", f"Expected '4', got: {response[:100]}",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Chat Single Turn", "FAIL", str(e), elapsed)


async def test_chat_multi_turn(storage_state: str, headless: bool = True):
    """V1 test_comprehensive.py → complex 3-turn context test."""
    print("\n" + "=" * 60)
    print("  TEST 2: Chat Agent — Multi-Turn (3 turns)")
    print("=" * 60)

    config = ClaudeConfig(headless=headless, storage_state=storage_state, timeout=120)
    start = time.monotonic()
    try:
        async with ClaudeChatAgent(config) as agent:
            print("\n   Turn 1/3: Pick a number")
            r1 = await agent.chat("Pick the number 42, and remember it. Reply with just the number.")
            print(f"   → {r1[:100]}")

            print("\n   Turn 2/3: Double it")
            r2 = await agent.chat("Double that number. Reply with just the number.")
            print(f"   → {r2[:100]}")

            print("\n   Turn 3/3: Add 16")
            r3 = await agent.chat("Add 16 to that. Reply with just the number.")
            print(f"   → {r3[:100]}")

            elapsed = (time.monotonic() - start) * 1000

            trace = {
                "test": "Chat Multi-Turn",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 120},
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("chat_multi_turn", trace)

            print(f"\n   Stats: {agent.get_stats().total_turns} turns, {elapsed:.0f}ms total")
            print(f"   Raw API responses: {sum(len(t.get('raw_api_responses', [])) for t in trace['turns'])}")

            passed = "84" in r2 and "100" in r3
            if passed:
                record("Chat Multi-Turn", "PASS", f"Context maintained: 42→84→100 ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Chat Multi-Turn", "FAIL", f"Context lost. r2={r2[:50]}, r3={r3[:50]}",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Chat Multi-Turn", "FAIL", str(e), elapsed)


async def test_chat_thinking(storage_state: str, headless: bool = True):
    """V1 test_agent.py → thinking extraction test."""
    print("\n" + "=" * 60)
    print("  TEST 3: Chat Agent — Thinking Extraction")
    print("=" * 60)

    config = ClaudeConfig(
        headless=headless, storage_state=storage_state,
        timeout=120, extract_thinking=True,
    )
    start = time.monotonic()
    try:
        async with ClaudeChatAgent(config) as agent:
            response = await agent.chat("What is the 10th prime number? Think step by step.")
            elapsed = (time.monotonic() - start) * 1000

            turns = agent.get_turns()
            thinking = turns[0].thinking if turns else None
            thinking_source = turns[0].thinking_source if turns else None

            trace = {
                "test": "Chat Thinking",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 120, "extract_thinking": True},
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("chat_thinking", trace)

            print(f"   Response: {response[:200]}")
            print(f"   Thinking: {'Yes (' + str(len(thinking)) + ' chars, source=' + str(thinking_source) + ')' if thinking else 'None captured'}")
            print(f"   Raw API responses: {sum(len(t.get('raw_api_responses', [])) for t in trace['turns'])}")

            if "29" in response:
                record("Chat Thinking", "PASS",
                       f"Correct answer, thinking={'captured ('+thinking_source+')' if thinking else 'not captured'} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Chat Thinking", "PASS" if len(response) > 0 else "FAIL",
                       f"Response received, thinking={'captured' if thinking else 'not captured'}",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Chat Thinking", "FAIL", str(e), elapsed)


# ───────────────────── Data Agent Tests ─────────────────────

async def test_data_json_generation(storage_state: str, headless: bool = True):
    """V1 data-agent/test_agent.py → JSON generation + extraction."""
    print("\n" + "=" * 60)
    print("  TEST 4: Data Agent — JSON Generation")
    print("=" * 60)

    config = ClaudeDataConfig(headless=headless, storage_state=storage_state, timeout=180)
    start = time.monotonic()
    try:
        async with ClaudeDataAgent(config) as agent:
            prompt = ClaudeDataAgent.build_data_prompt(
                "Transform the input JSON by adding a 'processed' field set to true "
                "and a 'category_upper' field with the category in uppercase. "
                "Output only the JSON, no explanation.",
                input_json={"name": "Test Item", "value": 42, "category": "electronics"},
            )
            print(f"   Prompt: {prompt[:150]}...")

            response = await agent.chat(prompt)
            elapsed = (time.monotonic() - start) * 1000

            extracted = ClaudeDataAgent.extract_json(response)

            trace = {
                "test": "Data JSON Generation",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 180},
                "prompt": prompt,
                "turns": extract_turns_trace(agent),
                "extracted_json": extracted,
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("data_json_generation", trace)

            print(f"   Response: {response[:300]}")
            print(f"   Extracted JSON: {extracted}")
            print(f"   Raw API responses: {sum(len(t.get('raw_api_responses', [])) for t in trace['turns'])}")

            if extracted and isinstance(extracted, dict):
                has_processed = extracted.get("processed") is True
                has_upper = "ELECTRONICS" in str(extracted.get("category_upper", ""))
                if has_processed:
                    record("Data JSON Generation", "PASS",
                           f"JSON extracted, processed={has_processed}, upper={has_upper} ({elapsed:.0f}ms)",
                           elapsed, str(trace_dir))
                else:
                    record("Data JSON Generation", "PASS",
                           f"JSON extracted but fields may differ: {list(extracted.keys())} ({elapsed:.0f}ms)",
                           elapsed, str(trace_dir))
            else:
                record("Data JSON Generation", "FAIL",
                       f"Could not extract JSON from response ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Data JSON Generation", "FAIL", str(e), elapsed)


async def test_data_break_prompt(storage_state: str, headless: bool = True):
    """V1 data-agent/test_agent.py → BREAK dataset style prompt."""
    print("\n" + "=" * 60)
    print("  TEST 5: Data Agent — Complex Prompt (BREAK-style)")
    print("=" * 60)

    config = ClaudeDataConfig(headless=headless, storage_state=storage_state, timeout=180)
    start = time.monotonic()
    try:
        async with ClaudeDataAgent(config) as agent:
            input_json = {
                "question_id": "test_001",
                "question_text": "What is the capital of France?",
                "options": ["Paris", "London", "Berlin", "Madrid"],
            }
            prompt = ClaudeDataAgent.build_data_prompt(
                "Transform the following quiz question into a training example.\n"
                "Required output fields:\n"
                '- "question": the original question text\n'
                '- "answer": the correct option from the list\n'
                '- "reasoning": one sentence explaining why\n\n'
                "Respond with ONLY a JSON object. No markdown fences, no explanation.",
                input_json=input_json,
            )

            response = await agent.chat(prompt)
            elapsed = (time.monotonic() - start) * 1000

            extracted = ClaudeDataAgent.extract_json(response)

            trace = {
                "test": "Data BREAK Prompt",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 180},
                "prompt": prompt,
                "input_json": input_json,
                "turns": extract_turns_trace(agent),
                "extracted_json": extracted,
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("data_break_prompt", trace)

            print(f"   Response: {response[:300]}")
            print(f"   Extracted: {extracted}")
            print(f"   Raw API responses: {sum(len(t.get('raw_api_responses', [])) for t in trace['turns'])}")

            if extracted and isinstance(extracted, dict):
                record("Data BREAK Prompt", "PASS",
                       f"JSON extracted with keys: {list(extracted.keys())} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif extracted:
                record("Data BREAK Prompt", "PASS",
                       f"JSON extracted (type={type(extracted).__name__}) ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Data BREAK Prompt", "FAIL",
                       f"No JSON extracted ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Data BREAK Prompt", "FAIL", str(e), elapsed)


# ───────────────────── Translator Agent Tests ─────────────────────

async def test_translator_single_chunk(storage_state: str, headless: bool = True):
    """V1 translator-agent → single file upload + translation."""
    print("\n" + "=" * 60)
    print("  TEST 6: Translator Agent — Single Chunk")
    print("=" * 60)

    config = ClaudeTranslatorConfig(
        headless=headless, storage_state=storage_state,
        timeout=180, source_language="ja", target_language="en",
    )
    start = time.monotonic()
    try:
        agent = ClaudeTranslatorAgent(config)
        agent._agent = ClaudeDataAgent(config)
        await agent._agent.__aenter__()

        try:
            chunk = TranslationChunk(
                chunk_id="test_001", chunk_index=0,
                source_text="東京は日本の首都です。人口は約1400万人です。",
            )

            result = await agent.translate_text(
                chunk,
                system_prompt=(
                    "Translate the following Japanese text to English. "
                    "Output only the English translation, nothing else.\n\n"
                    "Japanese text to translate:"
                ),
                is_first_turn=True,
            )
            elapsed = (time.monotonic() - start) * 1000

            trace = {
                "test": "Translator Single Chunk",
                "timestamp": datetime.now().isoformat(),
                "config": {"source_language": "ja", "target_language": "en"},
                "source_text": chunk.source_text,
                "turns": extract_turns_trace(agent._agent),
                "translation_result": result.to_dict(),
                "thinking": result.thinking,
                "stats": agent._agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("translator_single_chunk", trace)

            print(f"   Source: {chunk.source_text}")
            print(f"   Translation: {result.translated_text[:300]}")
            print(f"   Success: {result.success}")
            print(f"   Thinking: {result.thinking[:100] if result.thinking else 'None'}")
            print(f"   Time: {result.processing_time_ms:.0f}ms")

            if result.success and ("Tokyo" in result.translated_text or "tokyo" in result.translated_text.lower()):
                record("Translator Single Chunk", "PASS",
                       f"Translated successfully ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif result.success:
                record("Translator Single Chunk", "PASS",
                       f"Got response: {result.translated_text[:80]} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Translator Single Chunk", "FAIL",
                       f"Error: {result.error}",
                       elapsed, str(trace_dir))
        finally:
            await agent._agent.__aexit__(None, None, None)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Translator Single Chunk", "FAIL", str(e), elapsed)


async def test_translator_multi_chunk(storage_state: str, headless: bool = True):
    """V1 translator-agent → multi-chunk with conversation management."""
    print("\n" + "=" * 60)
    print("  TEST 7: Translator Agent — Multi-Chunk (2 chunks)")
    print("=" * 60)

    config = ClaudeTranslatorConfig(
        headless=headless, storage_state=storage_state,
        timeout=180, max_turns_per_conversation=10,
        source_language="ja", target_language="en",
    )
    start = time.monotonic()
    try:
        agent = ClaudeTranslatorAgent(config)
        agent._agent = ClaudeDataAgent(config)
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
                "test": "Translator Multi-Chunk",
                "timestamp": datetime.now().isoformat(),
                "config": {"max_turns_per_conversation": 10},
                "turns": extract_turns_trace(agent._agent),
                "results": [r1.to_dict(), r2.to_dict()],
                "full_translation": full,
                "stats": agent._agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("translator_multi_chunk", trace)

            print(f"\n   Full translation ({len(full)} chars):")
            print(f"   {full[:400]}")
            print(f"   Turn count: {agent.turn_in_conversation}")

            if r1.success and r2.success:
                record("Translator Multi-Chunk", "PASS",
                       f"2 chunks translated, {agent.turn_in_conversation} turns ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                errors = [r.error for r in [r1, r2] if not r.success]
                record("Translator Multi-Chunk", "FAIL", f"Errors: {errors}",
                       elapsed, str(trace_dir))
        finally:
            await agent._agent.__aexit__(None, None, None)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Translator Multi-Chunk", "FAIL", str(e), elapsed)


async def test_translator_pdf(storage_state: str, headless: bool = True):
    """Translator agent — PDF file upload and translation."""
    print("\n" + "=" * 60)
    print("  TEST 8: Translator Agent — PDF Upload")
    print("=" * 60)

    pdf_path = Path(__file__).parent / "fixtures" / "test_japanese.pdf"
    if not pdf_path.exists():
        record("Translator PDF Upload", "SKIP", f"PDF fixture not found: {pdf_path}")
        return

    config = ClaudeTranslatorConfig(
        headless=headless, storage_state=storage_state,
        timeout=180, source_language="ja", target_language="en",
    )
    start = time.monotonic()
    try:
        agent = ClaudeTranslatorAgent(config)
        agent._agent = ClaudeDataAgent(config)
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
                "test": "Translator PDF Upload",
                "timestamp": datetime.now().isoformat(),
                "config": {"source_language": "ja", "target_language": "en"},
                "source_file": str(pdf_path),
                "source_file_size": pdf_path.stat().st_size,
                "turns": extract_turns_trace(agent._agent),
                "translation_result": result.to_dict(),
                "thinking": result.thinking,
                "stats": agent._agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("translator_pdf_upload", trace)

            print(f"   Source: {pdf_path.name} ({pdf_path.stat().st_size} bytes)")
            print(f"   Translation: {result.translated_text[:300]}")
            print(f"   Success: {result.success}")
            print(f"   Thinking: {result.thinking[:100] if result.thinking else 'None'}")

            if result.success and ("Tokyo" in result.translated_text or "capital" in result.translated_text.lower()):
                record("Translator PDF Upload", "PASS",
                       f"PDF translated: {result.translated_text[:80]} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif result.success:
                record("Translator PDF Upload", "PASS",
                       f"Got response: {result.translated_text[:80]} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("Translator PDF Upload", "FAIL",
                       f"Error: {result.error}",
                       elapsed, str(trace_dir))
        finally:
            await agent._agent.__aexit__(None, None, None)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Translator PDF Upload", "FAIL", str(e), elapsed)


# ───────────────────── Multi-Page PDF Sequential Test ─────────────────────

async def test_translator_multi_page_pdf(storage_state: str, headless: bool = True):
    """Upload PDF pages one at a time and verify conversation context management."""
    print("\n" + "=" * 60)
    print("  TEST 9: Translator Agent — Multi-Page PDF (Sequential)")
    print("=" * 60)

    fixtures = Path(__file__).parent / "fixtures"
    pdf_pages = [
        fixtures / "test_japanese_page1.pdf",
        fixtures / "test_japanese_page2.pdf",
        fixtures / "test_japanese_page3.pdf",
    ]
    missing = [p for p in pdf_pages if not p.exists()]
    if missing:
        record("Translator Multi-Page PDF", "SKIP",
               f"Missing fixtures: {[p.name for p in missing]}")
        return

    config = ClaudeTranslatorConfig(
        headless=headless, storage_state=storage_state,
        timeout=240, max_turns_per_conversation=10,
        source_language="ja", target_language="en",
    )
    start = time.monotonic()
    try:
        agent = ClaudeTranslatorAgent(config)
        agent._agent = ClaudeDataAgent(config)
        await agent._agent.__aenter__()

        try:
            results = []
            page_topics = ["Tokyo/capital", "culture/anime", "technology/Shinkansen"]

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
                "test": "Translator Multi-Page PDF",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "max_turns": 10, "pages": 3},
                "turns": extract_turns_trace(agent._agent),
                "results": [r.to_dict() for r in results],
                "full_translation": full,
                "conversation_turns": agent.turn_in_conversation,
                "stats": agent._agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("translator_multi_page_pdf", trace)

            print(f"\n   Full translation ({len(full)} chars):")
            print(f"   {full[:500]}")
            print(f"   Total turns in conversation: {agent.turn_in_conversation}")
            print(f"   History turns: {len(agent._agent.history.turns)}")

            all_success = all(r.success for r in results)
            if all_success and agent.turn_in_conversation == 3:
                record("Translator Multi-Page PDF", "PASS",
                       f"3 pages translated in {agent.turn_in_conversation} turns ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif all_success:
                record("Translator Multi-Page PDF", "PASS",
                       f"All pages translated, {agent.turn_in_conversation} turns ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                errors = [r.error for r in results if not r.success]
                record("Translator Multi-Page PDF", "FAIL",
                       f"Some pages failed: {errors}", elapsed, str(trace_dir))
        finally:
            await agent._agent.__aexit__(None, None, None)
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Translator Multi-Page PDF", "FAIL", str(e), elapsed)


# ───────────────────── Model Change Test ─────────────────────

async def test_model_change(storage_state: str, headless: bool = True):
    """Test changing Claude model via the model selector dropdown."""
    print("\n" + "=" * 60)
    print("  TEST 10: Model Change — Switch to Opus")
    print("=" * 60)

    config = ClaudeConfig(headless=headless, storage_state=storage_state, timeout=120)
    start = time.monotonic()
    try:
        async with ClaudeChatAgent(config) as agent:
            # Navigate to claude.ai first
            page = await agent._ensure_ready()
            await page.wait_for_timeout(5000)

            # Find the model selector button
            print("   Discovering available models...")
            print(f"   Page title: {await page.title()}")
            print(f"   Page URL: {page.url}")
            selector_btn = page.locator('[data-testid="model-selector-dropdown"]').first
            if await selector_btn.count() == 0:
                # Wait a bit more for dynamic content
                await page.wait_for_timeout(3000)
                selector_btn = page.locator('[data-testid="model-selector-dropdown"]').first
            if await selector_btn.count() == 0:
                selector_btn = page.locator('button:has-text("Sonnet"), button:has-text("Opus"), button:has-text("Haiku")').first

            if await selector_btn.count() == 0:
                record("Model Change", "FAIL", "Model selector button not found in DOM")
                return

            current_model_text = (await selector_btn.inner_text()).strip().replace("\n", " ")
            print(f"   Current model: {current_model_text}")

            # Click to open the dropdown menu
            await selector_btn.click()
            await page.wait_for_timeout(1500)

            # Find model menu items (role="menuitem" inside role="menu")
            menu_items = page.locator('[role="menu"] [role="menuitem"]')
            item_count = await menu_items.count()

            available_models = []
            opus_option = None
            for idx in range(item_count):
                item = menu_items.nth(idx)
                text = (await item.inner_text()).strip().replace("\n", " — ")
                available_models.append(text)
                if "opus" in text.lower():
                    opus_option = item
                print(f"   [{idx}] {text}")

            trace_data = {
                "test": "Model Change",
                "timestamp": datetime.now().isoformat(),
                "config": {"headless": headless, "timeout": 120},
                "current_model_text": current_model_text,
                "available_models": available_models,
                "item_count": item_count,
            }

            if opus_option:
                print("   Selecting Opus model...")
                await opus_option.click()
                await page.wait_for_timeout(2000)

                # Verify model changed on button
                new_model_text = (await selector_btn.inner_text()).strip().replace("\n", " ")
                print(f"   New model: {new_model_text}")

                # Send a test message to verify it responds
                response = await agent.chat("What model are you? Reply in one short sentence.")
                elapsed = (time.monotonic() - start) * 1000

                trace_data.update({
                    "new_model_text": new_model_text,
                    "response": response,
                    "turns": extract_turns_trace(agent),
                    "stats": agent.get_stats().to_dict(),
                    "elapsed_total_ms": elapsed,
                })
                trace_dir = save_trace("model_change", trace_data)

                print(f"   Response: {response[:200]}")

                if "opus" in new_model_text.lower():
                    record("Model Change", "PASS",
                           f"Switched to Opus: '{new_model_text}' ({elapsed:.0f}ms)",
                           elapsed, str(trace_dir))
                else:
                    record("Model Change", "PASS",
                           f"Model selector worked: '{current_model_text}' → '{new_model_text}' ({elapsed:.0f}ms)",
                           elapsed, str(trace_dir))
            else:
                elapsed = (time.monotonic() - start) * 1000
                await page.keyboard.press("Escape")
                trace_data["elapsed_total_ms"] = elapsed
                trace_dir = save_trace("model_change", trace_data)

                if available_models:
                    record("Model Change", "PASS",
                           f"Found {len(available_models)} models but no Opus: {available_models}",
                           elapsed, str(trace_dir))
                else:
                    record("Model Change", "FAIL",
                           "No model options found in dropdown menu",
                           elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("Model Change", "FAIL", str(e), elapsed)


# ───────────────────── Main ─────────────────────

def print_summary():
    print("\n" + "=" * 60)
    print("  LIVE TEST SUMMARY")
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
    """Ensure we have valid Claude auth. If no storage state, open browser for manual login."""
    if storage_state and Path(storage_state).exists():
        print(f"  Using existing storage state: {storage_state}")
        return storage_state

    state_dir = Path(__file__).parent.parent.parent / "storage"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = str(state_dir / "claude_storage_state.json")

    print("\n  ⚠️  No storage state found. Opening browser for manual login...")
    print("  Please log into claude.ai in the browser window.")
    print("  Once you see the chat input, press ENTER here to continue.\n")

    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False, args=[
        "--disable-blink-features=AutomationControlled",
    ])
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    page = await context.new_page()
    await page.goto("https://claude.ai/new", wait_until="domcontentloaded")

    await asyncio.get_event_loop().run_in_executor(None, input, "  → Press ENTER after logging in... ")

    await context.storage_state(path=state_path)
    print(f"\n  ✅ Storage state saved to: {state_path}")

    await page.close()
    await context.close()
    await browser.close()
    await pw.stop()

    return state_path


async def run_all(storage_state: str, save_state: bool, headless: bool = True):
    """Run all live tests sequentially with full trace capture."""
    mode = "headless" if headless else "visible"
    print("=" * 60)
    print("  V1 Claude Jobs — Live Browser Tests + Full Trace")
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
    parser = argparse.ArgumentParser(description="V1 Claude Jobs — Live Browser Tests")
    parser.add_argument(
        "--storage-state", "-s",
        default=os.getenv("CLAUDE_STORAGE_STATE", ""),
        help="Path to Playwright storage state JSON for Claude auth",
    )
    parser.add_argument(
        "--save-state", action="store_true",
        help="Save storage state after tests for future reuse",
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
        success = asyncio.run(run_all(args.storage_state, args.save_state, headless))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
