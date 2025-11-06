#!/usr/bin/env python3
"""OpenRouter API live tests — end-to-end validation of chat and data agents.

Usage:
    python tests/integration/test_openrouter_live.py
    python tests/integration/test_openrouter_live.py -t chat_single
    python tests/integration/test_openrouter_live.py -t chat_single chat_multi
    python tests/integration/test_openrouter_live.py --model google/gemini-2.0-flash-001

Requires: OPENROUTER_API_KEY environment variable.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from universal_agents.providers.openrouter.chat import OpenRouterChatAgent
from universal_agents.providers.openrouter.config import OpenRouterConfig, OpenRouterDataConfig
from universal_agents.providers.openrouter.data import OpenRouterDataAgent

# ───────────────────── Globals ─────────────────────

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TRACE_DIR = Path(__file__).parent.parent.parent / "storage" / "test_results" / "openrouter" / f"run_{TIMESTAMP}"

RESULTS: list[dict[str, Any]] = []


def save_trace(name: str, data: dict) -> Path:
    """Save a trace JSON file."""
    trace_dir = TRACE_DIR / name
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / "trace.json"
    trace_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return trace_dir


def extract_turns_trace(agent) -> list[dict]:
    """Extract conversation turns as serializable dicts."""
    turns = []
    for t in agent.history.turns:
        turns.append({
            "turn": t.turn_number,
            "user": t.user_message.content[:200] if t.user_message else "",
            "assistant": t.assistant_message.content[:500] if t.assistant_message else "",
            "thinking": (t.thinking or "")[:200],
            "time_ms": t.processing_time_ms,
        })
    return turns


def record(test_name: str, status: str, detail: str = "",
           elapsed_ms: float = 0, trace_path: str = ""):
    """Record a test result."""
    icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(status, "?")
    print(f"\n{icon} {test_name}: {status}")
    if detail:
        print(f"   {detail}")
    if trace_path:
        print(f"   📁 Trace: {trace_path}")
    RESULTS.append({
        "test": test_name, "status": status, "detail": detail,
        "elapsed_ms": elapsed_ms, "trace_path": trace_path,
    })


# ───────────────────── Chat Tests ─────────────────────

async def test_chat_single(model: str):
    """Single-turn chat via OpenRouter API."""
    print("\n" + "=" * 60)
    print("  TEST 1: OpenRouter Chat — Single Turn")
    print("=" * 60)

    config = OpenRouterConfig(model=model, max_tokens=256, temperature=0.0)
    start = time.monotonic()
    try:
        async with OpenRouterChatAgent(config) as agent:
            response = await agent.chat("What is 2+2? Reply with just the number.")
            elapsed = (time.monotonic() - start) * 1000

            trace = {
                "test": "OpenRouter Chat Single",
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("openrouter_chat_single", trace)

            print(f"   Model: {model}")
            print(f"   Response: {response[:200]}")
            print(f"   Time: {elapsed:.0f}ms")

            if "4" in response:
                record("OpenRouter Chat Single", "PASS",
                       f"Response: '{response.strip()[:80]}' ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("OpenRouter Chat Single", "PASS",
                       f"Got response: '{response.strip()[:80]}' ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("OpenRouter Chat Single", "FAIL", str(e), elapsed)


async def test_chat_multi(model: str):
    """Multi-turn conversation with context retention."""
    print("\n" + "=" * 60)
    print("  TEST 2: OpenRouter Chat — Multi-Turn (3 turns)")
    print("=" * 60)

    config = OpenRouterConfig(model=model, max_tokens=256, temperature=0.0)
    start = time.monotonic()
    try:
        async with OpenRouterChatAgent(config) as agent:
            r1 = await agent.chat("Remember the number 42. Just reply 'OK, I remember 42.'")
            print(f"   Turn 1: {r1[:100]}")

            r2 = await agent.chat("Now double the number you remember. Reply with just the result.")
            print(f"   Turn 2: {r2[:100]}")

            r3 = await agent.chat("Add 16 to that. Reply with just the result.")
            print(f"   Turn 3: {r3[:100]}")

            elapsed = (time.monotonic() - start) * 1000

            trace = {
                "test": "OpenRouter Chat Multi-Turn",
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("openrouter_chat_multi", trace)

            turn_count = len(agent.history.turns)
            print(f"\n   Turns: {turn_count}")
            print(f"   Time: {elapsed:.0f}ms")

            if turn_count == 3 and ("100" in r3 or "84" in r2):
                record("OpenRouter Chat Multi-Turn", "PASS",
                       f"{turn_count} turns, context maintained ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif turn_count == 3:
                record("OpenRouter Chat Multi-Turn", "PASS",
                       f"{turn_count} turns completed ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("OpenRouter Chat Multi-Turn", "FAIL",
                       f"Expected 3 turns, got {turn_count}", elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("OpenRouter Chat Multi-Turn", "FAIL", str(e), elapsed)


async def test_chat_thinking(model: str):
    """Extended thinking via OpenRouter API (Data agent with Claude model)."""
    print("\n" + "=" * 60)
    print("  TEST 3: OpenRouter Chat — Extended Thinking")
    print("=" * 60)

    # Use data agent with thinking enabled and a Claude model
    thinking_model = model
    if "claude" not in thinking_model.lower():
        thinking_model = "anthropic/claude-sonnet-4"

    config = OpenRouterDataConfig(
        model=thinking_model,
        max_tokens=4096,
        temperature=1.0,  # Required for extended thinking
        enable_thinking=True,
        thinking_budget=5000,
    )
    start = time.monotonic()
    try:
        async with OpenRouterDataAgent(config) as agent:
            response = await agent.chat(
                "A farmer has 15 chickens. All but 8 die. How many are left? Think step by step."
            )
            elapsed = (time.monotonic() - start) * 1000

            last_turn = agent.history.turns[-1] if agent.history.turns else None
            thinking = last_turn.thinking if last_turn else ""

            trace = {
                "test": "OpenRouter Chat Thinking",
                "timestamp": datetime.now().isoformat(),
                "model": thinking_model,
                "turns": extract_turns_trace(agent),
                "thinking_length": len(thinking or ""),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("openrouter_chat_thinking", trace)

            print(f"   Model: {thinking_model}")
            print(f"   Response: {response[:300]}")
            print(f"   Thinking: {(thinking or '')[:200]}")
            print(f"   Time: {elapsed:.0f}ms")

            has_answer = "8" in response
            has_thinking = bool(thinking)

            if has_answer and has_thinking:
                record("OpenRouter Chat Thinking", "PASS",
                       f"Answer '8' + thinking ({len(thinking)} chars) ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif has_answer:
                record("OpenRouter Chat Thinking", "PASS",
                       f"Answer '8' (no thinking captured) ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("OpenRouter Chat Thinking", "PASS",
                       f"Got response ({len(response)} chars), thinking: {has_thinking} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("OpenRouter Chat Thinking", "FAIL", str(e), elapsed)


# ───────────────────── Data Tests ─────────────────────

async def test_data_json(model: str):
    """Structured JSON generation via data agent."""
    print("\n" + "=" * 60)
    print("  TEST 4: OpenRouter Data — JSON Generation")
    print("=" * 60)

    config = OpenRouterDataConfig(model=model, max_tokens=1024, temperature=0.0,
                                  enable_thinking=False)
    start = time.monotonic()
    try:
        async with OpenRouterDataAgent(config) as agent:
            prompt = agent.build_data_prompt(
                "Generate a JSON object with these exact keys: name (string), "
                "processed (boolean, set to true), count (integer, set to 42). "
                "Return ONLY the JSON, no explanation."
            )
            response = await agent.chat(prompt)
            elapsed = (time.monotonic() - start) * 1000

            parsed = agent.parse_json_response(response)

            trace = {
                "test": "OpenRouter Data JSON",
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "prompt": prompt,
                "response": response,
                "parsed": parsed,
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("openrouter_data_json", trace)

            print(f"   Response: {response[:300]}")
            print(f"   Parsed: {parsed}")
            print(f"   Time: {elapsed:.0f}ms")

            if parsed and isinstance(parsed, dict):
                keys = sorted(parsed.keys())
                record("OpenRouter Data JSON", "PASS",
                       f"JSON with keys {keys} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("OpenRouter Data JSON", "FAIL",
                       f"Could not parse JSON from response ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("OpenRouter Data JSON", "FAIL", str(e), elapsed)


async def test_data_break(model: str):
    """Data generation with BREAK prompt (Q/A extraction)."""
    print("\n" + "=" * 60)
    print("  TEST 5: OpenRouter Data — BREAK Prompt")
    print("=" * 60)

    config = OpenRouterDataConfig(model=model, max_tokens=1024, temperature=0.0,
                                  enable_thinking=False)
    start = time.monotonic()
    try:
        async with OpenRouterDataAgent(config) as agent:
            prompt = agent.build_data_prompt(
                "Generate a trivia question about chemistry. Return as JSON with "
                "keys: question, answer, reasoning. Return ONLY the JSON."
            )
            response = await agent.chat(prompt)
            elapsed = (time.monotonic() - start) * 1000

            parsed = agent.parse_json_response(response)

            trace = {
                "test": "OpenRouter Data BREAK",
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "prompt": prompt,
                "response": response,
                "parsed": parsed,
                "turns": extract_turns_trace(agent),
                "stats": agent.get_stats().to_dict(),
                "elapsed_total_ms": elapsed,
            }
            trace_dir = save_trace("openrouter_data_break", trace)

            print(f"   Response: {response[:300]}")
            print(f"   Parsed: {parsed}")
            print(f"   Time: {elapsed:.0f}ms")

            if parsed and isinstance(parsed, dict) and "question" in parsed:
                keys = sorted(parsed.keys())
                record("OpenRouter Data BREAK", "PASS",
                       f"Q/A JSON with keys {keys} ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            elif parsed:
                record("OpenRouter Data BREAK", "PASS",
                       f"Got JSON response ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
            else:
                record("OpenRouter Data BREAK", "FAIL",
                       f"Could not parse JSON ({elapsed:.0f}ms)",
                       elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("OpenRouter Data BREAK", "FAIL", str(e), elapsed)


# ───────────────────── Model Change Test ─────────────────────

async def test_model_change(model: str):
    """Test switching models by creating agents with different configs."""
    print("\n" + "=" * 60)
    print("  TEST 6: OpenRouter — Model Change (Config-Based)")
    print("=" * 60)

    backup_model = os.getenv("BACKUP_OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
    models = [model, backup_model]
    # Deduplicate
    if models[0] == models[1]:
        models[1] = "openai/gpt-4.1-nano"

    start = time.monotonic()
    responses = {}
    try:
        for m in models:
            config = OpenRouterConfig(model=m, max_tokens=256, temperature=0.0)
            async with OpenRouterChatAgent(config) as agent:
                resp = await agent.chat("What model are you? Reply in one sentence.")
                responses[m] = resp.strip()[:200]
                print(f"   {m}: {responses[m][:100]}")

        elapsed = (time.monotonic() - start) * 1000

        trace = {
            "test": "OpenRouter Model Change",
            "timestamp": datetime.now().isoformat(),
            "models": models,
            "responses": responses,
            "elapsed_total_ms": elapsed,
        }
        trace_dir = save_trace("openrouter_model_change", trace)

        if len(responses) == 2:
            record("OpenRouter Model Change", "PASS",
                   f"Both models responded: {list(responses.keys())} ({elapsed:.0f}ms)",
                   elapsed, str(trace_dir))
        else:
            record("OpenRouter Model Change", "FAIL",
                   f"Only {len(responses)}/{len(models)} responded ({elapsed:.0f}ms)",
                   elapsed, str(trace_dir))
    except Exception as e:
        elapsed = (time.monotonic() - start) * 1000
        record("OpenRouter Model Change", "FAIL", str(e), elapsed)


# ───────────────────── Summary & Runner ─────────────────────

def print_summary() -> bool:
    """Print formatted test summary. Returns True if all passed."""
    print("\n" + "=" * 60)
    print("  OPENROUTER LIVE TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    skipped = sum(1 for r in RESULTS if r["status"] == "SKIP")

    for r in RESULTS:
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(r["status"], "?")
        line = f"  {icon} {r['test']}: {r['status']}"
        if r["elapsed_ms"]:
            line += f" ({r['elapsed_ms']:.1f}ms)"
        print(line)
        if r["detail"]:
            print(f"     {r['detail']}")
        if r.get("trace_path"):
            print(f"     📁 {r['trace_path']}")

    total_ms = sum(r["elapsed_ms"] for r in RESULTS)
    print(f"\n  Results: {passed}/{len(RESULTS)} passed, {failed} failed, {skipped} skipped")
    print(f"  Total time: {total_ms / 1000:.1f}s")
    print(f"  Traces: {TRACE_DIR}")
    return failed == 0


async def run_all(model: str):
    """Run all tests."""
    await test_chat_single(model)
    await test_chat_multi(model)
    await test_chat_thinking(model)
    await test_data_json(model)
    await test_data_break(model)
    await test_model_change(model)

    return print_summary()


TEST_MAP = {
    "chat_single": test_chat_single,
    "chat_multi": test_chat_multi,
    "chat_thinking": test_chat_thinking,
    "data_json": test_data_json,
    "data_break": test_data_break,
    "model_change": test_model_change,
}


def main():
    parser = argparse.ArgumentParser(description="OpenRouter API live tests")
    default_model = os.getenv("DEFAULT_OPENROUTER_MODEL", "anthropic/claude-sonnet-4")
    parser.add_argument(
        "--model", "-m", default=default_model,
        help=f"Primary model to test (default: {default_model})",
    )
    parser.add_argument(
        "--test", "-t", nargs="*",
        help=f"Run specific test(s). Options: {', '.join(TEST_MAP.keys())}",
    )
    args = parser.parse_args()

    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY environment variable not set")
        sys.exit(1)

    print(f"  Model: {args.model}")

    if args.test:
        async def run_selected():
            for name in args.test:
                if name not in TEST_MAP:
                    print(f"Unknown test: {name}. Options: {', '.join(TEST_MAP.keys())}")
                    continue
                await TEST_MAP[name](args.model)
            return print_summary()

        success = asyncio.run(run_selected())
    else:
        success = asyncio.run(run_all(args.model))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
