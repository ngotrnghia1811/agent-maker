"""SRT subtitle parsing, detection, and chunking utilities.

Provides:
- detect_srt_format(): Check if text is SRT format
- parse_srt_blocks(): Parse SRT text into structured blocks
- chunk_srt_text(): Split SRT text into chunks by subtitle blocks
- chunk_plain_text(): Split plain text into chunks at paragraph boundaries
"""

import re
from dataclasses import dataclass
from typing import Any

# Pattern: sequence number, then timestamp line
_SRT_BLOCK_RE = re.compile(
    r"^(\d+)\s*\n"
    r"(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3})\s*\n"
    r"((?:.+\n?)+)",
    re.MULTILINE,
)


@dataclass
class SrtBlock:
    """A single SRT subtitle entry."""

    index: int
    start_time: str
    end_time: str
    text: str

    @property
    def raw(self) -> str:
        """Reconstruct the original SRT block."""
        return f"{self.index}\n{self.start_time} --> {self.end_time}\n{self.text}"


def detect_srt_format(text: str) -> bool:
    """Detect if text is in SRT subtitle format.

    Checks the first 1000 characters for the pattern:
    <number>\\n<HH:MM:SS,mmm> --> <HH:MM:SS,mmm>
    """
    sample = text[:1000]
    pattern = r"\d+\s*\n\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[.,]\d{3}"
    return bool(re.search(pattern, sample))


def parse_srt_blocks(text: str) -> list[SrtBlock]:
    """Parse SRT text into a list of SrtBlock entries."""
    blocks: list[SrtBlock] = []
    # Split on blank lines to get raw blocks
    raw_blocks = re.split(r"\n\s*\n", text.strip())

    for raw in raw_blocks:
        raw = raw.strip()
        if not raw:
            continue
        m = _SRT_BLOCK_RE.match(raw)
        if m:
            blocks.append(
                SrtBlock(
                    index=int(m.group(1)),
                    start_time=m.group(2),
                    end_time=m.group(3),
                    text=m.group(4).strip(),
                )
            )
    return blocks


def chunk_srt_text(
    text: str,
    blocks_per_chunk: int = 50,
    max_chars: int = 0,
) -> list[str]:
    """Split SRT text into chunks, preserving subtitle block boundaries.

    Args:
        text: Full SRT text.
        blocks_per_chunk: Maximum subtitle entries per chunk.
        max_chars: If > 0, also split when accumulated chars exceed this.

    Returns:
        List of SRT text chunks.
    """
    raw_blocks = re.split(r"\n\s*\n", text.strip())
    raw_blocks = [b.strip() for b in raw_blocks if b.strip()]

    if not raw_blocks:
        return [text] if text.strip() else []

    chunks: list[str] = []
    current: list[str] = []
    current_chars = 0

    for block in raw_blocks:
        block_len = len(block)

        # Check if adding this block would exceed limits
        should_split = (
            len(current) >= blocks_per_chunk
            or (max_chars > 0 and current_chars + block_len > max_chars and current)
        )

        if should_split:
            chunks.append("\n\n".join(current))
            current = []
            current_chars = 0

        current.append(block)
        current_chars += block_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def normalize_srt_text(text: str) -> str:
    """Normalize messy SRT text into proper SRT format.

    Fixes common issues from LLM output:
    - Missing blank lines between blocks
    - Inline block numbers glued to the previous line's text
    - Stray +N markers between blocks
    - Split block numbers (e.g. Claude outputs "1\\n\\n0" instead of "10")
    - Wrong or missing block numbers (renumbered sequentially)
    - Inconsistent line endings

    Returns properly formatted SRT with blank lines between each block.
    """
    # Remove stray +N markers (e.g. "+3" or "+2" on their own or glued)
    text = re.sub(r"\)\+\d+\n", ")\n", text)
    text = re.sub(r"^\+\d+\s*$", "", text, flags=re.MULTILINE)

    # Fix split block numbers: Claude sometimes splits "10" across lines as
    # "text)\n1\n\n0\n00:01:14,720 -->".  Merge the digits back together.
    # Pattern: non-whitespace char, then \n, one or more leading digits,
    # then \n\n (blank line), then remaining digit(s), then \n timestamp.
    text = re.sub(
        r"(\S)\n(\d+)\n\n(\d+)\n(\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->)",
        r"\1\n\n\2\3\n\4",
        text,
    )

    # Insert a blank line before SRT block numbers that are glued to
    # the previous line (e.g. "sake.)2\n00:00:08" → "sake.)\n\n2\n00:00:08")
    text = re.sub(
        r"([^\n])(\d+)\n(\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->)",
        r"\1\n\n\2\n\3",
        text,
    )

    # Insert a blank line before block numbers that are on their own line
    # but not preceded by a blank line (e.g. "text\n2\n00:00:05" → "text\n\n2\n00:00:05")
    text = re.sub(
        r"(\S[^\n]*)\n(\d+)\n(\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->)",
        r"\1\n\n\2\n\3",
        text,
    )

    # Now parse and reconstruct with sequential renumbering
    blocks = parse_srt_blocks(text)
    if not blocks:
        return text  # Not parseable as SRT, return as-is

    parts = []
    for i, block in enumerate(blocks, start=1):
        block.index = i  # Renumber sequentially
        # Strip any trailing standalone-digit lines from block text.
        # Claude sometimes appends the leading digit(s) of the NEXT block
        # number to the current block's text (e.g. a lone "1" before block 10).
        block_lines = block.text.rstrip().split("\n")
        while block_lines and re.match(r"^\d+$", block_lines[-1].strip()):
            block_lines.pop()
        block.text = "\n".join(block_lines)
        parts.append(block.raw)
    return "\n\n".join(parts) + "\n"


def chunk_plain_text(text: str, chunk_size: int = 3000) -> list[str]:
    """Split plain text into chunks at paragraph boundaries.

    Args:
        text: Full text.
        chunk_size: Maximum characters per chunk.

    Returns:
        List of text chunks.
    """
    paragraphs = re.split(r"\n\s*\n", text.strip())

    if not paragraphs:
        return [text] if text.strip() else []

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_size = len(para)

        if current_size + para_size > chunk_size and current:
            chunks.append("\n\n".join(current))
            current = []
            current_size = 0

        current.append(para)
        current_size += para_size

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def add_overlap(chunks: list[str], overlap_chars: int) -> list[str]:
    """Add overlap from the end of each chunk to the start of the next.

    This provides context continuity for the translator.

    Args:
        chunks: List of text chunks.
        overlap_chars: Number of characters to overlap.

    Returns:
        New list of chunks with overlap prepended (except the first).
    """
    if overlap_chars <= 0 or len(chunks) <= 1:
        return list(chunks)

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        overlap = prev[-overlap_chars:] if len(prev) > overlap_chars else prev
        # Find a clean boundary (newline)
        nl = overlap.find("\n")
        if nl >= 0:
            overlap = overlap[nl + 1 :]
        result.append(f"[...continuation...]\n{overlap}\n\n{chunks[i]}")

    return result


def get_srt_line_range(chunk: str) -> tuple[int, int]:
    """Extract the first and last subtitle index numbers from an SRT chunk.

    Returns:
        (first_index, last_index) or (0, 0) if no indices found.
    """
    indices = re.findall(r"^(\d+)\s*$", chunk, re.MULTILINE)
    if not indices:
        return (0, 0)
    return (int(indices[0]), int(indices[-1]))
