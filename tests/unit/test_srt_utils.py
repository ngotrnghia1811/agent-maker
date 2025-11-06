"""Tests for core/srt_utils.py — SRT parsing, detection, and chunking."""

import pytest

from universal_agents.core.srt_utils import (
    SrtBlock,
    add_overlap,
    chunk_plain_text,
    chunk_srt_text,
    detect_srt_format,
    get_srt_line_range,
    normalize_srt_text,
    parse_srt_blocks,
)

# -------------------------------------------------------------------
# Sample SRT content
# -------------------------------------------------------------------

SAMPLE_SRT = """\
1
00:00:01,000 --> 00:00:04,000
こんにちは、皆さん。

2
00:00:04,500 --> 00:00:08,200
今日は剣道の基本について話しましょう。

3
00:00:09,000 --> 00:00:13,500
まず、構えについてです。

4
00:00:14,000 --> 00:00:18,000
中段の構えが最も基本的です。

5
00:00:18,500 --> 00:00:22,000
次に、素振りの練習をしましょう。
"""

SAMPLE_PLAIN = """\
This is the first paragraph of the document.
It has multiple lines.

This is the second paragraph.

This is the third paragraph with more content that goes on quite a bit.
"""


class TestDetectSrtFormat:
    def test_valid_srt(self):
        assert detect_srt_format(SAMPLE_SRT) is True

    def test_plain_text(self):
        assert detect_srt_format(SAMPLE_PLAIN) is False

    def test_empty_text(self):
        assert detect_srt_format("") is False

    def test_srt_with_dot_separator(self):
        text = "1\n00:00:01.000 --> 00:00:04.000\nHello"
        assert detect_srt_format(text) is True

    def test_partial_timestamp(self):
        text = "1\n00:00:01 some random text"
        assert detect_srt_format(text) is False

    def test_srt_deep_in_text(self):
        # Only checks first 1000 chars
        text = "x" * 1001 + "\n1\n00:00:01,000 --> 00:00:04,000\nHello"
        assert detect_srt_format(text) is False


class TestParseSrtBlocks:
    def test_parse_sample(self):
        blocks = parse_srt_blocks(SAMPLE_SRT)
        assert len(blocks) == 5
        assert blocks[0].index == 1
        assert blocks[0].start_time == "00:00:01,000"
        assert blocks[0].end_time == "00:00:04,000"
        assert "こんにちは" in blocks[0].text

    def test_parse_empty(self):
        assert parse_srt_blocks("") == []

    def test_parse_single_block(self):
        text = "1\n00:00:01,000 --> 00:00:04,000\nHello world"
        blocks = parse_srt_blocks(text)
        assert len(blocks) == 1
        assert blocks[0].text == "Hello world"

    def test_block_raw_reconstruction(self):
        blocks = parse_srt_blocks(SAMPLE_SRT)
        raw = blocks[0].raw
        assert "1\n00:00:01,000 --> 00:00:04,000" in raw
        assert "こんにちは" in raw


class TestChunkSrtText:
    def test_single_chunk_when_small(self):
        chunks = chunk_srt_text(SAMPLE_SRT, blocks_per_chunk=10)
        assert len(chunks) == 1

    def test_multiple_chunks(self):
        chunks = chunk_srt_text(SAMPLE_SRT, blocks_per_chunk=2)
        assert len(chunks) == 3  # 5 blocks / 2 per chunk = 3

    def test_one_block_per_chunk(self):
        chunks = chunk_srt_text(SAMPLE_SRT, blocks_per_chunk=1)
        assert len(chunks) == 5

    def test_max_chars_limit(self):
        chunks = chunk_srt_text(SAMPLE_SRT, blocks_per_chunk=50, max_chars=100)
        assert len(chunks) > 1

    def test_empty_text(self):
        assert chunk_srt_text("") == []
        assert chunk_srt_text("   ") == []

    def test_preserves_content(self):
        chunks = chunk_srt_text(SAMPLE_SRT, blocks_per_chunk=2)
        combined = "\n\n".join(chunks)
        assert "こんにちは" in combined
        assert "素振り" in combined


