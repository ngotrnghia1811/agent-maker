"""Tests for AgentPackager — self-contained agent packaging."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from universal_agents.compiler.agent_assembler import CompiledAgent
from universal_agents.compiler.agent_packager import AgentPackager
from universal_agents.compiler.capability_resolver import ResolvedComponents
from universal_agents.compiler.requirements import UserRequirements


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture
def components() -> ResolvedComponents:
    return ResolvedComponents(
        provider="gemini",
        transport="browser",
        agent_class_name="GeminiChatAgent",
        config_class_name="GeminiChatConfig",
        agent_module="universal_agents.providers.gemini.chat",
        config_module="universal_agents.providers.gemini.config",
        capabilities=["chat", "file_upload"],
    )


@pytest.fixture
def compiled(components) -> CompiledAgent:
    return CompiledAgent(
        provider="gemini",
        agent_class_name="GeminiChatAgent",
        config_class_name="GeminiChatConfig",
        config_kwargs={"visible": True, "timeout": 60000},
        capabilities=["chat", "file_upload"],
        script="# placeholder script",
    )


@pytest.fixture
def req() -> UserRequirements:
    return UserRequirements(
        use_case="chat",
        output_format="package",
    )


@pytest.fixture
def packager() -> AgentPackager:
    return AgentPackager()


# ======================================================================
# Package creation
# ======================================================================

class TestPackageCreation:
    def test_creates_package_directory(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            assert pkg_dir.exists()
            assert pkg_dir.name == "test_pkg"

    def test_creates_all_expected_files(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            assert (pkg_dir / "agent.py").exists()
            assert (pkg_dir / "config.json").exists()
            assert (pkg_dir / "requirements.txt").exists()
            assert (pkg_dir / "README.md").exists()
            assert (pkg_dir / "source_spec.json").exists()
            assert (pkg_dir / "storage").is_dir()

    def test_auto_generates_name(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir))
            assert pkg_dir.name.startswith("gemini_geminichatagent_")


# ======================================================================
# config.json
# ======================================================================

class TestConfigJson:
    def test_config_has_required_keys(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            config = json.loads((pkg_dir / "config.json").read_text())
            assert config["provider"] == "gemini"
            assert config["agent_class"] == "GeminiChatAgent"
            assert config["config_class"] == "GeminiChatConfig"
            assert config["config_kwargs"]["visible"] is True
            assert config["config_kwargs"]["timeout"] == 60000

    def test_config_has_metadata(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            config = json.loads((pkg_dir / "config.json").read_text())
            meta = config["_metadata"]
            assert meta["transport"] == "browser"
            assert "agent_module" in meta
            assert "created" in meta


# ======================================================================
# agent.py
# ======================================================================

class TestAgentScript:
    def test_script_is_executable(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            agent_path = pkg_dir / "agent.py"
            assert os.access(agent_path, os.X_OK)

    def test_script_reads_config(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            script = (pkg_dir / "agent.py").read_text()
            assert "config.json" in script
            assert "json.load" in script

    def test_script_imports_agent(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            script = (pkg_dir / "agent.py").read_text()
            assert "GeminiChatAgent" in script
            assert "GeminiChatConfig" in script

    def test_script_has_main_block(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            script = (pkg_dir / "agent.py").read_text()
            assert 'if __name__ == "__main__"' in script


# ======================================================================
# requirements.txt
# ======================================================================

class TestRequirements:
    def test_has_playwright(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            reqs = (pkg_dir / "requirements.txt").read_text()
            assert "playwright" in reqs

    def test_gemini_browser_has_camoufox(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            reqs = (pkg_dir / "requirements.txt").read_text()
            assert "camoufox" in reqs


# ======================================================================
# source_spec.json
# ======================================================================

class TestSourceSpec:
    def test_spec_round_trips(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            spec = json.loads((pkg_dir / "source_spec.json").read_text())
            assert spec["use_case"] == "chat"
            assert spec["output_format"] == "package"

    def test_spec_has_compiled_info(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            spec = json.loads((pkg_dir / "source_spec.json").read_text())
            assert spec["_compiled"]["provider"] == "gemini"
            assert spec["_compiled"]["transport"] == "browser"


# ======================================================================
# README.md
# ======================================================================

class TestReadme:
    def test_readme_has_quickstart(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            readme = (pkg_dir / "README.md").read_text()
            assert "python agent.py" in readme
            assert "pip install" in readme

    def test_readme_mentions_provider(self, packager, compiled, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "test_pkg")
            readme = (pkg_dir / "README.md").read_text()
            assert "gemini" in readme.lower()


# ======================================================================
# Storage state copying
# ======================================================================

class TestStorageCopy:
    def test_copies_storage_state_file(self, packager, components, req):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake storage state file
            state_file = Path(tmpdir) / "gemini_state.json"
            state_file.write_text('{"cookies": []}')

            compiled = CompiledAgent(
                provider="gemini",
                agent_class_name="GeminiChatAgent",
                config_class_name="GeminiChatConfig",
                config_kwargs={"storage_state": str(state_file)},
                capabilities=["chat"],
            )

            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "pkg")
            copied = pkg_dir / "storage" / "gemini_state.json"
            assert copied.exists()
            assert json.loads(copied.read_text()) == {"cookies": []}

    def test_ignores_missing_storage_state(self, packager, compiled, components, req):
        compiled.config_kwargs["storage_state"] = "/nonexistent/state.json"
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "pkg")
            # No crash, storage dir still created
            assert (pkg_dir / "storage").is_dir()


# ======================================================================
# Use-case-specific scripts
# ======================================================================

class TestUseCaseScripts:
    def test_chat_script(self, packager, compiled, components):
        req = UserRequirements(use_case="chat", output_format="package")
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "pkg")
            script = (pkg_dir / "agent.py").read_text()
            assert "agent.chat" in script

    def test_translation_script(self, packager, compiled, components):
        req = UserRequirements(use_case="translation", output_format="package")
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "pkg")
            script = (pkg_dir / "agent.py").read_text()
            assert "translate" in script.lower()

    def test_data_script(self, packager, compiled, components):
        req = UserRequirements(use_case="data", output_format="package")
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = packager.package(compiled, components, req, Path(tmpdir), "pkg")
            script = (pkg_dir / "agent.py").read_text()
            assert "agent.chat" in script


# ======================================================================
# Integration: assembler → packager pipeline
# ======================================================================

class TestAssemblerPackagePipeline:
    def test_assembler_package_format(self):
        """Verify the assembler.assemble() creates a package when format='package'."""
        from universal_agents.compiler.agent_assembler import AgentAssembler

        req = UserRequirements(
            use_case="chat",
            output_format="package",
            cost_sensitivity="free",
            provider_preference="gemini",
        )
        components = ResolvedComponents(
            provider="gemini",
            transport="browser",
            agent_class_name="GeminiChatAgent",
            config_class_name="GeminiChatConfig",
            agent_module="universal_agents.providers.gemini.chat",
            config_module="universal_agents.providers.gemini.config",
            capabilities=["chat"],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            req.package_dir = tmpdir
            req.package_name = "integration_test"
            assembler = AgentAssembler()
            compiled = assembler.assemble(components, req)

            assert compiled.package_dir is not None
            pkg_path = Path(compiled.package_dir)
            assert pkg_path.exists()
            assert (pkg_path / "agent.py").exists()
            assert (pkg_path / "config.json").exists()
            assert (pkg_path / "source_spec.json").exists()
