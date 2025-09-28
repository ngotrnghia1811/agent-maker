"""Unified output saving: JSON, TXT, MD formats."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .types import ConversationTurn, TurnResult


def save_turn(
    turn_result: TurnResult,
    output_dir: Path,
    conversation_name: str,
    provider: str,
) -> dict[str, str]:
    """Save a single turn's output in JSON, TXT, and MD formats."""
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"turn_{turn_result.turn_number:02d}_{conversation_name}_{provider}"
    saved: dict[str, str] = {}

    # JSON
    json_path = output_dir / f"{prefix}_response.json"
    json_path.write_text(json.dumps(turn_result.to_dict(), indent=2, default=str))
    saved["json"] = str(json_path)

    # Plain text
    txt_path = output_dir / f"{prefix}_response.txt"
    txt_path.write_text(turn_result.response)
    saved["txt"] = str(txt_path)

    # Markdown
    md_path = output_dir / f"{prefix}_response.md"
    md_content = turn_result.response
    if turn_result.thinking:
        md_content = f"<details>\n<summary>Thinking</summary>\n\n{turn_result.thinking}\n\n</details>\n\n{md_content}"
    md_path.write_text(md_content)
    saved["md"] = str(md_path)

    return saved


def save_summary(
    turns: list[ConversationTurn],
    output_dir: Path,
    conversation_name: str,
    provider: str,
    session_id: str,
) -> dict[str, str]:
    """Save a results summary for a conversation."""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}

    summary: dict[str, Any] = {
        "session_id": session_id,
        "provider": provider,
        "conversation_name": conversation_name,
        "timestamp": datetime.now().isoformat(),
        "total_turns": len(turns),
        "successful_turns": sum(1 for t in turns if t.success),
        "failed_turns": sum(1 for t in turns if not t.success),
        "total_processing_time_ms": sum(t.processing_time_ms for t in turns),
        "turns": [
            {
                "turn_number": t.turn_number,
                "success": t.success,
                "processing_time_ms": t.processing_time_ms,
                "error": t.error,
                "has_thinking": t.thinking is not None,
            }
            for t in turns
        ],
    }

    json_path = output_dir / f"{conversation_name}_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, default=str))
    saved["json"] = str(json_path)

    txt_path = output_dir / f"{conversation_name}_summary.txt"
    lines = [
        f"Session: {session_id}",
        f"Provider: {provider}",
        f"Turns: {summary['total_turns']} ({summary['successful_turns']} ok, {summary['failed_turns']} failed)",
        f"Total time: {summary['total_processing_time_ms']:.0f}ms",
    ]
    txt_path.write_text("\n".join(lines))
    saved["txt"] = str(txt_path)

    return saved


def save_full_results(
    turns: list[ConversationTurn],
    output_dir: Path,
    conversation_name: str,
    provider: str,
    session_id: str,
) -> str:
    """Save complete conversation history as a single JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)

    full: dict[str, Any] = {
        "session_id": session_id,
        "provider": provider,
        "conversation_name": conversation_name,
        "timestamp": datetime.now().isoformat(),
        "turns": [
            {
                "turn_number": t.turn_number,
                "user_message": t.user_message.content,
                "user_timestamp": t.user_message.timestamp.isoformat(),
                "assistant_message": t.assistant_message.content,
                "assistant_timestamp": t.assistant_message.timestamp.isoformat(),
                "thinking": t.thinking,
                "thinking_source": t.thinking_source,
                "processing_time_ms": t.processing_time_ms,
                "success": t.success,
                "error": t.error,
                "raw_api_responses": t.raw_api_responses,
            }
            for t in turns
        ],
    }

    path = output_dir / f"{conversation_name}_full_results.json"
    path.write_text(json.dumps(full, indent=2, default=str))
    return str(path)
