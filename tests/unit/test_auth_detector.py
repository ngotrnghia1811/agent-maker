"""Unit tests for the AuthDetector."""

import json
import os
import pytest
from pathlib import Path

from universal_agents.compiler.auth_detector import AuthDetector, AuthStatus


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory with storage/ and .env."""
    storage = tmp_path / "storage"
    storage.mkdir()
    env_file = tmp_path / ".env"
    return tmp_path, storage, env_file


class TestAuthStatus:
    def test_has_true(self):
        status = AuthStatus(available={"openai_key": True})
        assert status.has("openai_key") is True

    def test_has_false(self):
        status = AuthStatus(available={"openai_key": False})
        assert status.has("openai_key") is False

    def test_has_missing(self):
        status = AuthStatus()
        assert status.has("nonexistent") is False

    def test_summary_lines(self):
        status = AuthStatus(
            available={"openai_key": True, "claude_storage": False},
            details={"openai_key": "sk-hq...1234"},
        )
        lines = status.summary_lines()
        assert len(lines) == 2
        assert "found" in lines[0]


class TestAuthDetector:
    def test_detects_api_key_from_env(self, tmp_project, monkeypatch):
        root, storage, env_file = tmp_project
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-1234567890")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test-key-abc")

        detector = AuthDetector(project_root=root)
        status = detector.detect()

        assert status.has("openai_key") is True
        assert status.has("openrouter_key") is True
        # Masking: first 8 + last 4 chars for keys > 16 chars
        assert "sk-test-" in status.details["openai_key"]
        assert "7890" in status.details["openai_key"]

    def test_no_api_key(self, tmp_project, monkeypatch):
        root, storage, env_file = tmp_project
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        detector = AuthDetector(project_root=root)
        status = detector.detect()

        assert status.has("openai_key") is False
        assert status.has("openrouter_key") is False

    def test_detects_storage_state_file(self, tmp_project, monkeypatch):
        root, storage, env_file = tmp_project
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        # Create a valid Playwright storage state
        state = {"cookies": [{"name": "sess", "value": "abc"}], "origins": []}
        (storage / "claude_storage_state.json").write_text(json.dumps(state))

        detector = AuthDetector(project_root=root)
        status = detector.detect()

        assert status.has("claude_storage") is True

    def test_invalid_storage_state(self, tmp_project, monkeypatch):
        root, storage, env_file = tmp_project
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        # Empty cookies and origins — invalid
        (storage / "claude_storage_state.json").write_text(
            json.dumps({"cookies": [], "origins": []})
        )

        detector = AuthDetector(project_root=root)
        status = detector.detect()

        assert status.has("claude_storage") is False

    def test_malformed_json_storage(self, tmp_project, monkeypatch):
        root, storage, env_file = tmp_project
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        (storage / "gemini_storage_state.json").write_text("not json at all")

        detector = AuthDetector(project_root=root)
        status = detector.detect()

        assert status.has("gemini_storage") is False

    def test_loads_dotenv_file(self, tmp_project, monkeypatch):
        root, storage, env_file = tmp_project
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        env_file.write_text("OPENAI_API_KEY=sk-from-dotenv-file-12345\n")

        detector = AuthDetector(project_root=root)
        status = detector.detect()

        assert status.has("openai_key") is True

    def test_env_var_overrides_dotenv(self, tmp_project, monkeypatch):
        root, storage, env_file = tmp_project
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        env_file.write_text("OPENAI_API_KEY=sk-from-file\n")

        detector = AuthDetector(project_root=root)
        status = detector.detect()

        # Env var wins — dotenv uses override=False
        assert status.has("openai_key") is True
        # Short key (<=16 chars) is fully masked as ***
        assert status.details["openai_key"] == "***"

    def test_missing_storage_dir(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        detector = AuthDetector(
            project_root=tmp_path,
            storage_dir=tmp_path / "nonexistent",
        )
        status = detector.detect()

        # Should not crash, just report nothing found
        assert status.has("claude_storage") is False

    def test_custom_storage_state_via_env(self, tmp_project, monkeypatch):
        root, storage, env_file = tmp_project
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        custom_path = root / "custom_claude_state.json"
        state = {"cookies": [{"name": "auth", "value": "xyz"}], "origins": []}
        custom_path.write_text(json.dumps(state))
        monkeypatch.setenv("CLAUDE_STORAGE_STATE", str(custom_path))

        detector = AuthDetector(project_root=root)
        status = detector.detect()

        assert status.has("claude_storage") is True

    def test_dotenv_with_comments_and_blanks(self, tmp_project, monkeypatch):
        root, storage, env_file = tmp_project
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        env_file.write_text(
            "# Comment line\n"
            "\n"
            "OPENROUTER_API_KEY='sk-or-v1-from-dotenv-quoted'\n"
            "SOME_OTHER_VAR=ignored\n"
        )

        detector = AuthDetector(project_root=root)
        status = detector.detect()

        assert status.has("openrouter_key") is True

    def test_validate_storage_state_with_origins(self, tmp_project):
        root, storage, _ = tmp_project
        state = {"cookies": [], "origins": [{"origin": "https://claude.ai", "localStorage": []}]}
        path = storage / "test_state.json"
        path.write_text(json.dumps(state))

        assert AuthDetector._validate_storage_state(path) is True
