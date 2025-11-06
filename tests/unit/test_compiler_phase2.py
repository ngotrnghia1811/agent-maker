"""Tests for compiler Phase 2 — CapabilityResolver, ConfigBuilder, AgentAssembler."""

import pytest

from universal_agents.compiler.requirements import UserRequirements
from universal_agents.compiler.capability_resolver import (
    CapabilityResolver,
    CompilerError,
    ResolvedComponents,
)
from universal_agents.compiler.config_builder import ConfigBuilder
from universal_agents.compiler.agent_assembler import AgentAssembler, CompiledAgent


# ======================================================================
# UserRequirements — apply_use_case_defaults
# ======================================================================


class TestUserRequirements:
    def test_defaults(self):
        req = UserRequirements()
        assert req.use_case == "chat"
        assert req.cost_sensitivity == "free"
        assert req.output_format == "script"
        assert req.auth_available == {}

    def test_apply_data_defaults(self):
        req = UserRequirements(use_case="data")
        req.apply_use_case_defaults()
        assert req.needs_json_output is True

    def test_apply_translation_defaults(self):
        req = UserRequirements(use_case="translation")
        req.apply_use_case_defaults()
        assert req.needs_file_upload is True
        assert req.needs_json_output is True
        assert req.needs_translation is True

    def test_apply_research_defaults(self):
        req = UserRequirements(use_case="research")
        req.apply_use_case_defaults()
        assert req.needs_citations is True

    def test_apply_code_defaults(self):
        req = UserRequirements(use_case="code")
        req.apply_use_case_defaults()
        assert req.needs_thinking is True

    def test_chat_defaults_unchanged(self):
        req = UserRequirements(use_case="chat")
        req.apply_use_case_defaults()
        assert req.needs_json_output is False
        assert req.needs_thinking is False


# ======================================================================
# CapabilityResolver — provider resolution
# ======================================================================


class TestCapabilityResolverProvider:
    def _req(self, **kw) -> UserRequirements:
        """Shorthand for requirements with openai_key auth by default."""
        kw.setdefault("auth_available", {"openai_key": True})
        return UserRequirements(**kw)

    def test_explicit_preference_with_auth(self):
        resolver = CapabilityResolver()
        req = self._req(provider_preference="openai")
        result = resolver.resolve(req)
        assert result.provider == "openai"

    def test_explicit_preference_missing_auth_fallback(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            provider_preference="claude",
            auth_available={"openai_key": True},
        )
        result = resolver.resolve(req)
        # claude auth missing → falls through to default priority
        assert result.provider == "openai"

    def test_citations_prefers_perplexity(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            needs_citations=True,
            auth_available={"pplx_storage": True},
        )
        result = resolver.resolve(req)
        assert result.provider == "perplexity"

    def test_translation_prefers_claude(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            needs_translation=True,
            needs_file_upload=True,
            auth_available={"claude_storage": True, "gemini_storage": True},
        )
        result = resolver.resolve(req)
        assert result.provider == "claude"

    def test_free_prefers_openrouter(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            cost_sensitivity="free",
            auth_available={"openrouter_key": True, "openai_key": True},
        )
        result = resolver.resolve(req)
        assert result.provider == "openrouter"

    def test_free_without_openrouter_falls_to_browser(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            cost_sensitivity="free",
            auth_available={"gemini_storage": True},
        )
        result = resolver.resolve(req)
        assert result.provider == "gemini"

    def test_speed_prefers_openai(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            latency_sensitivity="speed",
            auth_available={"openai_key": True, "openrouter_key": True},
        )
        result = resolver.resolve(req)
        assert result.provider == "openai"

    def test_thinking_prefers_openai(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            needs_thinking=True,
            auth_available={"openai_key": True, "claude_storage": True},
        )
        result = resolver.resolve(req)
        assert result.provider == "openai"

    def test_default_priority_order(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            auth_available={"gemini_storage": True, "copilot_cli": True},
        )
        result = resolver.resolve(req)
        assert result.provider == "gemini"

    def test_no_auth_raises(self):
        resolver = CapabilityResolver()
        req = UserRequirements(auth_available={})
        with pytest.raises(CompilerError, match="No provider available"):
            resolver.resolve(req)


# ======================================================================
# CapabilityResolver — agent class resolution
# ======================================================================


