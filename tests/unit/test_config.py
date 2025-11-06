"""Unit tests for core/config.py."""

from universal_agents.core.config import APIConfig, BaseConfig, BrowserConfig, CLIConfig


class TestBaseConfig:
    def test_defaults(self):
        cfg = BaseConfig()
        assert cfg.provider_name == ""
        assert cfg.max_history_turns == 50
        assert cfg.max_retries == 3
        assert cfg.retry_delay == 2.0
        assert cfg.timeout == 180

    def test_custom_values(self):
        cfg = BaseConfig(provider_name="test", timeout=60)
        assert cfg.provider_name == "test"
        assert cfg.timeout == 60


class TestBrowserConfig:
    def test_inherits_base(self):
        cfg = BrowserConfig(provider_name="claude", base_url="https://claude.ai")
        assert cfg.max_retries == 3  # from BaseConfig
        assert cfg.headless is True
        assert cfg.viewport_width == 1920
        assert cfg.required_stable_checks == 3

    def test_storage_state(self):
        cfg = BrowserConfig(storage_state="/tmp/state.json")
        assert cfg.storage_state == "/tmp/state.json"


class TestAPIConfig:
    def test_defaults(self):
        cfg = APIConfig()
        assert cfg.temperature == 0.7
        assert cfg.max_tokens == 4096
        assert cfg.stream is False

    def test_api_key_not_in_repr(self):
        cfg = APIConfig(api_key="secret")
        assert "secret" not in repr(cfg)


class TestCLIConfig:
    def test_defaults(self):
        cfg = CLIConfig(command="copilot")
        assert cfg.command == "copilot"
        assert cfg.working_dir == ""


class TestConfigSerialization:
    """Tests for to_dict() / from_dict() on all config types."""

    def test_base_config_round_trip(self):
        cfg = BaseConfig(provider_name="test", timeout=60)
        d = cfg.to_dict()
        assert d["provider_name"] == "test"
        assert d["timeout"] == 60
        restored = BaseConfig.from_dict(d)
        assert restored == cfg

    def test_browser_config_round_trip(self):
        cfg = BrowserConfig(
            provider_name="claude",
            base_url="https://claude.ai",
            headless=False,
            viewport_width=1280,
        )
        d = cfg.to_dict()
        assert d["headless"] is False
        restored = BrowserConfig.from_dict(d)
        assert restored == cfg

    def test_api_config_round_trip(self):
        cfg = APIConfig(
            api_key="sk-test",
            model="gpt-4",
            temperature=0.5,
            stream=True,
        )
        d = cfg.to_dict()
        assert d["model"] == "gpt-4"
        assert d["api_key"] == "sk-test"
        restored = APIConfig.from_dict(d)
        assert restored == cfg

    def test_cli_config_round_trip(self):
        cfg = CLIConfig(command="copilot", timeout=30)
        d = cfg.to_dict()
        restored = CLIConfig.from_dict(d)
        assert restored == cfg

    def test_from_dict_ignores_unknown_keys(self):
        d = {"provider_name": "test", "unknown_field": 42, "bogus": "val"}
        cfg = BaseConfig.from_dict(d)
        assert cfg.provider_name == "test"
        assert not hasattr(cfg, "unknown_field")

    def test_provider_config_round_trip(self):
        """Test that provider-specific configs serialize correctly."""
        from universal_agents.providers.claude.config import ClaudeConfig
        cfg = ClaudeConfig(extract_thinking=False)
        d = cfg.to_dict()
        assert d["extract_thinking"] is False
        assert d["provider_name"] == "claude"
        restored = ClaudeConfig.from_dict(d)
        assert restored == cfg

    def test_openrouter_config_round_trip(self):
        from universal_agents.providers.openrouter.config import OpenRouterConfig
        cfg = OpenRouterConfig(api_key="sk-test", model="gpt-4")
        d = cfg.to_dict()
        assert d["model"] == "gpt-4"
        restored = OpenRouterConfig.from_dict(d)
        assert restored == cfg

    def test_openai_data_config_round_trip(self):
        from universal_agents.providers.openai.config import OpenAIDataConfig
        cfg = OpenAIDataConfig(
            api_key="sk-test",
            reasoning_effort="medium",
            max_completion_tokens=8192,
        )
        d = cfg.to_dict()
        assert d["reasoning_effort"] == "medium"
        restored = OpenAIDataConfig.from_dict(d)
        assert restored == cfg
