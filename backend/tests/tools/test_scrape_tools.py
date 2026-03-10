"""Tests for web scraping tools (ScrapeWebsiteInfinibayTool, SpiderScrapeTool)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.tools.web.scrape_website import ScrapeWebsiteInfinibayTool
from backend.tools.web.spider_scrape import SpiderScrapeTool


class TestScrapeWebsiteTool:
    @patch("backend.tools.web.scrape_website.scrape_with_crewai")
    @patch("backend.tools.web.scrape_website.web_rate_limiter")
    @patch("backend.tools.web.scrape_website.robots_checker")
    def test_scrape_website_returns_content(self, mock_robots, mock_limiter, mock_scrape, agent_context):
        mock_robots.is_allowed.return_value = True
        mock_scrape.return_value = "Scraped page content here"

        tool = ScrapeWebsiteInfinibayTool()
        result = json.loads(tool._run(url="https://example.com"))

        assert result["content"] == "Scraped page content here"
        assert result["url"] == "https://example.com"
        mock_scrape.assert_called_once_with("https://example.com")

    @patch("backend.tools.web.scrape_website.robots_checker")
    def test_scrape_website_respects_robots(self, mock_robots, agent_context):
        mock_robots.is_allowed.return_value = False

        tool = ScrapeWebsiteInfinibayTool()
        result = json.loads(tool._run(url="https://blocked.com"))

        assert "error" in result
        assert "robots.txt" in result["error"]

    @patch("backend.tools.web.scrape_website.store_scraped_content_as_finding")
    @patch("backend.tools.web.scrape_website.scrape_with_crewai")
    @patch("backend.tools.web.scrape_website.web_rate_limiter")
    @patch("backend.tools.web.scrape_website.robots_checker")
    def test_scrape_website_stores_as_finding(
        self, mock_robots, mock_limiter, mock_scrape, mock_store, agent_context
    ):
        mock_robots.is_allowed.return_value = True
        mock_scrape.return_value = "Content to store"
        mock_store.return_value = 42  # finding ID

        tool = ScrapeWebsiteInfinibayTool()
        result = json.loads(tool._run(
            url="https://example.com",
            store_as_finding=True,
            topic="Test topic",
        ))

        assert result["stored_as_finding_id"] == 42
        mock_store.assert_called_once()

    @patch("backend.tools.web.scrape_website.scrape_with_crewai")
    @patch("backend.tools.web.scrape_website.web_rate_limiter")
    @patch("backend.tools.web.scrape_website.robots_checker")
    def test_scrape_website_handles_failure(self, mock_robots, mock_limiter, mock_scrape, agent_context):
        mock_robots.is_allowed.return_value = True
        mock_scrape.return_value = None  # scrape failed

        tool = ScrapeWebsiteInfinibayTool()
        result = json.loads(tool._run(url="https://example.com"))

        assert "error" in result
        assert "Failed to scrape" in result["error"]


class TestSpiderScrapeTool:
    @patch("backend.tools.web.spider_scrape.settings")
    def test_spider_requires_api_key(self, mock_settings, agent_context):
        mock_settings.SPIDER_API_KEY = ""

        tool = SpiderScrapeTool()
        result = json.loads(tool._run(url="https://example.com"))

        assert "error" in result
        assert "SPIDER_API_KEY" in result["error"]

    @patch("backend.tools.web.spider_scrape.web_rate_limiter")
    @patch("backend.tools.web.spider_scrape.settings")
    def test_spider_scrape_delegates_to_crewai(self, mock_settings, mock_limiter, agent_context):
        mock_settings.SPIDER_API_KEY = "test-key"

        mock_tool_instance = MagicMock()
        mock_tool_instance.run.return_value = "Spider scraped content"

        with patch("backend.tools.web.spider_scrape.SpiderTool", return_value=mock_tool_instance):
            tool = SpiderScrapeTool()
            result = json.loads(tool._run(url="https://js-heavy-site.com"))

        assert result["content"] == "Spider scraped content"
        assert result["url"] == "https://js-heavy-site.com"

    @patch("backend.tools.web.spider_scrape.web_rate_limiter")
    @patch("backend.tools.web.spider_scrape.settings")
    def test_spider_handles_import_error(self, mock_settings, mock_limiter, agent_context):
        mock_settings.SPIDER_API_KEY = "test-key"

        with patch.dict("sys.modules", {"crewai_tools": None}):
            tool = SpiderScrapeTool()
            result = json.loads(tool._run(url="https://example.com"))

            assert "error" in result
