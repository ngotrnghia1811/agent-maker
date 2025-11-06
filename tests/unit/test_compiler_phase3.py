"""Tests for compiler Phase 3+4 — QuestionFlow, AgentCompiler, CLI."""

import io
import json
import os
import tempfile
from unittest.mock import patch

import pytest

from universal_agents.compiler.question_flow import QuestionFlow, PRESETS, _build_questions
from universal_agents.compiler.compiler import AgentCompiler
from universal_agents.compiler.auth_detector import AuthDetector, AuthStatus
from universal_agents.compiler.requirements import UserRequirements
from universal_agents.compiler.__main__ import main as cli_main


# ======================================================================
# Helpers
# ======================================================================

def _mock_auth(available: dict[str, bool] | None = None) -> AuthDetector:
    """Create an AuthDetector that returns fixed results."""
    det = AuthDetector.__new__(AuthDetector)
    status = AuthStatus(
        available=available or {"openai_key": True, "openrouter_key": True},
        details={},
    )
    det.detect = lambda: status
    return det


def _make_flow(answers: list[str], auth: dict[str, bool] | None = None) -> tuple[QuestionFlow, io.StringIO]:
    """Create a QuestionFlow with canned answers."""
    answer_iter = iter(answers)
    buf = io.StringIO()
    flow = QuestionFlow(
        auth_detector=_mock_auth(auth),
        input_fn=lambda prompt: next(answer_iter),
        output=buf,
    )
    return flow, buf


# ======================================================================
# Question definitions
# ======================================================================


class TestQuestionDefinitions:
    def test_questions_built(self):
        qs = _build_questions()
        assert len(qs) > 10

    def test_all_have_ids(self):
        qs = _build_questions()
        ids = [q.id for q in qs]
        assert "0.1" in ids
        assert "1.1" in ids
        assert "5.2" in ids

    def test_all_have_options(self):
        for q in _build_questions():
            assert len(q.options) >= 2, f"Question {q.id} has < 2 options"


# ======================================================================
# QuestionFlow — presets
# ======================================================================


class TestPresets:
    def test_all_presets_valid(self):
        for name, spec in PRESETS.items():
            req = UserRequirements(**spec)
            assert req.use_case in ("chat", "data", "translation", "research", "code")

    def test_load_preset_free_chat(self):
        flow, _ = _make_flow([])
        req = flow.interview(preset="free-chat")
        assert req.use_case == "chat"
        assert req.cost_sensitivity == "free"
        assert req.output_format == "script"
        assert req.auth_available  # auto-detected

    def test_load_preset_openai_data(self):
        flow, _ = _make_flow([], auth={"openai_key": True})
        req = flow.interview(preset="openai-data")
        assert req.use_case == "data"
        assert req.needs_json_output is True
        assert req.needs_thinking is True
        assert req.provider_preference == "openai"

    def test_unknown_preset_raises(self):
        flow, _ = _make_flow([])
        with pytest.raises(ValueError, match="Unknown preset"):
            flow.interview(preset="nonexistent")


# ======================================================================
# QuestionFlow — interactive interview
# ======================================================================


class TestInteractiveFlow:
    def test_full_interview_chat_openai(self):
        """Simulate choosing chat + openai through all questions."""
        answers = [
            "1",  # 0.1: keep compiler-LLM default
            "1",  # 1.1: chat
            # 1.2 skipped (chat)
            "2",  # 2.1: no thinking
            "2",  # 2.2: balanced
            "2",  # 2.3: no streaming
            "1",  # 3.1: free
            "3",  # 3.2: openai
            "1",  # 3.3 auth confirm (before 3.4)
            "1",  # 3.4: use provider default
            "1",  # 4.1: yes fallback (API)
            "2",  # 4.2: no monitoring
            "1",  # 5.1: default prompt
            "2",  # 5.2: script
        ]
        flow, output = _make_flow(answers, auth={"openai_key": True, "openrouter_key": True})
        req = flow.interview()

        assert req.use_case == "chat"
        assert req.needs_thinking is False
        assert req.latency_sensitivity == "balanced"
        assert req.output_format == "script"

    def test_interview_data_use_case_sets_defaults(self):
        """Selecting data sets needs_json_output automatically."""
        answers = [
            "1",  # 0.1
            "2",  # 1.1: data
            "2",  # 1.2: no file upload
            # 2.1 skipped (needs_thinking not set by data)
            "2",  # 2.1: no thinking (not skipped, data doesn't set thinking)
            "2",  # 2.2: balanced
            "2",  # 2.3: no streaming
            "1",  # 3.1: free
            "8",  # 3.2: no preference
            "1",  # 3.3 auth confirm
            "1",  # 3.4: default model
            "1",  # 4.1: fallback
            "2",  # 4.2: no monitoring
            "1",  # 5.1: default prompt
            "2",  # 5.2: script
        ]
        flow, _ = _make_flow(answers, auth={"openai_key": True, "openrouter_key": True})
        req = flow.interview()

        assert req.use_case == "data"
        assert req.needs_json_output is True  # auto-set

    def test_interview_invalid_input_retries(self):
        """Invalid input should be retried."""
        answers = [
            "x",  # invalid → retry
            "99", # out of range → retry
            "1",  # 0.1: valid
            "1",  # 1.1: chat
            "2",  # 2.1: no thinking
            "2",  # 2.2
            "2",  # 2.3
            "1",  # 3.1
            "8",  # 3.2
            "1",  # 3.3
            "1",  # 3.4
            "2",  # 4.1
            "2",  # 4.2
            "1",  # 5.1
            "2",  # 5.2
        ]
        flow, output = _make_flow(answers, auth={"openai_key": True})
        req = flow.interview()
        assert req.use_case == "chat"
        assert "Please enter a number" in output.getvalue()


