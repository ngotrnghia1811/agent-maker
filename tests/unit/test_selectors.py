"""Unit tests for browser/selectors.py."""

from universal_agents.browser.selectors import ProviderSelectors


class TestProviderSelectors:
    def test_frozen(self):
        s = ProviderSelectors(
            input=["div.ProseMirror"],
            submit=["button[type='submit']"],
            response=[".markdown"],
        )
        assert s.input == ["div.ProseMirror"]
        assert s.loading == []
        assert s.new_chat == []

    def test_with_optional_fields(self):
        s = ProviderSelectors(
            input=["textarea"],
            submit=["button"],
            response=[".response"],
            loading=[".spinner"],
            new_chat=["a.new"],
        )
        assert s.loading == [".spinner"]
        assert s.new_chat == ["a.new"]
