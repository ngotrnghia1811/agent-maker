"""Integration tests — full compiler pipeline: preset/interview → compile → verify.

These tests exercise the end-to-end flow through all compiler components
without mocking internal modules (only external I/O is mocked).
"""

import io
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from universal_agents.compiler import (
    AgentCompiler,
    AuthDetector,
    AuthStatus,
    CompilerLLM,
    QuestionFlow,
    PRESETS,
)


# ======================================================================
# Helpers
# ======================================================================

def _mock_auth(available: dict[str, bool] | None = None) -> AuthDetector:
    det = AuthDetector.__new__(AuthDetector)
    status = AuthStatus(
        available=available or {"openai_key": True, "openrouter_key": True},
        details={},
    )
    det.detect = lambda: status
    return det


def _compile_preset(preset_name: str, auth: dict[str, bool] | None = None):
    """Compile a preset and return the CompiledAgent."""
    compiler = AgentCompiler(auth_detector=_mock_auth(auth))
    return compiler.compile_from_spec(PRESETS[preset_name])


# ======================================================================
# Preset → compile → verify structure
# ======================================================================

class TestPresetCompilation:
    """Each preset should compile successfully and produce a valid CompiledAgent."""

    def test_free_chat(self):
        result = _compile_preset("free-chat")
        assert result.provider == "openrouter"
        assert result.agent_class_name == "OpenRouterChatAgent"
        assert result.script is not None
        assert "OpenRouterChatAgent" in result.script
        assert "OpenRouterConfig" in result.script
        assert result.config_kwargs.get("model") is not None

    def test_openai_data(self):
        result = _compile_preset("openai-data", auth={"openai_key": True})
        assert result.provider == "openai"
        assert result.agent_class_name == "OpenAIDataAgent"
        assert "json" in result.capabilities or result.config_kwargs.get("response_format") is not None
        assert result.script is not None
        assert "OpenAIDataAgent" in result.script

    def test_openrouter_free(self):
        result = _compile_preset("openrouter-free")
        assert result.provider == "openrouter"
        assert result.script is not None

    def test_claude_translate(self):
        result = _compile_preset("claude-translate", auth={"claude_storage": True})
        assert result.provider == "claude"
        assert "Translator" in result.agent_class_name
        assert result.script is not None

    def test_research(self):
        result = _compile_preset("research", auth={"pplx_storage": True, "openai_key": True})
        assert result.provider == "perplexity"
        assert result.agent_class_name == "PerplexityChatAgent"
        assert result.script is not None

    def test_code_review(self):
        result = _compile_preset("code-review", auth={"openai_key": True})
        assert result.provider == "openai"
        assert result.script is not None
        # Code review preset requests thinking
        assert "thinking" in result.capabilities or result.config_kwargs.get("reasoning_effort") is not None


# ======================================================================
# Spec → compile → instantiate (dynamic import)
# ======================================================================

class TestInstantiation:
    """CompiledAgent should be importable and instantiatable (no browser needed)."""

    def test_openai_chat_instantiates(self):
        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
        compiled = compiler.compile_from_spec({
            "use_case": "chat",
            "provider_preference": "openai",
            "output_format": "instance",
        })
        assert compiled.agent_instance is not None
        assert type(compiled.agent_instance).__name__ == "OpenAIChatAgent"

    def test_openrouter_data_instantiates(self):
        compiler = AgentCompiler(auth_detector=_mock_auth({"openrouter_key": True}))
        compiled = compiler.compile_from_spec({
            "use_case": "data",
            "provider_preference": "openrouter",
            "output_format": "instance",
        })
        assert compiled.agent_instance is not None
        assert type(compiled.agent_instance).__name__ == "OpenRouterDataAgent"

    def test_openai_data_instantiates(self):
        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
        compiled = compiler.compile_from_spec({
            "use_case": "data",
            "provider_preference": "openai",
            "output_format": "instance",
        })
        assert compiled.agent_instance is not None
        assert type(compiled.agent_instance).__name__ == "OpenAIDataAgent"


# ======================================================================
# Interactive interview → compile → verify
# ======================================================================

