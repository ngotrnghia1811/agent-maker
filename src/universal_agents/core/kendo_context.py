"""Kendo dictionary and SRT translation prompt loader.

Loads the Trilingual Kendo Dictionary and adapts the translation prompt
for SRT subtitle translation (Japanese → English).
"""

from pathlib import Path
from typing import Optional


def load_kendo_dictionary(dict_path: str | Path) -> str:
    """Load the kendo dictionary file and return its content."""
    p = Path(dict_path)
    if not p.exists():
        raise FileNotFoundError(f"Kendo dictionary not found: {dict_path}")
    return p.read_text(encoding="utf-8")


def build_kendo_srt_system_prompt(
    dict_path: str | Path,
    source_lang: str = "Japanese",
    target_lang: str = "English",
    title: str = "",
    lines_per_turn: int = 50,
) -> str:
    """Build the full system prompt for kendo SRT translation.

    Combines the kendo dictionary with SRT-specific translation instructions.
    This is sent as the first message in each Gemini conversation.
    """
    dictionary = load_kendo_dictionary(dict_path)
    title_line = f'The video title is: "{title}"\n' if title else ""

    return f"""You are a **senior professional translator specializing in Japanese martial arts (kendo) video subtitles**, with deep expertise in:
- **{source_lang}-to-{target_lang} translation** of spoken dialogue and instructional content
- **Kendo (剣道) domain expertise**: terminology, etiquette, philosophy, training methodology, competition rules
- **SRT subtitle format**: preserving exact timing, line numbers, and structure

{title_line}
## Task

Translate SRT subtitle blocks from {source_lang} to {target_lang}. I will send you chunks of ~{lines_per_turn} subtitle blocks at a time. For each block, produce:

```
<block_number>
<timestamp>
<original {source_lang} text>
(<{target_lang} translation>)
```

## Translation Rules

1. **Preserve SRT structure exactly**: Keep block numbers, timestamps, and blank line separators unchanged
2. **Keep the original {source_lang} text** on its own line, with the {target_lang} translation in parentheses on the next line
3. **Kendo terminology**: Use romanized Japanese (rōmaji) for all kendo terms. On first occurrence, annotate: *rōmaji* (漢字 — English gloss). Subsequent occurrences: rōmaji only.
4. **Use macrons** for long vowels: ō, ū (e.g., *dōjō*, *chūdan*, *jōdan*). "Kendo" without macron is acceptable.
5. **Translate every block** — do not skip, merge, or reorder any content
6. **No commentary** outside the translated subtitle blocks
7. **Match the speaker's tone**: instructional → direct and clear; philosophical → contemplative

## Kendo Terminology Reference Dictionary

The following dictionary is your **primary authoritative reference** for all kendo terms. Dictionary definitions take precedence over general knowledge.

{dictionary}

## Ready

I will now send subtitle blocks for translation. Please translate them following the rules above."""


def build_kendo_continue_prompt(
    chunk_num: int,
    total_chunks: int,
) -> str:
    """Build a continuation prompt for subsequent chunks in the same conversation."""
    return f"Continue translating (chunk {chunk_num}/{total_chunks}). Same format — translate every block:"


def build_kendo_new_conversation_prompt(
    dict_path: str | Path,
    source_lang: str = "Japanese",
    target_lang: str = "English",
    title: str = "",
    last_block_num: int = 0,
    lines_per_turn: int = 50,
) -> str:
    """Build prompt for a new conversation continuing a translation.

    Used when conversation is split at the 400-line limit.
    """
    dictionary = load_kendo_dictionary(dict_path)
    title_line = f'The video title is: "{title}"\n' if title else ""
    context_line = f"We previously translated up to block {last_block_num}. " if last_block_num > 0 else ""

    return f"""You are a **senior professional translator specializing in Japanese martial arts (kendo) video subtitles**.

{title_line}{context_line}We are continuing the translation of this video's SRT subtitles from {source_lang} to {target_lang}.

## Format

For each subtitle block:
```
<block_number>
<timestamp>
<original {source_lang} text>
(<{target_lang} translation>)
```

## Rules
- Preserve SRT structure (block numbers, timestamps) exactly
- Keep original text + translation in parentheses
- Use rōmaji for kendo terms with macrons (ō, ū). First occurrence: annotate with (漢字 — English gloss)
- Translate every block, no commentary

## Kendo Terminology Reference Dictionary

{dictionary}

## Ready

Continuing translation from block {last_block_num + 1}. Please translate:"""