class TestChunkPlainText:
    def test_single_chunk_small(self):
        chunks = chunk_plain_text(SAMPLE_PLAIN, chunk_size=10000)
        assert len(chunks) == 1

    def test_multiple_chunks(self):
        chunks = chunk_plain_text(SAMPLE_PLAIN, chunk_size=50)
        assert len(chunks) >= 2

    def test_empty_text(self):
        assert chunk_plain_text("") == []

    def test_preserves_content(self):
        chunks = chunk_plain_text(SAMPLE_PLAIN, chunk_size=80)
        combined = "\n\n".join(chunks)
        assert "first paragraph" in combined
        assert "third paragraph" in combined


class TestAddOverlap:
    def test_no_overlap(self):
        chunks = ["chunk1", "chunk2"]
        result = add_overlap(chunks, overlap_chars=0)
        assert result == chunks

    def test_single_chunk(self):
        result = add_overlap(["only one"], overlap_chars=10)
        assert result == ["only one"]

    def test_adds_overlap(self):
        chunks = ["First chunk with content", "Second chunk with content"]
        result = add_overlap(chunks, overlap_chars=10)
        assert len(result) == 2
        assert result[0] == chunks[0]  # First unchanged
        assert "[...continuation...]" in result[1]

    def test_overlap_contains_previous_text(self):
        chunks = ["AAAA\nBBBB\nCCCC", "DDDD\nEEEE"]
        result = add_overlap(chunks, overlap_chars=5)
        assert "CCCC" in result[1]

    def test_empty_list(self):
        assert add_overlap([], overlap_chars=10) == []


class TestGetSrtLineRange:
    def test_sample_chunk(self):
        chunk = "1\n00:00:01,000 --> 00:00:04,000\nHello\n\n2\n00:00:05,000 --> 00:00:08,000\nWorld"
        first, last = get_srt_line_range(chunk)
        assert first == 1
        assert last == 2

    def test_single_block(self):
        chunk = "42\n00:01:00,000 --> 00:01:05,000\nText"
        first, last = get_srt_line_range(chunk)
        assert first == 42
        assert last == 42

    def test_no_indices(self):
        assert get_srt_line_range("just plain text") == (0, 0)


