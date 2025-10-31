"""Capability resolver — maps UserRequirements to concrete component selections."""

import logging
from dataclasses import dataclass

from .requirements import UserRequirements

logger = logging.getLogger(__name__)


class CompilerError(Exception):
    """Error during agent compilation."""


@dataclass
class ResolvedComponents:
    """Concrete component selections from the resolver."""

    provider: str  # "claude", "gemini", "gpt", "perplexity", "openai", "openrouter", "copilot"
    transport: str  # "browser", "api", "cli"
    agent_class_name: str  # e.g. "ClaudeChatAgent", "OpenAIDataAgent"
    config_class_name: str  # e.g. "ClaudeConfig", "OpenAIDataConfig"
    agent_module: str  # e.g. "universal_agents.providers.claude.chat"
    config_module: str  # e.g. "universal_agents.providers.claude.config"
    capabilities: list[str]  # e.g. ["chat", "thinking"]
    use_monitoring: bool = False


# Provider → transport mapping
_PROVIDER_TRANSPORT: dict[str, str] = {
    "claude": "browser",
    "gemini": "browser",
    "gpt": "browser",
    "perplexity": "browser",
    "openai": "api",
    "openrouter": "api",
    "copilot": "cli",
}

# (provider, use_case) → (agent_class, config_class, agent_module, config_module)
_AGENT_MAP: dict[tuple[str, str], tuple[str, str, str, str]] = {
    # Claude
    ("claude", "chat"): ("ClaudeChatAgent", "ClaudeConfig", "providers.claude.chat", "providers.claude.config"),
    ("claude", "code"): ("ClaudeChatAgent", "ClaudeConfig", "providers.claude.chat", "providers.claude.config"),
    ("claude", "data"): ("ClaudeDataAgent", "ClaudeDataConfig", "providers.claude.data", "providers.claude.config"),
    ("claude", "translation"): ("ClaudeTranslatorAgent", "ClaudeTranslatorConfig", "providers.claude.translator", "providers.claude.config"),
    # Gemini
    ("gemini", "chat"): ("GeminiChatAgent", "GeminiConfig", "providers.gemini.chat", "providers.gemini.config"),
    ("gemini", "code"): ("GeminiChatAgent", "GeminiConfig", "providers.gemini.chat", "providers.gemini.config"),
    ("gemini", "data"): ("GeminiDataAgent", "GeminiDataConfig", "providers.gemini.data", "providers.gemini.config"),
    ("gemini", "translation"): ("GeminiTranslatorAgent", "GeminiTranslatorConfig", "providers.gemini.translator", "providers.gemini.config"),
    # GPT
    ("gpt", "chat"): ("GPTChatAgent", "GPTConfig", "providers.gpt.chat", "providers.gpt.config"),
    ("gpt", "code"): ("GPTChatAgent", "GPTConfig", "providers.gpt.chat", "providers.gpt.config"),
    # Perplexity
    ("perplexity", "chat"): ("PerplexityChatAgent", "PerplexityConfig", "providers.pplx.chat", "providers.pplx.config"),
    ("perplexity", "research"): ("PerplexityResearchAgent", "PerplexityResearchConfig", "providers.pplx.research", "providers.pplx.config"),
    # OpenAI
    ("openai", "chat"): ("OpenAIChatAgent", "OpenAIConfig", "providers.openai.chat", "providers.openai.config"),
    ("openai", "code"): ("OpenAIDataAgent", "OpenAIDataConfig", "providers.openai.data", "providers.openai.config"),
    ("openai", "data"): ("OpenAIDataAgent", "OpenAIDataConfig", "providers.openai.data", "providers.openai.config"),
    # OpenRouter
    ("openrouter", "chat"): ("OpenRouterChatAgent", "OpenRouterConfig", "providers.openrouter.chat", "providers.openrouter.config"),
    ("openrouter", "code"): ("OpenRouterDataAgent", "OpenRouterDataConfig", "providers.openrouter.data", "providers.openrouter.config"),
    ("openrouter", "data"): ("OpenRouterDataAgent", "OpenRouterDataConfig", "providers.openrouter.data", "providers.openrouter.config"),
    # Copilot
    ("copilot", "chat"): ("CopilotChatAgent", "CopilotConfig", "providers.copilot.chat", "providers.copilot.config"),
    ("copilot", "code"): ("CopilotChatAgent", "CopilotConfig", "providers.copilot.chat", "providers.copilot.config"),
}

