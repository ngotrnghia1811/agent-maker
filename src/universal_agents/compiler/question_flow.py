"""Question flow — interactive interview that collects UserRequirements."""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, TextIO

from .auth_detector import AuthDetector, AuthStatus
from .compiler_llm import CompilerLLM
from .requirements import UserRequirements

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Question definitions
# ------------------------------------------------------------------

@dataclass
class Question:
    """A single interview question."""

    id: str  # e.g. "1.1"
    text: str
    options: list[str]  # display strings for numbered options
    field_name: str  # UserRequirements field to set
    value_map: dict[int, Any] | None = None  # option index → value (1-based)
    skip_if: Callable[[UserRequirements], bool] | None = None


def _build_questions() -> list[Question]:
    """Build the full list of interview questions per plan §5."""
    return [
        # Phase 0: Compiler-LLM
        Question(
            id="0.1",
            text="Compiler-LLM is set to: stepfun/step-3.5-flash:free (OpenRouter)",
            options=[
                "Keep current (recommended — free & fast)",
                "Use OpenAI (gpt-4.1-mini)",
                "Use a different OpenRouter model",
                "Custom (specify provider and model)",
            ],
            field_name="compiler_llm_provider",
            value_map={
                1: ("openrouter", None),
                2: ("openai", "gpt-4.1-mini"),
                3: ("openrouter", "__ask__"),
                4: ("__custom__", None),
            },
        ),
        # Phase 1: Use Case
        Question(
            id="1.1",
            text="What will you use this agent for?",
            options=[
                "General chat / conversation",
                "Structured data extraction (JSON output)",
                "Document translation",
                "Research with citations",
                "Code assistance / review",
                "Custom (describe your use case)",
            ],
            field_name="use_case",
            value_map={1: "chat", 2: "data", 3: "translation", 4: "research", 5: "code", 6: "__custom__"},
        ),
        Question(
            id="1.2",
            text="Does the agent need to process files (PDF, images)?",
            options=[
                "Yes — PDF and/or image upload required",
                "No — text-only input",
            ],
            field_name="needs_file_upload",
            value_map={1: True, 2: False},
            skip_if=lambda r: r.use_case in ("chat", "code") or r.needs_file_upload,
        ),
        # Phase 2: Quality & Intelligence
        Question(
            id="2.1",
            text="Should the agent show its reasoning/thinking process?",
            options=[
                "Yes — I want to see chain-of-thought",
                "No — just the final answer",
                "Don't care — let the compiler decide",
            ],
            field_name="needs_thinking",
            value_map={1: True, 2: False, 3: None},
            skip_if=lambda r: r.needs_thinking,  # already set by use_case defaults
        ),
        Question(
            id="2.2",
            text="Response speed vs. quality preference?",
            options=[
                "Speed — fast responses, lower cost",
                "Balanced — good quality at reasonable speed",
                "Quality — best output, cost/speed secondary",
            ],
            field_name="latency_sensitivity",
            value_map={1: "speed", 2: "balanced", 3: "quality"},
        ),
        Question(
            id="2.3",
            text="Do you need real-time streaming responses?",
            options=[
                "Yes — stream tokens as they arrive",
                "No — wait for complete response",
            ],
            field_name="needs_streaming",
            value_map={1: True, 2: False},
            skip_if=lambda r: r.provider_preference in ("claude", "gemini", "gpt", "perplexity"),
        ),
        # Phase 3: Provider & Cost
        Question(
            id="3.1",
            text="Budget preference?",
            options=[
                "Free — free-tier models only ($0)",
                "Low — minimize cost (< $0.01/request)",
                "Medium — reasonable cost for good quality",
                "Unlimited — best available, cost doesn't matter",
            ],
            field_name="cost_sensitivity",
            value_map={1: "free", 2: "low", 3: "medium", 4: "unlimited"},
        ),
        Question(
            id="3.2",
            text="Preferred provider?",
            options=[
                "Claude (browser — free with login)",
                "Gemini (browser — free with login)",
                "OpenAI (API — requires OPENAI_API_KEY)",
                "OpenRouter (API — many models, free tier available)",
                "GPT (browser — free with login)",
                "Perplexity (browser — citations, free with login)",
                "Copilot (CLI — free with GitHub auth)",
                "No preference — let the compiler decide",
            ],
            field_name="provider_preference",
            value_map={
                1: "claude", 2: "gemini", 3: "openai", 4: "openrouter",
                5: "gpt", 6: "perplexity", 7: "copilot", 8: None,
            },
        ),
        # 3.3 is handled specially (auth display)
        Question(
            id="3.4",
            text="Preferred model?",
            options=[
                "Use provider default",
                "Custom (specify model name)",
            ],
            field_name="model_preference",
            value_map={1: None, 2: "__custom__"},
            skip_if=lambda r: r.model_preference is not None,
        ),
        # Phase 4: Resilience
        Question(
            id="4.1",
            text="Auto-retry with backup models on failure?",
            options=[
                "Yes — automatically try fallback models",
                "No — fail immediately on error",
            ],
            field_name="needs_fallback",
            value_map={1: True, 2: False},
            skip_if=lambda r: r.provider_preference in ("claude", "gemini", "gpt", "perplexity"),
        ),
        Question(
            id="4.2",
            text="Enable monitoring dashboard?",
            options=[
                "Yes — wrap agent with MonitoredAgent + Reporter",
                "No — lightweight, no monitoring overhead",
            ],
            field_name="needs_monitoring",
            value_map={1: True, 2: False},
        ),
        # Phase 5: Customization
        Question(
            id="5.1",
            text="System prompt?",
            options=[
                "Default — use provider's built-in system prompt",
                'Minimal — "You are a helpful assistant."',
                'Data-focused — "Extract structured data. Respond only with valid JSON."',
                'Code-focused — "You are an expert programmer. Think step-by-step."',
                "Custom (write your own system prompt)",
            ],
            field_name="custom_system_prompt",
            value_map={
                1: None,
                2: "You are a helpful assistant.",
                3: "Extract structured data. Respond only with valid JSON.",
                4: "You are an expert programmer. Think step-by-step.",
                5: "__custom__",
            },
        ),
        Question(
            id="5.2",
            text="Output format?",
            options=[
                "Instance — ready-to-use Python object (await agent.chat(...))",
                "Script — standalone .py file you can run directly",
                "Config-only — JSON config dict for external tooling",
            ],
            field_name="output_format",
            value_map={1: "instance", 2: "script", 3: "config_only"},
        ),
    ]


