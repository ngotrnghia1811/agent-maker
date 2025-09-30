"""Config builder — constructs provider-specific config dicts from resolved components."""

from __future__ import annotations

from typing import Any

from .capability_resolver import ResolvedComponents
from .requirements import UserRequirements


# Default models per (provider, use_case)
_DEFAULT_MODELS: dict[tuple[str, str], str] = {
    ("openai", "chat"): "gpt-4.1-mini",
    ("openai", "code"): "o4-mini",
    ("openai", "data"): "gpt-4.1-mini",
    ("openrouter", "chat"): "anthropic/claude-sonnet-4",
    ("openrouter", "code"): "anthropic/claude-sonnet-4",
    ("openrouter", "data"): "anthropic/claude-sonnet-4",
}


class ConfigBuilder:
    """Build a config dict from resolved components + user requirements."""

    def build(
        self,
        components: ResolvedComponents,
        req: UserRequirements,
    ) -> dict[str, Any]:
        """Return a kwargs dict suitable for ``ConfigClass(**kwargs)``."""
        cfg: dict[str, Any] = {}

        # Model selection
        model = req.model_preference or _DEFAULT_MODELS.get(
            (components.provider, req.use_case)
        )
        if model:
            cfg["model"] = model

        # System prompt — applies to all transports
        if req.custom_system_prompt:
            cfg["system_prompt"] = req.custom_system_prompt

        # Transport-specific settings
        if components.transport == "browser":
            self._apply_browser(cfg, components, req)
        elif components.transport == "api":
            self._apply_api(cfg, components, req)
        elif components.transport == "cli":
            self._apply_cli(cfg, components, req)

        return cfg

    # ------------------------------------------------------------------
    # Transport-specific helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_browser(
        cfg: dict[str, Any],
        components: ResolvedComponents,
        req: UserRequirements,
    ) -> None:
        # Thinking support (Claude / Gemini)
        if components.provider in ("claude", "gemini"):
            cfg["extract_thinking"] = req.needs_thinking
            # Claude extended thinking requires temperature=1.0
            if req.needs_thinking and components.provider == "claude":
                cfg["temperature"] = 1.0

        # Translation settings
        if req.needs_translation and "translation" in components.agent_class_name.lower():
            if req.use_case == "translation":
                cfg["timeout"] = 600

        # Gemini model selection
        if components.provider == "gemini" and req.needs_thinking:
            cfg["required_model"] = "thinking"

    @staticmethod
    def _apply_api(
        cfg: dict[str, Any],
        components: ResolvedComponents,
        req: UserRequirements,
    ) -> None:
        cfg["stream"] = req.needs_streaming

        # OpenAI-specific
        if components.provider == "openai":
            if req.needs_thinking:
                cfg["reasoning_effort"] = "medium"
            if req.needs_json_output:
                cfg["response_format"] = {"type": "json_object"}

        # OpenRouter-specific
        if components.provider == "openrouter":
            if req.needs_thinking:
                cfg["enable_thinking"] = True
                cfg["thinking_budget"] = 10000
                # Claude thinking models require temperature=1.0
                model = cfg.get("model", "")
                if "claude" in model or "anthropic" in model:
                    cfg["temperature"] = 1.0

            if req.needs_fallback:
                cfg.setdefault(
                    "fallback_models",
                    _get_fallback_models(req),
                )

        # Longer timeout for data / code
        if req.use_case in ("data", "code", "translation"):
            cfg["timeout"] = 600
            cfg["max_tokens"] = 16384

    @staticmethod
    def _apply_cli(
        cfg: dict[str, Any],
        components: ResolvedComponents,
        req: UserRequirements,
    ) -> None:
        pass  # CLI has minimal configuration; bare defaults suffice


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_FREE_FALLBACKS = [
    "deepseek/deepseek-chat-v3.1:free",
    "google/gemma-2-9b-it:free",
]

_PAID_FALLBACKS = [
    "anthropic/claude-sonnet-4",
    "openai/gpt-4.1",
    "google/gemini-2.5-flash",
]


def _get_fallback_models(req: UserRequirements) -> list[str]:
    """Select fallback models based on cost sensitivity."""
    if req.cost_sensitivity in ("free", "low"):
        return list(_FREE_FALLBACKS)
    return list(_PAID_FALLBACKS)
