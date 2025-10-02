"""Book translation prompt builder for trilingual kendo book translation.

Builds prompts for page-by-page PDF translation following the
Trilingual Kendo Translation Prompt format (JA → EN → ZH).
"""

from pathlib import Path


def load_dictionary(dict_path: str | Path) -> str:
    """Load the kendo dictionary file."""
    p = Path(dict_path)
    if not p.exists():
        raise FileNotFoundError(f"Dictionary not found: {dict_path}")
    return p.read_text(encoding="utf-8")


def load_translation_prompt(prompt_path: str | Path) -> str:
    """Load the translation prompt template file."""
    p = Path(prompt_path)
    if not p.exists():
        raise FileNotFoundError(f"Translation prompt not found: {prompt_path}")
    return p.read_text(encoding="utf-8")


def build_book_system_prompt(
    dict_path: str | Path,
    prompt_path: str | Path | None = None,
    book_title: str = "",
) -> str:
    """Build the first-turn system prompt for a new book translation conversation.

    Combines the full translation prompt template with the dictionary.
    If prompt_path is provided, uses it directly; otherwise builds a default prompt.

    This is sent as the first message (with the first page PDF) in each conversation.
    """
    dictionary = load_dictionary(dict_path)

    if prompt_path:
        base_prompt = load_translation_prompt(prompt_path)
    else:
        base_prompt = _default_translation_prompt()

    title_line = f'\n**Book Title:** "{book_title}"\n' if book_title else ""

    return f"""{base_prompt}

---

## Reference Dictionary

{dictionary}

---
{title_line}
I will now send you pages from a kendo book as PDF images, one page at a time.
For each page, please translate following the instructions above.

Here is the first page. Please translate it:"""


def build_book_continue_prompt(
    page_num: int,
    total_pages: int,
) -> str:
    """Build the prompt for subsequent pages within the same conversation."""
    return (
        f"Here is page {page_num} of {total_pages}. "
        f"Please translate it following the same format and rules as before:"
    )


def build_book_new_conversation_prompt(
    dict_path: str | Path,
    prompt_path: str | Path | None = None,
    book_title: str = "",
    last_page: int = 0,
    total_pages: int = 0,
) -> str:
    """Build prompt for a new conversation continuing an interrupted translation.

    Used when the conversation is split (after 15 turns or rate limit).
    Re-sends the full prompt + dictionary context for continuity.
    """
    dictionary = load_dictionary(dict_path)

    if prompt_path:
        base_prompt = load_translation_prompt(prompt_path)
    else:
        base_prompt = _default_translation_prompt()

    title_line = f'\n**Book Title:** "{book_title}"\n' if book_title else ""

    return f"""{base_prompt}

---

## Reference Dictionary

{dictionary}

---
{title_line}
We are continuing the translation of this book.
Previously translated: pages 1–{last_page} of {total_pages}.

I will now continue sending pages starting from page {last_page + 1}.
Here is the next page. Please translate it following the instructions above:"""


def _default_translation_prompt() -> str:
    """Fallback translation prompt if no prompt file is provided."""
    return """# Trilingual Kendo Book Translation

## Role

You are a senior professional translator specializing in Japanese martial arts literature.
You have deep expertise in Japanese-to-English and Japanese-to-Chinese translation,
with extensive knowledge of kendo terminology, etiquette, philosophy, and training methodology.

## Task

Translate a kendo book from Japanese into a trilingual format (Japanese / English / Chinese).
Produce a precise, sentence-by-sentence trilingual rendering of each page.

## Instructions

For each sentence in the source text, produce three lines:
1. **Japanese (JA)**: The original Japanese sentence, reproduced exactly.
2. **English (EN)**: A precise English translation.
3. **Chinese (ZH)**: A precise Chinese (Simplified Mandarin) translation.

### Kendo Terminology Rules
- Keep all kendo terms in romanized Japanese (rōmaji) with macrons (ō, ū).
- First occurrence: annotate with *rōmaji* (漢字 — English gloss) / *rōmaji*（漢字——中文释义）
- Subsequent occurrences: rōmaji only.
- Dictionary definitions take precedence over general knowledge.

### Format

```
Page [#]

[Japanese sentence 1]
[English sentence 1]
[Chinese sentence 1]

---

[Japanese sentence 2]
[English sentence 2]
[Chinese sentence 2]

---

=== END OF PAGE [#] ===
```

### Rules
- Translate EVERY sentence — do not skip, merge, or reorder
- Preserve headings, page numbers, footnotes
- No extra commentary outside the translated blocks
- Match the author's tone (instructional, philosophical, historical)"""
