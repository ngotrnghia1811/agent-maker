#!/usr/bin/env python3
"""One-off script to check translated SRT quality."""
import re
import sys
import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from universal_agents.core.srt_utils import parse_srt_blocks


def check_file(path: str):
    with open(path, "r") as f:
        text = f.read()
    blocks = parse_srt_blocks(text)
    name = Path(path).name
    print(f"\n=== {name} ===")
    print(f"Blocks: {len(blocks)}")
    if not blocks:
        print("  NO BLOCKS FOUND")
        return

    print(f"Time range: {blocks[0].start_time} - {blocks[-1].end_time}")

    # Check for stray trailing digits in block text
    stray_digits = []
    for b in blocks:
        lines = b.text.strip().split("\n")
        last = lines[-1].strip()
        if re.match(r"^\d{1,2}$", last) and len(lines) > 1:
            stray_digits.append((b.index, last))

    if stray_digits:
        print(f"ISSUE: {len(stray_digits)} blocks with stray trailing digits:")
        for idx, digit in stray_digits[:5]:
            print(f"  Block {idx}: trailing '{digit}'")
    else:
        print("OK: No stray trailing digits")

    # Check sequential numbering
    bad_nums = [(b.index, i + 1) for i, b in enumerate(blocks) if b.index != i + 1]
    if bad_nums:
        print(f"ISSUE: {len(bad_nums)} blocks with wrong numbers")
        for actual, expected in bad_nums[:5]:
            print(f"  Got {actual}, expected {expected}")
    else:
        print("OK: Sequential numbering")

    # Check for timestamp gaps > 60s
    def to_sec(t):
        parts = t.replace(",", ".").split(":")
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

    prev_end = "00:00:00,000"
    gaps = []
    for b in blocks:
        gap = to_sec(b.start_time) - to_sec(prev_end)
        if gap > 60:
            gaps.append((b.index, prev_end, b.start_time, gap))
        prev_end = b.end_time

    if gaps:
        print(f"ISSUE: {len(gaps)} timestamp gaps > 60s:")
        for idx, pe, st, g in gaps:
            print(f"  Block {idx}: {pe} -> {st} ({g:.0f}s gap)")
    else:
        print("OK: No large timestamp gaps")

    # Check for empty text blocks
    empty = [b.index for b in blocks if not b.text.strip()]
    if empty:
        print(f"ISSUE: {len(empty)} empty text blocks: {empty[:10]}")
    else:
        print("OK: No empty blocks")


base = Path(__file__).resolve().parent.parent / "compiled_agents" / "claude_kendo_srt_translator"

# Check translated files
for p in sorted(glob.glob(str(base / "translated" / "*.en.srt"))):
    check_file(p)

# Compare block counts with originals
print("\n=== Completeness Check ===")
for p in sorted(glob.glob(str(base / "srt_files" / "*.ja-orig.srt"))):
    with open(p, "r") as f:
        orig_blocks = parse_srt_blocks(f.read())
    stem = Path(p).stem.replace(".ja-orig", "")
    translated = base / "translated" / f"{stem}.en.srt"
    if translated.exists():
        with open(translated, "r") as f:
            trans_blocks = parse_srt_blocks(f.read())
        missing = len(orig_blocks) - len(trans_blocks)
        status = "COMPLETE" if missing <= 0 else f"MISSING {missing} blocks"
        print(f"{stem}: orig={len(orig_blocks)}, translated={len(trans_blocks)} -> {status}")
    else:
        print(f"{stem}: NOT TRANSLATED")
