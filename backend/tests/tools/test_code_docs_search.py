"""Tests for CodeDocsSearchPabadaTool."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.tools.web.code_docs_search import CodeDocsSearchPabadaTool


class TestCodeDocsSearchTool:
    @patch("backend.tools.web.code_docs_search.build_crewai_tools_config")
    def test_code_docs_search_with_url(self, mock_config, agent_context):
        mock_config.return_value = {"embedder": {"provider": "openai", "config": {"model": "test"}}}

        mock_tool = MagicMock()
        mock_tool.run.return_value = "React hooks documentation: useState allows..."

        with patch("backend.tools.web.code_docs_search.CodeDocsSearchTool", return_value=mock_tool):
            tool = CodeDocsSearchPabadaTool()
            result = json.loads(tool._run(
                query="useState hook",
                docs_url="https://react.dev/reference",
            ))

        assert result["query"] == "useState hook"
        assert result["docs_url"] == "https://react.dev/reference"
        assert "React hooks" in result["result"]

    @patch("backend.tools.web.code_docs_search.build_crewai_tools_config")
    def test_code_docs_search_without_url(self, mock_config, agent_context):
        mock_config.return_value = {"embedder": {"provider": "openai", "config": {"model": "test"}}}

        mock_tool = MagicMock()
        mock_tool.run.return_value = "Some docs result"

        with patch("backend.tools.web.code_docs_search.CodeDocsSearchTool", return_value=mock_tool):
            tool = CodeDocsSearchPabadaTool()
            result = json.loads(tool._run(query="fastapi middleware"))

        assert result["query"] == "fastapi middleware"
        assert result["docs_url"] == ""

    def test_code_docs_search_handles_import_error(self, agent_context):
        with patch.dict("sys.modules", {"crewai_tools": None}):
            tool = CodeDocsSearchPabadaTool()
            result = json.loads(tool._run(query="test"))

            assert "error" in result

    @patch("backend.tools.web.code_docs_search.build_crewai_tools_config")
    def test_code_docs_search_config_mapping(self, mock_config, agent_context):
        """Verify that build_crewai_tools_config is called."""
        mock_config.return_value = {"embedder": {"provider": "ollama", "config": {"model": "nomic"}}}

        mock_tool = MagicMock()
        mock_tool.run.return_value = "result"

        with patch("backend.tools.web.code_docs_search.CodeDocsSearchTool", return_value=mock_tool) as mock_cls:
            tool = CodeDocsSearchPabadaTool()
            tool._run(query="test query", docs_url="https://docs.example.com")

        mock_config.assert_called_once()
        # Verify config was passed to the tool
        call_kwargs = mock_cls.call_args[1]
        assert "config" in call_kwargs
        assert call_kwargs["config"]["embedder"]["provider"] == "ollama"
