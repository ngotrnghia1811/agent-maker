"""Unit tests for Copilot CLI agent."""

import pytest

from universal_agents.providers.copilot.chat import CopilotChatAgent
from universal_agents.providers.copilot.config import CopilotConfig


class TestCopilotConfig:
    def test_defaults(self):
        config = CopilotConfig()
        assert config.provider_name == "copilot"
        assert config.command == "copilot"
        assert config.max_history_turns == 10
        assert config.allow_all_tools is False
        assert config.allowed_tools == []
        assert config.denied_tools == []


class TestCopilotChatAgent:
    def test_build_command_default(self):
        agent = CopilotChatAgent()
        cmd = agent._build_command()
        assert cmd == ["copilot", "-I"]

    def test_build_command_allow_all(self):
        config = CopilotConfig(allow_all_tools=True)
        agent = CopilotChatAgent(config)
        cmd = agent._build_command()
        assert "--allow-all-tools" in cmd

    def test_build_prompt_with_system(self):
        config = CopilotConfig(system_prompt="Be concise")
        agent = CopilotChatAgent(config)
        prompt = agent._build_prompt("hello")
        assert "[System Instructions]: Be concise" in prompt
        assert "[Current Query]: hello" in prompt

    def test_build_prompt_no_system(self):
        config = CopilotConfig(system_prompt="")
        agent = CopilotChatAgent(config)
        prompt = agent._build_prompt("hello")
        assert "[System Instructions]" not in prompt
        assert "[Current Query]: hello" in prompt