# ------------------------------------------------------------------
# Presets
# ------------------------------------------------------------------

PRESETS: dict[str, dict[str, Any]] = {
    "free-chat": dict(
        use_case="chat",
        cost_sensitivity="free",
        output_format="script",
    ),
    "openai-data": dict(
        use_case="data",
        needs_json_output=True,
        needs_thinking=True,
        provider_preference="openai",
        output_format="script",
    ),
    "openrouter-free": dict(
        use_case="chat",
        cost_sensitivity="free",
        provider_preference="openrouter",
        output_format="script",
    ),
    "claude-translate": dict(
        use_case="translation",
        needs_file_upload=True,
        needs_translation=True,
        provider_preference="claude",
        output_format="script",
    ),
    "research": dict(
        use_case="research",
        needs_citations=True,
        provider_preference="perplexity",
        output_format="script",
    ),
    "code-review": dict(
        use_case="code",
        needs_thinking=True,
        provider_preference="openai",
        output_format="script",
    ),
}


# ------------------------------------------------------------------
# QuestionFlow
# ------------------------------------------------------------------

class QuestionFlow:
    """Interactive interview that builds a UserRequirements from user answers."""

    def __init__(
        self,
        auth_detector: AuthDetector | None = None,
        compiler_llm: CompilerLLM | None = None,
        input_fn: Callable[[str], str] | None = None,
        output: TextIO | None = None,
    ) -> None:
        self._auth_detector = auth_detector or AuthDetector()
        self._compiler_llm = compiler_llm  # lazily created after Q0.1
        self._input_fn = input_fn or _default_input
        self._output = output or sys.stdout
        self._questions = _build_questions()

    def interview(self, preset: str | None = None) -> UserRequirements:
        """Run the full interview and return populated requirements."""
        req = UserRequirements()

        # Shortcut: preset
        if preset:
            return self._load_preset(preset)

        # Detect auth up front
        auth_status = self._auth_detector.detect()
        req.auth_available = auth_status.available

        for q in self._questions:
            # Skip logic
            if q.skip_if and q.skip_if(req):
                continue

            # Special: auth display (between 3.2 and 3.4)
            if q.id == "3.4":
                self._display_auth(auth_status)
                confirmed = self._ask_choice(
                    "Authentication detected (see above):",
                    ["Looks correct — proceed", "I have additional auth not detected"],
                )
                if confirmed == 2:
                    self._print("(Note: please update .env or storage/ files and re-run)")

            value = self._ask_question(q, req)
            if value is not None:
                self._apply_value(req, q, value)

            # After use-case question, apply defaults
            if q.id == "1.1":
                req.apply_use_case_defaults()

        return req

    def _load_preset(self, name: str) -> UserRequirements:
        """Load a preset into UserRequirements."""
        if name not in PRESETS:
            available = ", ".join(sorted(PRESETS))
            raise ValueError(f"Unknown preset '{name}'. Available: {available}")
        req = UserRequirements(**PRESETS[name])
        req.apply_use_case_defaults()
        # Detect auth
        auth_status = self._auth_detector.detect()
        req.auth_available = auth_status.available
        return req

    def _ask_question(self, q: Question, req: UserRequirements) -> Any:
        """Present a question, get user input, return the mapped value."""
        choice = self._ask_choice(q.text, q.options)

        if q.value_map is None:
            return choice

        mapped = q.value_map.get(choice)

        # Handle compiler-LLM setup (special tuple values)
        if q.id == "0.1" and isinstance(mapped, tuple):
            provider, model = mapped
            if provider == "__custom__":
                provider = self._ask_text("Enter provider (openrouter/openai):")
                model = self._ask_text("Enter model name:")
            elif model == "__ask__":
                model = self._ask_text("Enter OpenRouter model name:")
            req.compiler_llm_provider = provider
            req.compiler_llm_model = model
            # Initialize Compiler-LLM with selected provider/model
            self._compiler_llm = CompilerLLM(provider=provider, model=model)
            return None  # already applied

        # Handle __custom__ sentinel — use Compiler-LLM if available
        if mapped == "__custom__":
            user_text = self._ask_text(f"Describe what you need for {q.field_name}:")
            # For system prompts, use the refine path
            if q.field_name == "custom_system_prompt" and self._compiler_llm:
                return self._llm_refine_prompt(user_text)
            # For other fields, use the interpret path
            if self._compiler_llm:
                return self._llm_interpret(q, user_text)
            return user_text

        return mapped

    def _apply_value(self, req: UserRequirements, q: Question, value: Any) -> None:
        """Set the value on the requirements object."""
        setattr(req, q.field_name, value)

    def _display_auth(self, status: AuthStatus) -> None:
        """Print detected auth status."""
        self._print("\n  Authentication detected:")
        for line in status.summary_lines():
            self._print(f"  {line}")
        self._print("")

    def _ask_choice(self, prompt: str, options: list[str]) -> int:
        """Display numbered options, return 1-based choice."""
        self._print(f"\n  {prompt}\n")
        for i, opt in enumerate(options, 1):
            self._print(f"     {i}. {opt}")
        self._print("")

        while True:
            raw = self._input_fn("  Your choice: ").strip()
            if raw.isdigit():
                n = int(raw)
                if 1 <= n <= len(options):
                    return n
            self._print(f"  Please enter a number between 1 and {len(options)}.")

    def _ask_text(self, prompt: str) -> str:
        """Ask for free-form text input."""
        self._print("")
        while True:
            raw = self._input_fn(f"  {prompt} ").strip()
            if raw:
                return raw
            self._print("  Please enter a non-empty value.")

    def _llm_interpret(self, q: Question, user_text: str) -> Any:
        """Use Compiler-LLM to interpret free-text into a valid field value."""
        valid_values = list(q.value_map.values()) if q.value_map else []
        # Filter out sentinels and tuples
        valid_values = [v for v in valid_values if v != "__custom__" and not isinstance(v, tuple)]
        try:
            result = asyncio.run(
                self._compiler_llm.interpret_custom(
                    question_text=q.text,
                    field_name=q.field_name,
                    user_text=user_text,
                    valid_values=valid_values,
                )
            )
            logger.debug("Compiler-LLM interpreted %r → %r", user_text, result)
            return result
        except Exception:
            logger.warning("Compiler-LLM failed, using raw text", exc_info=True)
            return user_text

    def _llm_refine_prompt(self, user_draft: str) -> str:
        """Use Compiler-LLM to refine a user-drafted system prompt."""
        try:
            result = asyncio.run(
                self._compiler_llm.refine_system_prompt(user_draft)
            )
            logger.debug("Compiler-LLM refined prompt (%d→%d chars)", len(user_draft), len(result))
            return result
        except Exception:
            logger.warning("Compiler-LLM refine failed, using raw draft", exc_info=True)
            return user_draft

    def _print(self, msg: str) -> None:
        self._output.write(msg + "\n")


def _default_input(prompt: str) -> str:
    """Default input function — reads from stdin."""
    return input(prompt)
