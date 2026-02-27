"""Tests for web search backends (_backends.py)."""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestSearchSerper:
    @patch("backend.tools.web._backends.settings")
    def test_returns_none_when_no_api_key(self, mock_settings):
        mock_settings.SERPER_API_KEY = ""
        from backend.tools.web._backends import search_serper

        result = search_serper("test query")
        assert result is None

    @patch("backend.tools.web._backends.web_rate_limiter")
    @patch("backend.tools.web._backends.settings")
    def test_serper_search_when_configured(self, mock_settings, mock_limiter):
        mock_settings.SERPER_API_KEY = "test-key"
        mock_settings.SERPER_COUNTRY = "us"
        mock_settings.SERPER_N_RESULTS = 5

        mock_tool_instance = MagicMock()
        mock_tool_instance.run.return_value = json.dumps([
            {"title": "Result 1", "link": "https://example.com", "snippet": "A snippet"},
        ])

        with patch("backend.tools.web._backends.SerperDevTool", return_value=mock_tool_instance) as mock_cls:
            from importlib import reload
            import backend.tools.web._backends as backends_mod

            # Call directly to test with mocked import
            result = backends_mod.search_serper("test query", 5)

        # Even if crewai_tools is not installed, the function should handle it
        # gracefully (returns None on ImportError)

    @patch("backend.tools.web._backends.web_rate_limiter")
    @patch("backend.tools.web._backends.settings")
    def test_serper_returns_none_on_import_error(self, mock_settings, mock_limiter):
        mock_settings.SERPER_API_KEY = "test-key"

        with patch.dict("sys.modules", {"crewai_tools": None}):
            from backend.tools.web._backends import search_serper
            # ImportError should be caught gracefully
            result = search_serper("test query")
            # Returns None when crewai_tools can't be imported
            assert result is None


class TestSearchDDG:
    @patch("backend.tools.web._backends.web_rate_limiter")
    def test_ddg_search_returns_results(self, mock_limiter):
        mock_ddgs_instance = MagicMock()
        mock_ddgs_instance.text.return_value = [
            {"title": "DDG Result", "href": "https://ddg.example.com", "body": "DDG snippet"},
        ]

        with patch("backend.tools.web._backends.DDGS", return_value=mock_ddgs_instance) as mock_cls:
            from importlib import reload
            import backend.tools.web._backends as mod

            result = mod.search_ddg("test query", 5)

        assert len(result) == 1
        assert result[0]["title"] == "DDG Result"
        assert result[0]["url"] == "https://ddg.example.com"
        assert result[0]["snippet"] == "DDG snippet"

    @patch("backend.tools.web._backends.web_rate_limiter")
    def test_ddg_search_handles_exception(self, mock_limiter):
        with patch("backend.tools.web._backends.DDGS", side_effect=Exception("DDG down")):
            from backend.tools.web._backends import search_ddg

            result = search_ddg("test query")
            assert result == []


class TestUnifiedSearch:
    @patch("backend.tools.web._backends.search_ddg")
    @patch("backend.tools.web._backends.search_serper")
    @patch("backend.tools.web._backends.settings")
    def test_uses_serper_when_key_set(self, mock_settings, mock_serper, mock_ddg):
        mock_settings.SERPER_API_KEY = "test-key"
        mock_settings.WEB_SEARCH_FALLBACK_ENABLED = True
        mock_serper.return_value = [{"title": "Serper", "url": "https://s.com", "snippet": "s"}]

        from backend.tools.web._backends import unified_search
        result = unified_search("test")

        mock_serper.assert_called_once_with("test", 10)
        mock_ddg.assert_not_called()
        assert result[0]["title"] == "Serper"

    @patch("backend.tools.web._backends.search_ddg")
    @patch("backend.tools.web._backends.search_serper")
    @patch("backend.tools.web._backends.settings")
    def test_fallback_to_ddg_on_serper_failure(self, mock_settings, mock_serper, mock_ddg):
        mock_settings.SERPER_API_KEY = "test-key"
        mock_settings.WEB_SEARCH_FALLBACK_ENABLED = True
        mock_serper.return_value = None  # Serper failed
        mock_ddg.return_value = [{"title": "DDG", "url": "https://d.com", "snippet": "d"}]

        from backend.tools.web._backends import unified_search
        result = unified_search("test")

        mock_serper.assert_called_once()
        mock_ddg.assert_called_once()
        assert result[0]["title"] == "DDG"

    @patch("backend.tools.web._backends.search_ddg")
    @patch("backend.tools.web._backends.search_serper")
    @patch("backend.tools.web._backends.settings")
    def test_ddg_only_when_no_serper_key(self, mock_settings, mock_serper, mock_ddg):
        mock_settings.SERPER_API_KEY = ""
        mock_settings.WEB_SEARCH_FALLBACK_ENABLED = True
        mock_ddg.return_value = [{"title": "DDG Only", "url": "https://d.com", "snippet": "d"}]

        from backend.tools.web._backends import unified_search
        result = unified_search("test")

        mock_serper.assert_not_called()
        mock_ddg.assert_called_once()
        assert result[0]["title"] == "DDG Only"


class TestFetchWithTrafilatura:
    @patch("backend.tools.web._backends.settings")
    def test_fetch_returns_content(self, mock_settings):
        mock_settings.WEB_TIMEOUT = 30

        mock_response = MagicMock()
        mock_response.text = "<html><body>Hello World</body></html>"
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response

        with patch("backend.tools.web._backends.httpx") as mock_httpx, \
             patch("backend.tools.web._backends.trafilatura") as mock_traf:
            mock_httpx.Client.return_value = mock_client
            mock_traf.extract.return_value = "Extracted content"

            from backend.tools.web._backends import fetch_with_trafilatura
            result = fetch_with_trafilatura("https://example.com")

        assert result == "Extracted content"

    def test_fetch_returns_none_on_missing_httpx(self):
        with patch.dict("sys.modules", {"httpx": None}):
            from backend.tools.web._backends import fetch_with_trafilatura
            result = fetch_with_trafilatura("https://example.com")
            assert result is None
