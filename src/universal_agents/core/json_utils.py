"""Shared JSON extraction utilities used by all data agents."""

import json
import re


def extract_json(response: str) -> dict | list | None:
    """Extract JSON from a response (searches code blocks first, then raw JSON).

    Strategy order:
      1. ```json ... ``` fenced code blocks
      2. ``` ... ``` generic code blocks
      3. Raw JSON object {...}
      4. Raw JSON array [...]

    Returns:
        Parsed dict/list, or None if no valid JSON found.
    """
    # Strategy 1 + 2: Markdown code blocks
    for pattern in (r"```json\s*([\s\S]*?)\s*```", r"```\s*([\s\S]*?)\s*```"):
        matches = re.findall(pattern, response, re.MULTILINE)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # Strategy 3 + 4: Raw JSON object or array
    for pat in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        m = re.search(pat, response)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass

    return None