class TestCapabilityResolverAgentClass:
    def test_openai_chat(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            use_case="chat",
            auth_available={"openai_key": True},
        )
        result = resolver.resolve(req)
        assert result.agent_class_name == "OpenAIChatAgent"
        assert result.config_class_name == "OpenAIConfig"
        assert result.transport == "api"

    def test_openai_data(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            use_case="data",
            auth_available={"openai_key": True},
        )
        result = resolver.resolve(req)
        assert result.agent_class_name == "OpenAIDataAgent"
        assert result.config_class_name == "OpenAIDataConfig"

    def test_claude_translation(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            use_case="translation",
            needs_translation=True,
            needs_file_upload=True,
            provider_preference="claude",
            auth_available={"claude_storage": True},
        )
        result = resolver.resolve(req)
        assert result.agent_class_name == "ClaudeTranslatorAgent"
        assert result.config_class_name == "ClaudeTranslatorConfig"
        assert result.transport == "browser"

    def test_gemini_data(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            use_case="data",
            provider_preference="gemini",
            auth_available={"gemini_storage": True},
        )
        result = resolver.resolve(req)
        assert result.agent_class_name == "GeminiDataAgent"

    def test_copilot_chat(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            provider_preference="copilot",
            auth_available={"copilot_cli": True},
        )
        result = resolver.resolve(req)
        assert result.agent_class_name == "CopilotChatAgent"
        assert result.transport == "cli"

    def test_unsupported_use_case_falls_back_to_chat(self):
        """GPT doesn't have a data agent; should fall back to chat."""
        resolver = CapabilityResolver()
        req = UserRequirements(
            use_case="data",
            provider_preference="gpt",
            auth_available={"gpt_storage": True},
        )
        result = resolver.resolve(req)
        assert result.agent_class_name == "GPTChatAgent"

    def test_perplexity_research(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            use_case="research",
            needs_citations=True,
            auth_available={"pplx_storage": True},
        )
        result = resolver.resolve(req)
        assert result.agent_class_name == "PerplexityChatAgent"

    def test_openrouter_code(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            use_case="code",
            provider_preference="openrouter",
            auth_available={"openrouter_key": True},
        )
        result = resolver.resolve(req)
        assert result.agent_class_name == "OpenRouterDataAgent"


# ======================================================================
# CapabilityResolver — capabilities list
# ======================================================================


class TestCapabilitiesList:
    def test_basic_chat(self):
        resolver = CapabilityResolver()
        req = UserRequirements(auth_available={"openai_key": True})
        result = resolver.resolve(req)
        assert "chat" in result.capabilities

    def test_thinking_flag(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            needs_thinking=True,
            auth_available={"openai_key": True},
        )
        result = resolver.resolve(req)
        assert "thinking" in result.capabilities

    def test_multiple_capabilities(self):
        resolver = CapabilityResolver()
        req = UserRequirements(
            use_case="data",
            needs_json_output=True,
            needs_monitoring=True,
            needs_fallback=True,
            auth_available={"openai_key": True},
        )
        result = resolver.resolve(req)
        assert "data" in result.capabilities
        assert "json_output" in result.capabilities
        assert "monitoring" in result.capabilities
        assert "fallback" in result.capabilities
        assert result.use_monitoring is True


# ======================================================================
# ConfigBuilder
# ======================================================================


