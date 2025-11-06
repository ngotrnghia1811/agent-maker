"""Unit tests for Perplexity citation parsing."""

import pytest

from universal_agents.providers.pplx.chat import Citation, PerplexityChatAgent
from universal_agents.providers.pplx.config import PerplexityConfig
from universal_agents.providers.pplx.selectors import PPLX_SELECTORS


class TestPerplexityConfig:
    def test_defaults(self):
        config = PerplexityConfig()
        assert config.provider_name == "perplexity"
        assert config.base_url == "https://www.perplexity.ai"
        assert config.extract_citations is True


class TestPerplexitySelectors:
    def test_has_required_selectors(self):
        assert len(PPLX_SELECTORS.input) > 0
        assert len(PPLX_SELECTORS.submit) > 0
        assert len(PPLX_SELECTORS.response) > 0


class TestCitationParsing:
    def test_is_citation_text_url(self):
        assert PerplexityChatAgent._is_citation_text("https://example.com")

    def test_is_citation_text_numbered(self):
        assert PerplexityChatAgent._is_citation_text("1. Some reference")

    def test_is_citation_text_bracketed(self):
        assert PerplexityChatAgent._is_citation_text("[1] A source")

    def test_is_citation_text_domain(self):
        assert PerplexityChatAgent._is_citation_text("See example.com for details")

    def test_is_citation_text_plain(self):
        assert not PerplexityChatAgent._is_citation_text("Just a normal sentence")

    def test_parse_citation_with_url(self):
        c = PerplexityChatAgent._parse_citation('Check https://arxiv.org/abs/1234 for details')
        assert c.url == "https://arxiv.org/abs/1234"
        assert c.citation_type == "academic"

    def test_parse_citation_with_title(self):
        c = PerplexityChatAgent._parse_citation('"Quantum Computing Review" by Smith')
        assert c.title == "Quantum Computing Review"

    def test_parse_citation_with_year(self):
        c = PerplexityChatAgent._parse_citation("Published in 2023")
        assert c.year == 2023

    def test_parse_citation_wikipedia(self):
        c = PerplexityChatAgent._parse_citation("https://en.wikipedia.org/wiki/Test")
        assert c.citation_type == "wiki"

    def test_parse_citation_web(self):
        c = PerplexityChatAgent._parse_citation("https://example.com/page")
        assert c.citation_type == "web"

    def test_parse_citation_unknown(self):
        c = PerplexityChatAgent._parse_citation("Some text without URL")
        assert c.citation_type == "unknown"


class TestCitationDataclass:
    def test_defaults(self):
        c = Citation(text="test")
        assert c.url is None
        assert c.title is None
        assert c.year is None
        assert c.citation_type == "unknown"
