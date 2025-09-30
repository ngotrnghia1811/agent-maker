"""Shared prompt building utilities used by all data agents."""

import json


def build_data_prompt(
    prompt: str,
    input_json: dict | list | None = None,
    final_remind: str = "",
) -> str:
    """Build a data generation prompt with optional JSON input block.

    Args:
        prompt: The main instruction text.
        input_json: Optional input data to embed as a JSON code block.
        final_remind: Optional reminder text appended at the end.

    Returns:
        Assembled prompt string.
    """
    parts = [prompt]
    if input_json is not None:
        parts.append(f"\n\nInput:\n```json\n{json.dumps(input_json, indent=2, ensure_ascii=False)}\n```")
    if final_remind:
        parts.append(f"\n\n{final_remind}")
    return "".join(parts)
