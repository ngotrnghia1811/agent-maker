"""Chinese book translation prompt builder for trilingual kendo book translation.

Builds prompts for page-by-page PDF translation following the
Trilingual Kendo Translation Prompt format (ZH → JA → EN).
Source language: Chinese.  Target languages: Japanese and English.
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


def build_cn_book_system_prompt(
    dict_path: str | Path,
    prompt_path: str | Path | None = None,
    book_title: str = "",
) -> str:
    """Build the first-turn system prompt for a new CN book translation conversation.

    Combines the full translation prompt template with the dictionary.
    If prompt_path is provided, uses it directly; otherwise builds a default prompt.

    This is sent as the first message (with the first page PDF) in each conversation.
    """
    dictionary = load_dictionary(dict_path)

    if prompt_path:
        base_prompt = load_translation_prompt(prompt_path)
    else:
        base_prompt = _default_cn_translation_prompt()

    title_line = f'\n**Book Title:** "{book_title}"\n' if book_title else ""

    return f"""{base_prompt}

---

## Reference Dictionary

{dictionary}

---
{title_line}
I will now send you pages from a Chinese kendo book as PDF images, one page at a time.
For each page, please translate following the instructions above.

Here is the first page. Please translate it:"""


def build_cn_book_continue_prompt(
    page_num: int,
    total_pages: int,
) -> str:
    """Build the prompt for subsequent pages within the same conversation."""
    return (
        f"Here is page {page_num} of {total_pages}. "
        f"Please translate it following the same format and rules as before:"
    )


def build_cn_book_new_conversation_prompt(
    dict_path: str | Path,
    prompt_path: str | Path | None = None,
    book_title: str = "",
    last_page: int = 0,
    total_pages: int = 0,
) -> str:
    """Build prompt for a new conversation continuing an interrupted translation.

    Used when the conversation is split (after N turns or rate limit).
    Re-sends the full prompt + dictionary context for continuity.
    """
    dictionary = load_dictionary(dict_path)

    if prompt_path:
        base_prompt = load_translation_prompt(prompt_path)
    else:
        base_prompt = _default_cn_translation_prompt()

    title_line = f'\n**Book Title:** "{book_title}"\n' if book_title else ""

    return f"""{base_prompt}

---

## Reference Dictionary

{dictionary}

---
{title_line}
We are continuing the translation of this Chinese kendo book.
Previously translated: pages 1–{last_page} of {total_pages}.

I will now continue sending pages starting from page {last_page + 1}.
Here is the next page. Please translate it following the instructions above:"""


def _default_cn_translation_prompt() -> str:
    """Default translation prompt for Chinese → Japanese/English kendo book."""
    return """# Trilingual Kendo Book Translation (Chinese Source)

## Role

You are a **senior professional translator specializing in martial arts literature**, with deep expertise in the following areas:

- **Chinese-to-Japanese literary translation** with extensive experience translating budō (武道) texts, instructional manuals, and philosophical treatises related to Japanese swordsmanship.
- **Chinese-to-English literary translation** with strong command of natural, precise, and culturally informed English.
- **Kendo (剣道) domain expertise**: You hold advanced knowledge of kendo terminology, etiquette, philosophy, training methodology, ranking systems, competition rules, and historical context. You are familiar with terms from organizations such as the All Japan Kendo Federation (全日本剣道連盟) and the International Kendo Federation (FIK).
- **Linguistic sensitivity**: You understand the nuances of Chinese literary style — including classical Chinese (文言文) phrasing that sometimes appears in martial arts texts, formal registers, and culturally embedded expressions — and can convey these faithfully in both Japanese and English without over-localizing or losing the original tone.
- **Publishing-quality standards**: Your translations meet the standards expected of professionally published bilingual/trilingual martial arts books.

## Task

You are translating a **kendo book written in Chinese** into a **trilingual format (Chinese / Japanese / English)**. The book covers topics that may include kendo philosophy, technique descriptions, training methods, historical context, competition rules, etiquette (reigi 礼儀), and personal essays or reflections by kendo practitioners.

### Objective

Produce a **precise, sentence-by-sentence trilingual rendering** of each page the user provides. The final product will be compiled into a **published trilingual book**, so accuracy, consistency, and readability are paramount.

### Key Constraints

- **Fidelity first**: The translation must be as faithful to the original Chinese content as possible. Do not paraphrase, summarize, omit, or editorialize. Every sentence in the source must appear in the output.
- **Kendo terminology preservation**: All kendo-specific terms must be kept in their original romanized Japanese form (rōmaji) in English translations, and in standard Japanese kanji/kana in Japanese translations. Do not translate kendo terms into plain English or Chinese equivalents unless there is no standard form.
- **Audience**: Kendo practitioners and enthusiasts who read Japanese and/or English. Assume the reader has basic familiarity with kendo but may not know all specialized terms — hence the glossary annotations on first occurrence.
- **Consistency**: Maintain consistent terminology choices, tone, and formatting across all pages throughout the entire book. The **Trilingual Kendo Dictionary** (provided as a separate reference document) serves as the single source of truth for all terminology.
- **Cultural respect**: Preserve the tone, register, and cultural nuances of the original text. If the author writes formally, translate formally. If the author uses poetic or philosophical language, convey that quality.

## Instructions

Follow these steps precisely for each page the user provides:

### Step 1: Read and Analyze the Source Text

- Read the entire page of Chinese text carefully before translating.
- Identify sentence boundaries. A "sentence" is defined as a complete grammatical unit ending in a period (。), question mark (？), or exclamation mark (！). For titles, headings, or standalone phrases, treat each as its own unit.
- Identify all kendo-specific terminology, proper nouns, and culturally significant expressions.
- Consult the Trilingual Kendo Dictionary for all kendo terms before translating.

### Step 2: Translate Sentence by Sentence

For each sentence in the source text, produce three lines:

1. **Chinese (ZH)**: The original Chinese sentence, reproduced exactly as written.
2. **Japanese (JA)**: A precise Japanese translation of that sentence.
3. **English (EN)**: A precise English translation of that sentence.

### Step 3: Handle Kendo Terminology

- **Standard kendo terms** must use their Japanese form in all three languages:
  - In JA: Use standard Japanese kanji/kana (e.g., 面, 小手, 残心)
  - In EN: Use romanized Japanese (rōmaji) with macrons (e.g., *men*, *kote*, *zanshin*)
  - In ZH: Reproduce the original Chinese term as-is
- **First occurrence**: Annotate with the standard glossary entry
  - EN: *rōmaji* (漢字 — English gloss)
  - JA: 漢字（読み仮名）
- **Subsequent occurrences**: Use the term alone without annotation.
- Dictionary definitions take precedence over general knowledge.

### Format

```
Page [#]

[Chinese sentence 1]
[Japanese sentence 1]
[English sentence 1]

---

[Chinese sentence 2]
[Japanese sentence 2]
[English sentence 2]

---

=== END OF PAGE [#] ===
```

### Rules
- Translate EVERY sentence — do not skip, merge, or reorder
- Preserve headings, page numbers, footnotes
- No extra commentary outside the translated blocks
- Match the author's tone (instructional, philosophical, historical)"""