# ======================================================================
# AgentCompiler — orchestrator
# ======================================================================


class TestAgentCompiler:
    def test_compile_from_spec(self):
        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
        compiled = compiler.compile_from_spec({
            "use_case": "chat",
            "provider_preference": "openai",
            "output_format": "script",
        })
        assert compiled.provider == "openai"
        assert compiled.agent_class_name == "OpenAIChatAgent"
        assert compiled.script is not None
        assert "OpenAIChatAgent" in compiled.script

    def test_compile_from_spec_config_only(self):
        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
        compiled = compiler.compile_from_spec({
            "use_case": "data",
            "output_format": "config_only",
        })
        assert compiled.script is None
        assert compiled.agent_class_name == "OpenAIDataAgent"

    def test_compile_from_spec_unknown_keys_ignored(self):
        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
        compiled = compiler.compile_from_spec({
            "use_case": "chat",
            "bogus_key": "should be ignored",
        })
        assert compiled.provider == "openai"

    def test_compile_interactive_with_preset(self):
        compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
        compiled = compiler.compile_interactive(preset="openai-data")
        assert compiled.provider == "openai"
        assert compiled.agent_class_name == "OpenAIDataAgent"

    def test_compile_from_json(self):
        spec = {"use_case": "chat", "output_format": "script"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(spec, f)
            f.flush()
            path = f.name
        try:
            compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
            compiled = compiler.compile_from_json(path)
            assert compiled.script is not None
        finally:
            os.unlink(path)


# ======================================================================
# CLI (__main__)
# ======================================================================


class TestCLI:
    def test_list_presets(self, capsys):
        ret = cli_main(["--list-presets"])
        assert ret == 0
        output = capsys.readouterr().out
        assert "free-chat" in output
        assert "openai-data" in output

    def test_preset_to_stdout(self, capsys):
        with patch(
            "universal_agents.compiler.compiler.AuthDetector",
            return_value=_mock_auth({"openai_key": True}),
        ):
            compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
            with patch(
                "universal_agents.compiler.__main__.AgentCompiler",
                return_value=compiler,
            ):
                ret = cli_main(["--preset", "openai-data"])
        assert ret == 0
        output = capsys.readouterr().out
        assert "OpenAIDataAgent" in output

    def test_preset_to_file(self, capsys):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            path = f.name
        try:
            compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
            with patch(
                "universal_agents.compiler.__main__.AgentCompiler",
                return_value=compiler,
            ):
                ret = cli_main(["--preset", "openai-data", "--output", path])
            assert ret == 0
            content = open(path).read()
            assert "OpenAIDataAgent" in content
        finally:
            os.unlink(path)

    def test_spec_file(self, capsys):
        spec = {"use_case": "chat", "output_format": "config_only"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(spec, f)
            f.flush()
            spec_path = f.name
        try:
            compiler = AgentCompiler(auth_detector=_mock_auth({"openai_key": True}))
            with patch(
                "universal_agents.compiler.__main__.AgentCompiler",
                return_value=compiler,
            ):
                ret = cli_main(["--spec", spec_path])
            assert ret == 0
            output = capsys.readouterr().out
            assert "Provider:" in output
        finally:
            os.unlink(spec_path)


# ======================================================================
# QuestionFlow — skip logic
# ======================================================================


class TestSkipLogic:
    """Test that questions are correctly skipped based on prior answers."""

    def test_file_upload_skipped_for_chat(self):
        """Q1.2 (file upload) should be skipped when use_case is chat."""
        qs = _build_questions()
        q12 = next(q for q in qs if q.id == "1.2")
        req = UserRequirements(use_case="chat")
        assert q12.skip_if(req) is True

    def test_file_upload_skipped_for_code(self):
        """Q1.2 (file upload) should be skipped when use_case is code."""
        qs = _build_questions()
        q12 = next(q for q in qs if q.id == "1.2")
        req = UserRequirements(use_case="code")
        assert q12.skip_if(req) is True

    def test_file_upload_not_skipped_for_data(self):
        """Q1.2 (file upload) should NOT be skipped for data use case."""
        qs = _build_questions()
        q12 = next(q for q in qs if q.id == "1.2")
        req = UserRequirements(use_case="data")
        assert q12.skip_if(req) is False

    def test_file_upload_skipped_when_already_set(self):
        """Q1.2 skipped when needs_file_upload is already True."""
        qs = _build_questions()
        q12 = next(q for q in qs if q.id == "1.2")
        req = UserRequirements(use_case="data", needs_file_upload=True)
        assert q12.skip_if(req) is True

    def test_thinking_skipped_when_already_set(self):
        """Q2.1 (thinking) should be skipped when already set to True."""
        qs = _build_questions()
        q21 = next(q for q in qs if q.id == "2.1")
        req = UserRequirements(needs_thinking=True)
        assert q21.skip_if(req) is True

    def test_thinking_not_skipped_when_unset(self):
        """Q2.1 (thinking) should NOT be skipped when needs_thinking is default."""
        qs = _build_questions()
        q21 = next(q for q in qs if q.id == "2.1")
        req = UserRequirements()
        assert q21.skip_if(req) is False

    def test_streaming_skipped_for_browser_providers(self):
        """Q2.3 (streaming) skipped for browser-only providers."""
        qs = _build_questions()
        q23 = next(q for q in qs if q.id == "2.3")
        for provider in ("claude", "gemini", "gpt", "perplexity"):
            req = UserRequirements(provider_preference=provider)
            assert q23.skip_if(req) is True, f"Should skip streaming for {provider}"

    def test_streaming_not_skipped_for_api_providers(self):
        """Q2.3 (streaming) NOT skipped for API providers."""
        qs = _build_questions()
        q23 = next(q for q in qs if q.id == "2.3")
        req = UserRequirements(provider_preference="openai")
        assert q23.skip_if(req) is False

    def test_fallback_skipped_for_browser_providers(self):
        """Q4.1 (fallback) skipped for browser providers."""
        qs = _build_questions()
        q41 = next(q for q in qs if q.id == "4.1")
        for provider in ("claude", "gemini", "gpt", "perplexity"):
            req = UserRequirements(provider_preference=provider)
            assert q41.skip_if(req) is True

    def test_fallback_not_skipped_for_openrouter(self):
        """Q4.1 (fallback) NOT skipped for openrouter."""
        qs = _build_questions()
        q41 = next(q for q in qs if q.id == "4.1")
        req = UserRequirements(provider_preference="openrouter")
        assert q41.skip_if(req) is False

    def test_model_preference_skipped_when_set(self):
        """Q3.4 (model) skipped when already set."""
        qs = _build_questions()
        q34 = next(q for q in qs if q.id == "3.4")
        req = UserRequirements(model_preference="gpt-4")
        assert q34.skip_if(req) is True

    def test_model_preference_not_skipped_when_none(self):
        """Q3.4 (model) not skipped when model_preference is None."""
        qs = _build_questions()
        q34 = next(q for q in qs if q.id == "3.4")
        req = UserRequirements()
        assert q34.skip_if(req) is False


class TestQuestionValueMaps:
    """Verify option→value mappings are consistent."""

    def test_use_case_values(self):
        qs = _build_questions()
        q = next(q for q in qs if q.id == "1.1")
        assert q.value_map[1] == "chat"
        assert q.value_map[3] == "translation"
        assert q.value_map[6] == "__custom__"

    def test_provider_values(self):
        qs = _build_questions()
        q = next(q for q in qs if q.id == "3.2")
        assert q.value_map[1] == "claude"
        assert q.value_map[4] == "openrouter"
        assert q.value_map[8] is None  # no preference

    def test_output_format_values(self):
        qs = _build_questions()
        q = next(q for q in qs if q.id == "5.2")
        assert q.value_map[1] == "instance"
        assert q.value_map[2] == "script"
        assert q.value_map[3] == "config_only"


class TestInteractiveTranslation:
    """Test the translation use case through the interview."""

    def test_translation_flow(self):
        answers = [
            "1",  # 0.1: keep compiler-LLM
            "3",  # 1.1: translation → apply_use_case_defaults sets needs_file_upload
            # 1.2 skipped (needs_file_upload already True from defaults)
            "1",  # 2.1: yes thinking
            "3",  # 2.2: quality
            "2",  # 2.3: no streaming (not skipped — provider not set yet)
            "4",  # 3.1: unlimited
            "2",  # 3.2: gemini
            "1",  # 3.3 auth confirm (before 3.4)
            "1",  # 3.4: default model
            # 4.1 skipped (gemini = browser)
            "2",  # 4.2: no monitoring
            "1",  # 5.1: default prompt
            "1",  # 5.2: instance
        ]
        flow, _ = _make_flow(
            answers,
            auth={"gemini_storage_state": True, "openai_key": True},
        )
        req = flow.interview()

        assert req.use_case == "translation"
        assert req.needs_translation is True  # from apply_use_case_defaults
        assert req.needs_file_upload is True
        assert req.provider_preference == "gemini"
        assert req.latency_sensitivity == "quality"
