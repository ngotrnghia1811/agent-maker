"""Translation job example — translate text chunks with conversation splitting."""

import asyncio

from universal_agents.providers.claude.config import ClaudeTranslatorConfig
from universal_agents.providers.claude.translator import (
    ClaudeTranslatorAgent,
    ProgressState,
    TranslationChunk,
)

# Example source text (Japanese)
SOURCE_CHUNKS = [
    "量子コンピュータは、量子力学の原理を利用して計算を行うコンピュータです。",
    "従来のコンピュータがビットを使用するのに対し、量子コンピュータは量子ビット（キュービット）を使用します。",
    "キュービットは0と1の重ね合わせ状態を取ることができ、これにより並列計算が可能になります。",
]

SYSTEM_PROMPT = """You are a professional Japanese-to-English translator.
Translate the following text accurately, preserving technical terminology.
Output the translation in a bilingual format: Japanese original followed by English translation."""


async def main():
    config = ClaudeTranslatorConfig(
        max_turns_per_conversation=2,  # Low for demo
        source_language="ja",
        target_language="en",
    )

    # Create chunks
    chunks = [
        TranslationChunk(chunk_id=f"chunk_{i}", chunk_index=i, source_text=text)
        for i, text in enumerate(SOURCE_CHUNKS)
    ]

    # Set up progress tracking
    progress = ProgressState(document_id="quantum_intro", total_chunks=len(chunks))

    async with ClaudeTranslatorAgent(config) as agent:
        for chunk in chunks:
            if progress.is_chunk_completed(chunk.chunk_index):
                print(f"Skipping chunk {chunk.chunk_index} (already done)")
                continue

            # Check if we need to start a new conversation
            if agent.should_split_conversation() and chunk.chunk_index > 0:
                print(f"\nSplitting conversation at chunk {chunk.chunk_index}")
                await agent.start_new_conversation()

            is_first = agent.turn_in_conversation == 0
            result = await agent.translate_text(
                chunk,
                system_prompt=SYSTEM_PROMPT if is_first else None,
                continue_prompt="Continue translating:" if not is_first else None,
                is_first_turn=is_first,
            )

            if result.success:
                print(f"✓ Chunk {chunk.chunk_index}: {result.translated_text[:100]}...")
                progress.mark_completed(chunk.chunk_index)
                progress.save("translation_progress.json")
            else:
                print(f"✗ Chunk {chunk.chunk_index}: {result.error}")

        # Export results
        full_text = agent.get_full_translation()
        print(f"\n{'='*60}")
        print(f"Full translation ({len(full_text)} chars):")
        print(full_text[:500])
        agent.export_results("translation_results.json")


if __name__ == "__main__":
    asyncio.run(main())