class TestInteractiveCompilation:
    """Full interactive interview followed by compilation."""

    def test_interactive_chat_openai(self):
        answers = [
            "1",  # 0.1: keep compiler-LLM default
            "1",  # 1.1: chat
            "2",  # 2.1: no thinking
            "2",  # 2.2: balanced
            "2",  # 2.3: no streaming
            "1",  # 3.1: free
            "3",  # 3.2: openai
            "1",  # 3.3: auth confirm
            "1",  # 3.4: default model
            "1",  # 4.1: yes fallback
            "2",  # 4.2: no monitoring
            "1",  # 5.1: default prompt
            "2",  # 5.2: script
        ]
        answer_iter = iter(answers)
        buf = io.StringIO()
        flow = QuestionFlow(
            auth_detector=_mock_auth({"openai_key": True, "openrouter_key": True}),
            input_fn=lambda p: next(answer_iter),
            output=buf,
        )
        req = flow.interview()

        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True, "openrouter_key": True}))
        compiled = compiler.compile_from_spec(req.__dict__)
        assert compiled.provider in ("openai", "openrouter")
        assert compiled.script is not None

    def test_interactive_data_openrouter(self):
        answers = [
            "1",  # 0.1: keep compiler-LLM default
            "2",  # 1.1: data
            "2",  # 1.2: no file upload
            "2",  # 2.1: no thinking
            "2",  # 2.2: balanced
            "2",  # 2.3: no streaming
            "1",  # 3.1: free
            "8",  # 3.2: no preference
            "1",  # 3.3: auth confirm
            "1",  # 3.4: default model
            "1",  # 4.1: fallback
            "2",  # 4.2: no monitoring
            "1",  # 5.1: default prompt
            "2",  # 5.2: script
        ]
        answer_iter = iter(answers)
        buf = io.StringIO()
        flow = QuestionFlow(
            auth_detector=_mock_auth({"openai_key": True, "openrouter_key": True}),
            input_fn=lambda p: next(answer_iter),
            output=buf,
        )
        req = flow.interview()
        assert req.use_case == "data"
        assert req.needs_json_output is True

        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True, "openrouter_key": True}))
        compiled = compiler.compile_from_spec(req.__dict__)
        assert compiled.script is not None
        assert "DataAgent" in compiled.agent_class_name or "Data" in compiled.agent_class_name


# ======================================================================
# JSON round-trip
# ======================================================================

class TestJsonRoundTrip:
    """compile_from_json should parse a JSON spec and produce valid output."""

    def test_json_spec_round_trip(self):
        spec = {
            "use_case": "chat",
            "provider_preference": "openai",
            "cost_sensitivity": "paid",
            "needs_thinking": True,
            "output_format": "script",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(spec, f)
            f.flush()
            path = f.name
        try:
            compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
            compiled = compiler.compile_from_json(path)
            assert compiled.provider == "openai"
            assert compiled.script is not None
            assert "thinking" in compiled.capabilities
        finally:
            os.unlink(path)

    def test_json_spec_minimal(self):
        spec = {"use_case": "chat"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(spec, f)
            f.flush()
            path = f.name
        try:
            compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True, "openrouter_key": True}))
            compiled = compiler.compile_from_json(path)
            assert compiled.script is not None
        finally:
            os.unlink(path)


# ======================================================================
# Config-only output
# ======================================================================

class TestConfigOnlyOutput:
    def test_config_only_no_script(self):
        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
        compiled = compiler.compile_from_spec({
            "use_case": "chat",
            "provider_preference": "openai",
            "output_format": "config_only",
        })
        assert compiled.script is None
        assert compiled.config_kwargs is not None
        assert compiled.agent_class_name is not None


# ======================================================================
# Fallback behavior
# ======================================================================

class TestFallbackBehavior:
    def test_preferred_unavailable_falls_back(self):
        """If preferred provider has no auth, should fall back."""
        compiler = AgentCompiler(auth_detector=_mock_auth({"openrouter_key": True}))
        compiled = compiler.compile_from_spec({
            "use_case": "chat",
            "provider_preference": "openai",  # but no openai_key
            "output_format": "script",
        })
        # Should fall back to openrouter since that's available
        assert compiled.provider == "openrouter"
        assert compiled.script is not None

    def test_no_preference_picks_best_available(self):
        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
        compiled = compiler.compile_from_spec({
            "use_case": "data",
            "needs_json_output": True,
            "output_format": "script",
        })
        assert compiled.provider == "openai"
        assert "DataAgent" in compiled.agent_class_name