class TestNormalizeSrtText:
    def test_already_formatted(self):
        """Properly formatted SRT should remain unchanged (modulo trailing newline)."""
        result = normalize_srt_text(SAMPLE_SRT)
        blocks = parse_srt_blocks(result)
        assert len(blocks) == 5
        assert "\n\n" in result

    def test_missing_blank_lines(self):
        """SRT blocks glued together should get blank line separators."""
        messy = (
            "1\n00:00:01,000 --> 00:00:04,000\nHello world\n"
            "2\n00:00:05,000 --> 00:00:08,000\nSecond line\n"
            "3\n00:00:09,000 --> 00:00:12,000\nThird line"
        )
        result = normalize_srt_text(messy)
        blocks = parse_srt_blocks(result)
        assert len(blocks) == 3
        # Verify blank lines between blocks
        lines = result.split("\n")
        blank_count = sum(1 for l in lines if l.strip() == "")
        assert blank_count >= 2

    def test_inline_block_numbers(self):
        """Block number glued to previous text: 'sake.)2' -> separated."""
        messy = (
            "1\n00:00:01,000 --> 00:00:04,000\n"
            "(Practicing Kendo is not just for your own sake.)2\n"
            "00:00:05,000 --> 00:00:08,000\nSecond block"
        )
        result = normalize_srt_text(messy)
        blocks = parse_srt_blocks(result)
        assert len(blocks) == 2

    def test_stray_plus_markers(self):
        """Remove +N markers that Gemini sometimes inserts."""
        messy = (
            "1\n00:00:01,000 --> 00:00:04,000\n"
            "First block text)+3\n"
            "2\n00:00:05,000 --> 00:00:08,000\nSecond"
        )
        result = normalize_srt_text(messy)
        assert "+3" not in result
        blocks = parse_srt_blocks(result)
        assert len(blocks) >= 1

    def test_non_srt_text_returned_as_is(self):
        """Non-SRT text should be returned unchanged."""
        plain = "Just some plain text without SRT formatting"
        assert normalize_srt_text(plain) == plain

    def test_real_world_gemini_output(self):
        """Simulate actual Gemini output with multiple issues."""
        messy = (
            "1\n00:00:04,680 --> 00:00:08,599\n"
            "検動するってことは\n(Practicing Kendo.)2\n"
            "00:00:08,599 --> 00:00:10,639\n"
            "人のためにどんだけ\n(For others.)+39\n"
            "00:00:43,879 --> 00:00:48,480\n"
            "それは相手が読んでる\n(Reading your opponent.)"
        )
        result = normalize_srt_text(messy)
        blocks = parse_srt_blocks(result)
        assert len(blocks) >= 2
        assert "+3" not in result

    def test_split_block_numbers_two_digit(self):
        """Claude splits '10' across lines: 'text)\\n1\\n\\n0\\n00:01:14'."""
        messy = (
            "9\n00:01:11,000 --> 00:01:14,000\n"
            "(re-examine my kendo.)\n"
            "1\n\n"
            "0\n00:01:14,720 --> 00:01:21,400\n"
            "(I had to start over.)\n"
            "1\n\n"
            "1\n00:01:21,400 --> 00:01:27,920\n"
            "(An extraordinary world.)"
        )
        result = normalize_srt_text(messy)
        blocks = parse_srt_blocks(result)
        assert len(blocks) == 3
        # Renumbered sequentially
        assert blocks[0].index == 1
        assert blocks[1].index == 2
        assert blocks[2].index == 3
        # Timestamps preserved
        assert blocks[1].start_time == "00:01:14,720"

    def test_split_block_numbers_larger(self):
        """Split numbers like '18' → '1\\n\\n8'."""
        messy = (
            "1\n\n"
            "7\n00:02:02,600 --> 00:02:09,599\n"
            "(My teacher said.)\n"
            "1\n\n"
            "8\n00:02:09,599 --> 00:02:11,760\n"
            "(Like an elementary student.)"
        )
        result = normalize_srt_text(messy)
        blocks = parse_srt_blocks(result)
        assert len(blocks) == 2
        assert blocks[0].index == 1
        assert blocks[1].index == 2

    def test_single_digit_cycling(self):
        """Claude outputs only last digit for blocks ≥10 (0,1,2 instead of 10,11,12)."""
        messy = (
            "9\n00:06:16,599 --> 00:06:19,240\nNine.\n\n"
            "0\n00:06:19,240 --> 00:06:28,000\nTen.\n\n"
            "1\n00:06:28,000 --> 00:06:36,240\nEleven."
        )
        result = normalize_srt_text(messy)
        blocks = parse_srt_blocks(result)
        assert len(blocks) == 3
        # Renumbered sequentially regardless of original numbers
        assert blocks[0].index == 1
        assert blocks[1].index == 2
        assert blocks[2].index == 3

    def test_renumber_sequential(self):
        """Blocks with wrong numbers are renumbered 1, 2, 3, ..."""
        messy = (
            "5\n00:00:01,000 --> 00:00:04,000\nFirst.\n\n"
            "99\n00:00:05,000 --> 00:00:08,000\nSecond.\n\n"
            "3\n00:00:09,000 --> 00:00:12,000\nThird."
        )
        result = normalize_srt_text(messy)
        blocks = parse_srt_blocks(result)
        assert len(blocks) == 3
        assert [b.index for b in blocks] == [1, 2, 3]
