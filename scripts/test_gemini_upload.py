#!/usr/bin/env python3
"""Quick test: upload a .txt file to Gemini and get a response."""

import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR / "src"))

from universal_agents.providers.gemini.data import GeminiDataAgent
from universal_agents.providers.gemini.config import GeminiDataConfig


async def test_upload():
    state_path = SCRIPT_DIR / "compiled_agents/gemini_kendo_srt_translator/storage/gemini_storage_state.json"

    config = GeminiDataConfig(
        headless=False,
        storage_state=str(state_path),
    )
    agent = GeminiDataAgent(config)

    # A message with >100 words to trigger file upload
    long_message = (
        "You are a helpful assistant. Please read this message carefully and respond with "
        "exactly the text 'UPLOAD_OK' if you received this as a file attachment, or 'TYPED_OK' "
        "if this was typed into the chat input.\n\n"
        + "This is filler text to exceed 100 words. " * 20
        + "\n\nRemember: respond with only 'UPLOAD_OK' or 'TYPED_OK'."
    )

    word_count = len(long_message.split())
    logger.info("Test message has %d words (threshold: %d)", word_count, agent.LONG_MESSAGE_WORD_THRESHOLD)

    async with agent:
        response = await agent.chat(long_message)
        logger.info("Response: %s", response[:200])
        print(f"\n=== Response ===\n{response[:500]}")


if __name__ == "__main__":
    asyncio.run(test_upload())