class TestConfigBuilder:
    def _resolve(self, **kw) -> tuple[ResolvedComponents, UserRequirements]:
        req = UserRequirements(**kw)
        resolver = CapabilityResolver()
        comp = resolver.resolve(req)
        return comp, req

    def test_api_model_set(self):
        comp, req = self._resolve(
            use_case="chat",
            model_preference="my-custom-model",
            auth_available={"openai_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["model"] == "my-custom-model"

    def test_default_model_used(self):
        comp, req = self._resolve(
            use_case="chat",
            auth_available={"openai_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg.get("model") == "gpt-4.1-mini"

    def test_system_prompt_for_api(self):
        comp, req = self._resolve(
            use_case="chat",
            custom_system_prompt="You are a pirate.",
            auth_available={"openai_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["system_prompt"] == "You are a pirate."

    def test_system_prompt_in_browser(self):
        comp, req = self._resolve(
            use_case="chat",
            custom_system_prompt="You are a pirate.",
            provider_preference="claude",
            auth_available={"claude_storage": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["system_prompt"] == "You are a pirate."

    def test_stream_flag(self):
        comp, req = self._resolve(
            use_case="chat",
            needs_streaming=True,
            auth_available={"openai_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["stream"] is True

    def test_openai_thinking_sets_reasoning(self):
        comp, req = self._resolve(
            needs_thinking=True,
            auth_available={"openai_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["reasoning_effort"] == "medium"

    def test_openrouter_thinking_sets_budget(self):
        comp, req = self._resolve(
            needs_thinking=True,
            provider_preference="openrouter",
            auth_available={"openrouter_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["enable_thinking"] is True
        assert cfg["thinking_budget"] == 10000

    def test_data_use_case_timeout(self):
        comp, req = self._resolve(
            use_case="data",
            auth_available={"openai_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["timeout"] == 600
        assert cfg["max_tokens"] == 16384

    def test_browser_extract_thinking(self):
        comp, req = self._resolve(
            needs_thinking=True,
            provider_preference="claude",
            auth_available={"claude_storage": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["extract_thinking"] is True

    def test_gemini_thinking_model(self):
        comp, req = self._resolve(
            needs_thinking=True,
            provider_preference="gemini",
            auth_available={"gemini_storage": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["required_model"] == "thinking"

    def test_openai_json_response_format(self):
        comp, req = self._resolve(
            use_case="data",
            needs_json_output=True,
            auth_available={"openai_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["response_format"] == {"type": "json_object"}

    def test_cli_minimal_config(self):
        comp, req = self._resolve(
            provider_preference="copilot",
            auth_available={"copilot_cli": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        # CLI has no model or complex config
        assert "stream" not in cfg

    def test_claude_thinking_sets_temperature(self):
        comp, req = self._resolve(
            needs_thinking=True,
            provider_preference="claude",
            auth_available={"claude_storage": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert cfg["extract_thinking"] is True
        assert cfg["temperature"] == 1.0

    def test_openrouter_claude_thinking_sets_temperature(self):
        comp, req = self._resolve(
            needs_thinking=True,
            provider_preference="openrouter",
            auth_available={"openrouter_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        # Default openrouter thinking model has anthropic/claude in name
        if "claude" in cfg.get("model", "") or "anthropic" in cfg.get("model", ""):
            assert cfg["temperature"] == 1.0

    def test_free_fallback_models(self):
        comp, req = self._resolve(
            use_case="chat",
            cost_sensitivity="free",
            needs_fallback=True,
            provider_preference="openrouter",
            auth_available={"openrouter_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert "fallback_models" in cfg
        assert all(":free" in m for m in cfg["fallback_models"])

    def test_paid_fallback_models(self):
        comp, req = self._resolve(
            use_case="chat",
            cost_sensitivity="unlimited",
            needs_fallback=True,
            provider_preference="openrouter",
            auth_available={"openrouter_key": True},
        )
        cfg = ConfigBuilder().build(comp, req)
        assert "fallback_models" in cfg
        # Paid fallbacks should not all be free
        assert not all(":free" in m for m in cfg["fallback_models"])


# ======================================================================
# AgentAssembler — script generation
# ======================================================================


class TestAgentAssemblerScript:
    def _assemble(self, **kw) -> CompiledAgent:
        req = UserRequirements(**kw)
        resolver = CapabilityResolver()
        comp = resolver.resolve(req)
        return AgentAssembler().assemble(comp, req)

    def test_script_generated(self):
        compiled = self._assemble(
            use_case="chat",
            output_format="script",
            auth_available={"openai_key": True},
        )
        assert compiled.script is not None
        assert "OpenAIChatAgent" in compiled.script
        assert "OpenAIConfig" in compiled.script
        assert "asyncio.run" in compiled.script

    def test_script_has_imports(self):
        compiled = self._assemble(
            use_case="chat",
            output_format="script",
            auth_available={"openai_key": True},
        )
        assert "from universal_agents" in compiled.script
        assert "import os" in compiled.script

    def test_data_script_has_run(self):
        compiled = self._assemble(
            use_case="data",
            output_format="script",
            auth_available={"openai_key": True},
        )
        assert "agent.run(" in compiled.script
        assert "input_json" in compiled.script

    def test_config_only_no_script(self):
        compiled = self._assemble(
            use_case="chat",
            output_format="config_only",
            auth_available={"openai_key": True},
        )
        assert compiled.script is None
        assert compiled.agent_instance is None
        assert compiled.config_kwargs is not None

    def test_compiled_agent_fields(self):
        compiled = self._assemble(
            use_case="data",
            output_format="config_only",
            auth_available={"openai_key": True},
        )
        assert compiled.provider == "openai"
        assert compiled.agent_class_name == "OpenAIDataAgent"
        assert compiled.config_class_name == "OpenAIDataConfig"
        assert "data" in compiled.capabilities

    def test_openrouter_script_has_model(self):
        compiled = self._assemble(
            use_case="chat",
            output_format="script",
            provider_preference="openrouter",
            auth_available={"openrouter_key": True},
        )
        assert "OpenRouterChatAgent" in compiled.script
        assert "model=" in compiled.script

    def test_translation_script(self):
        compiled = self._assemble(
            use_case="translation",
            needs_translation=True,
            needs_file_upload=True,
            provider_preference="claude",
            output_format="script",
            auth_available={"claude_storage": True},
        )
        assert "ClaudeTranslatorAgent" in compiled.script
        assert "translate(" in compiled.script

    def test_monitoring_script_includes_wrapper(self):
        compiled = self._assemble(
            use_case="chat",
            needs_monitoring=True,
            output_format="script",
            auth_available={"openai_key": True},
        )
        assert "MonitoredAgent" in compiled.script
        assert "AgentRegistry" in compiled.script
        assert "Reporter" in compiled.script
        assert "_base_agent" in compiled.script

    def test_no_monitoring_script_no_wrapper(self):
        compiled = self._assemble(
            use_case="chat",
            needs_monitoring=False,
            output_format="script",
            auth_available={"openai_key": True},
        )
        assert "MonitoredAgent" not in compiled.script

    def test_description_field_exists(self):
        compiled = self._assemble(
            use_case="chat",
            output_format="config_only",
            auth_available={"openai_key": True},
        )
        # description is None unless Compiler-LLM is used
        assert hasattr(compiled, "description")


# ======================================================================
# End-to-end pipeline (resolver → builder → assembler)
# ======================================================================


class TestEndToEnd:
    def test_full_pipeline_openai_data(self):
        req = UserRequirements(
            use_case="data",
            needs_json_output=True,
            needs_thinking=True,
            custom_system_prompt="Extract structured data.",
            output_format="script",
            auth_available={"openai_key": True},
        )
        req.apply_use_case_defaults()

        resolver = CapabilityResolver()
        comp = resolver.resolve(req)
        assert comp.provider == "openai"
        assert comp.agent_class_name == "OpenAIDataAgent"

        builder = ConfigBuilder()
        cfg = builder.build(comp, req)
        assert cfg["response_format"] == {"type": "json_object"}
        assert cfg["reasoning_effort"] == "medium"
        assert cfg["system_prompt"] == "Extract structured data."

        assembler = AgentAssembler(builder)
        compiled = assembler.assemble(comp, req)
        assert "OpenAIDataAgent" in compiled.script
        assert "json_output" in compiled.capabilities

    def test_full_pipeline_openrouter_free_chat(self):
        req = UserRequirements(
            use_case="chat",
            cost_sensitivity="free",
            output_format="config_only",
            auth_available={"openrouter_key": True, "openai_key": True},
        )
        resolver = CapabilityResolver()
        comp = resolver.resolve(req)
        assert comp.provider == "openrouter"

        compiled = AgentAssembler().assemble(comp, req)
        assert compiled.config_kwargs.get("model") == "anthropic/claude-sonnet-4"
        assert compiled.script is None

    def test_full_pipeline_perplexity_research(self):
        req = UserRequirements(
            use_case="research",
            auth_available={"pplx_storage": True, "openai_key": True},
        )
        req.apply_use_case_defaults()
        assert req.needs_citations is True

        resolver = CapabilityResolver()
        comp = resolver.resolve(req)
        assert comp.provider == "perplexity"
        assert comp.agent_class_name == "PerplexityChatAgent"