# Auth key used to check if a provider is available
_PROVIDER_AUTH_KEY: dict[str, str] = {
    "claude": "claude_storage",
    "gemini": "gemini_storage",
    "gpt": "gpt_storage",
    "perplexity": "pplx_storage",
    "openai": "openai_key",
    "openrouter": "openrouter_key",
    "copilot": "copilot_cli",
}


class CapabilityResolver:
    """Maps UserRequirements → concrete component selections."""

    def resolve(self, req: UserRequirements) -> ResolvedComponents:
        """Resolve requirements into concrete components."""
        provider = self._resolve_provider(req)
        transport = _PROVIDER_TRANSPORT[provider]
        use_case = req.use_case

        # Look up agent/config classes
        key = (provider, use_case)
        if key not in _AGENT_MAP:
            # Fall back to chat for unsupported use cases
            key = (provider, "chat")
            if key not in _AGENT_MAP:
                raise CompilerError(
                    f"No agent available for provider={provider}, use_case={use_case}"
                )
            logger.warning(
                "No %s agent for %s, falling back to chat", use_case, provider
            )

        agent_cls, config_cls, agent_mod, config_mod = _AGENT_MAP[key]

        capabilities = self._list_capabilities(req, provider)

        return ResolvedComponents(
            provider=provider,
            transport=transport,
            agent_class_name=agent_cls,
            config_class_name=config_cls,
            agent_module=f"universal_agents.{agent_mod}",
            config_module=f"universal_agents.{config_mod}",
            capabilities=capabilities,
            use_monitoring=req.needs_monitoring,
        )

    def _resolve_provider(self, req: UserRequirements) -> str:
        """Select the best provider given requirements and available auth."""
        auth = req.auth_available

        # 1. Explicit preference wins (if auth available)
        if req.provider_preference:
            auth_key = _PROVIDER_AUTH_KEY.get(req.provider_preference, "")
            if auth.get(auth_key, False):
                return req.provider_preference
            logger.warning(
                "Preferred provider %s not available (missing auth: %s)",
                req.provider_preference,
                auth_key,
            )

        # 2. Capability-driven selection
        if req.needs_citations:
            if auth.get("pplx_storage"):
                return "perplexity"

        if req.needs_translation and req.needs_file_upload:
            if auth.get("claude_storage"):
                return "claude"
            if auth.get("gemini_storage"):
                return "gemini"

        # 3. Quality/speed-driven selection (checked before cost)
        if req.latency_sensitivity == "speed":
            if auth.get("openai_key"):
                return "openai"
            if auth.get("openrouter_key"):
                return "openrouter"

        if req.needs_thinking:
            if auth.get("openai_key"):
                return "openai"
            if auth.get("claude_storage"):
                return "claude"

        # 4. Cost-driven selection
        if req.cost_sensitivity == "free":
            if auth.get("openrouter_key"):
                return "openrouter"
            for p in ("gemini", "claude", "gpt"):
                if auth.get(f"{p}_storage"):
                    return p

        # 5. Default fallback — try providers in priority order
        for p in ("openai", "openrouter", "claude", "gemini", "gpt", "copilot"):
            auth_key = _PROVIDER_AUTH_KEY.get(p, "")
            if auth.get(auth_key, False):
                return p

        raise CompilerError("No provider available with current authentication")

    @staticmethod
    def _list_capabilities(req: UserRequirements, provider: str) -> list[str]:
        """Enumerate the capabilities the compiled agent will have."""
        caps = [req.use_case]
        if req.needs_thinking:
            caps.append("thinking")
        if req.needs_json_output:
            caps.append("json_output")
        if req.needs_file_upload:
            caps.append("file_upload")
        if req.needs_translation:
            caps.append("translation")
        if req.needs_citations:
            caps.append("citations")
        if req.needs_streaming:
            caps.append("streaming")
        if req.needs_fallback:
            caps.append("fallback")
        if req.needs_monitoring:
            caps.append("monitoring")
        return caps
