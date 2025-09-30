"""Translation prompt templates for book and transcript modes.

Provides system prompts and continuation prompts specialized for:
- Book / document translation (paragraph-based)
- Transcript / subtitle translation (SRT format preserving)
"""


def get_system_prompt(
    source_lang: str = "Japanese",
    target_lang: str = "English",
    mode: str = "book",
    title: str = "",
) -> str:
    """Get the system prompt for the first turn of a translation.

    Args:
        source_lang: Source language name.
        target_lang: Target language name.
        mode: "book" or "transcript".
        title: Optional document/video title.
    """
    if mode == "transcript":
        return _transcript_system_prompt(source_lang, target_lang, title)
    return _book_system_prompt(source_lang, target_lang, title)


def get_continue_prompt(mode: str = "book", chunk_num: int = 0) -> str:
    """Get the continuation prompt for subsequent chunks."""
    if mode == "transcript":
        if chunk_num > 0:
            return f"Continue translating (chunk {chunk_num}). Same format as before:"
        return "Continue translating in the same format:"
    if chunk_num > 0:
        return f"Continue translating from where you left off (chunk {chunk_num}):"
    return "Continue translating from where you left off:"


def get_new_conversation_prompt(
    source_lang: str = "Japanese",
    target_lang: str = "English",
    mode: str = "book",
    title: str = "",
    last_line: int = 0,
) -> str:
    """Get prompt for starting a new conversation mid-document.

    Used when conversation is split due to exceeding max_turns.
    """
    if mode == "transcript":
        return _transcript_new_conversation_prompt(source_lang, target_lang, title, last_line)
    return _book_new_conversation_prompt(source_lang, target_lang, title)


# ------------------------------------------------------------------
# Book mode prompts
# ------------------------------------------------------------------

def _book_system_prompt(source_lang: str, target_lang: str, title: str) -> str:
    title_line = f'The document is: "{title}"\n' if title else ""
    return f"""You are a professional translator specializing in {source_lang} to {target_lang} translation.

{title_line}I will send you text in chunks for translation.

**Guidelines:**
- Translate naturally and fluently — not word-for-word
- Preserve paragraph structure and formatting
- Keep domain-specific terms that have no direct equivalent
- Maintain consistent terminology across chunks
- Do NOT add commentary outside the translation

Please translate the following text:"""


def _book_new_conversation_prompt(source_lang: str, target_lang: str, title: str) -> str:
    title_line = f'The document is: "{title}"\n' if title else ""
    return f"""You are a professional translator specializing in {source_lang} to {target_lang} translation.

{title_line}I will continue sending text for translation. Maintain consistent terminology.

Please translate the following:"""


# ------------------------------------------------------------------
# Transcript mode prompts
# ------------------------------------------------------------------

def _transcript_system_prompt(source_lang: str, target_lang: str, title: str) -> str:
    title_line = f'The video/transcript title is: "{title}"\n' if title else ""
    return f"""You are a professional bilingual translator specializing in {source_lang} to {target_lang} translation of video transcripts and subtitles.

{title_line}I will send you transcript text in chunks. The text is in SRT subtitle format or plain transcript format with line numbers and timestamps.

**Your task**: Translate each line while maintaining the exact format:

line_number
timestamp --> timestamp
{source_lang} text ({target_lang} translation)

**Translation Guidelines:**
- Keep the EXACT format: line number, timestamps, then text with translation in parentheses
- Translate EVERY line — do not skip any content
- Keep timestamps exactly as they appear
- Preserve line numbers exactly
- Keep domain-specific terms in their original form when there is no direct equivalent
- Do NOT add empty lines between subtitle entries that weren't in the original
- Do NOT add commentary outside the translation

Please translate the following transcript text:"""


def _transcript_new_conversation_prompt(
    source_lang: str, target_lang: str, title: str, last_line: int,
) -> str:
    title_line = f'The video is: "{title}"\n' if title else ""
    line_context = f"We previously translated up to line {last_line}. " if last_line > 0 else ""
    return f"""You are a professional bilingual translator specializing in {source_lang} to {target_lang} translation of video transcripts.

{title_line}{line_context}I will continue sending transcript text for bilingual translation.

Translate each line in this format:
line_number
timestamp --> timestamp
{source_lang} text ({target_lang} translation)

**Guidelines:**
- Keep exact format with line numbers and timestamps
- Translate every line, preserve domain terms

Please translate the following:"""
