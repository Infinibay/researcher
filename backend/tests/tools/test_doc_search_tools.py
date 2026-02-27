"""Tests for document search tools (DOCX, JSON, XML)."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from backend.tools.rag.docx_search import DOCXSearchPabadaTool
from backend.tools.rag.json_search import JSONSearchPabadaTool
from backend.tools.rag.xml_search import XMLSearchPabadaTool


class TestDOCXSearchTool:
    def test_docx_search_sandbox_validation(self, agent_context):
        """Path outside sandbox should return error."""
        tool = DOCXSearchPabadaTool()
        result = json.loads(tool._run(
            query="test",
            docx_path="/etc/secret.docx",
        ))
        assert "error" in result
        assert "Access denied" in result["error"]

    def test_docx_search_file_not_found(self, agent_context, sandbox_dir):
        tool = DOCXSearchPabadaTool()
        result = json.loads(tool._run(
            query="test",
            docx_path=os.path.join(sandbox_dir, "nonexistent.docx"),
        ))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_docx_search_wrong_extension(self, agent_context, sandbox_dir):
        # Create a non-docx file
        txt_path = os.path.join(sandbox_dir, "test.txt")
        with open(txt_path, "w") as f:
            f.write("not a docx")

        tool = DOCXSearchPabadaTool()
        result = json.loads(tool._run(query="test", docx_path=txt_path))
        assert "error" in result
        assert "Not a DOCX" in result["error"]

    @patch("backend.tools.rag.docx_search.build_crewai_tools_config")
    def test_docx_search_delegates_to_crewai(self, mock_config, agent_context, sandbox_dir):
        mock_config.return_value = {"embedder": {"provider": "openai", "config": {"model": "test"}}}

        docx_path = os.path.join(sandbox_dir, "test.docx")
        with open(docx_path, "wb") as f:
            f.write(b"fake docx content")

        mock_tool = MagicMock()
        mock_tool.run.return_value = "Found relevant section about testing"

        with patch("backend.tools.rag.docx_search.DOCXSearchTool", return_value=mock_tool):
            tool = DOCXSearchPabadaTool()
            result = json.loads(tool._run(query="testing", docx_path=docx_path))

        assert result["query"] == "testing"
        assert "Found relevant section" in result["result"]


class TestJSONSearchTool:
    def test_json_search_file_not_found(self, agent_context, sandbox_dir):
        tool = JSONSearchPabadaTool()
        result = json.loads(tool._run(
            query="test",
            json_path=os.path.join(sandbox_dir, "nonexistent.json"),
        ))
        assert "error" in result

    def test_json_search_wrong_extension(self, agent_context, sandbox_dir):
        txt_path = os.path.join(sandbox_dir, "test.txt")
        with open(txt_path, "w") as f:
            f.write("not json")

        tool = JSONSearchPabadaTool()
        result = json.loads(tool._run(query="test", json_path=txt_path))
        assert "error" in result
        assert "Not a JSON" in result["error"]

    @patch("backend.tools.rag.json_search.build_crewai_tools_config")
    def test_json_search_delegates(self, mock_config, agent_context, sandbox_dir):
        mock_config.return_value = {"embedder": {"provider": "openai", "config": {"model": "test"}}}

        json_path = os.path.join(sandbox_dir, "data.json")
        with open(json_path, "w") as f:
            f.write('{"key": "value"}')

        mock_tool = MagicMock()
        mock_tool.run.return_value = "Found key: value"

        with patch("backend.tools.rag.json_search.JSONSearchTool", return_value=mock_tool):
            tool = JSONSearchPabadaTool()
            result = json.loads(tool._run(query="key", json_path=json_path))

        assert result["query"] == "key"
        assert "Found key" in result["result"]


class TestXMLSearchTool:
    def test_xml_search_file_not_found(self, agent_context, sandbox_dir):
        tool = XMLSearchPabadaTool()
        result = json.loads(tool._run(
            query="test",
            xml_path=os.path.join(sandbox_dir, "nonexistent.xml"),
        ))
        assert "error" in result

    def test_xml_search_wrong_extension(self, agent_context, sandbox_dir):
        txt_path = os.path.join(sandbox_dir, "test.txt")
        with open(txt_path, "w") as f:
            f.write("not xml")

        tool = XMLSearchPabadaTool()
        result = json.loads(tool._run(query="test", xml_path=txt_path))
        assert "error" in result
        assert "Not an XML" in result["error"]

    @patch("backend.tools.rag.xml_search.build_crewai_tools_config")
    def test_xml_search_delegates(self, mock_config, agent_context, sandbox_dir):
        mock_config.return_value = {"embedder": {"provider": "openai", "config": {"model": "test"}}}

        xml_path = os.path.join(sandbox_dir, "config.xml")
        with open(xml_path, "w") as f:
            f.write("<root><item>data</item></root>")

        mock_tool = MagicMock()
        mock_tool.run.return_value = "Found item: data"

        with patch("backend.tools.rag.xml_search.XMLSearchTool", return_value=mock_tool):
            tool = XMLSearchPabadaTool()
            result = json.loads(tool._run(query="item", xml_path=xml_path))

        assert result["query"] == "item"
        assert "Found item" in result["result"]
