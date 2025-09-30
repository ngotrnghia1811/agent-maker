"""User requirements dataclass — collected from the interview phase."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UserRequirements:
    """Structured output of the compiler interview.

    Every field maps directly to one or more interview questions.
    See docs/agent_compiler_plan.md §5 for the question→field mapping.
    """

    # Phase 1: Use Case
    use_case: str = "chat"  # "chat", "data", "translation", "research", "code"
    needs_file_upload: bool = False

    # Phase 2: Quality & Intelligence
    needs_thinking: bool = False
    needs_json_output: bool = False
    needs_streaming: bool = False

    # Phase 3: Provider & Cost
    cost_sensitivity: str = "free"  # "free", "low", "medium", "unlimited"
    latency_sensitivity: str = "balanced"  # "speed", "balanced", "quality"
    provider_preference: str | None = None
    model_preference: str | None = None
    auth_available: dict[str, bool] = field(default_factory=dict)

    # Phase 4: Resilience
    needs_fallback: bool = False
    needs_monitoring: bool = False

    # Phase 5: Customization
    needs_translation: bool = False
    needs_citations: bool = False
    custom_system_prompt: str | None = None
    output_format: str = "script"  # "instance", "script", "config_only", "package"
    package_dir: str | None = None  # Output directory for "package" format
    package_name: str | None = None  # Name for the package directory

    # Compiler-LLM (Phase 0)
    compiler_llm_provider: str = "openrouter"
    compiler_llm_model: str | None = None

    def apply_use_case_defaults(self) -> None:
        """Auto-set capability flags based on use case selection."""
        if self.use_case == "data":
            self.needs_json_output = True
        elif self.use_case == "translation":
            self.needs_file_upload = True
            self.needs_json_output = True
            self.needs_translation = True
        elif self.use_case == "research":
            self.needs_citations = True
        elif self.use_case == "code":
            self.needs_thinking = True
