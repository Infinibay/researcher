"""Tests for KnowledgeService in backend/knowledge/service.py."""

from unittest.mock import patch, MagicMock

import pytest

from backend.config.settings import Settings
from backend.knowledge.service import KnowledgeService


class TestConfigureEmbedder:
    def test_configure_embedder_default(self):
        cfg = Settings(
            EMBEDDING_PROVIDER="openai",
            EMBEDDING_MODEL="text-embedding-3-small",
            EMBEDDING_BASE_URL=None,
        )
        result = KnowledgeService.configure_embedder(cfg)

        assert result["provider"] == "openai"
        assert "config" in result
        assert result["config"]["model"] == "text-embedding-3-small"
        assert "api_base" not in result["config"]

    def test_configure_embedder_with_base_url(self):
        cfg = Settings(
            EMBEDDING_PROVIDER="openai",
            EMBEDDING_MODEL="text-embedding-3-small",
            EMBEDDING_BASE_URL="http://localhost:11434",
        )
        result = KnowledgeService.configure_embedder(cfg)

        assert result["config"]["api_base"] == "http://localhost:11434"


class TestGetSourcesForProject:
    @patch("backend.knowledge.service.FindingsKnowledgeSource")
    @patch("backend.knowledge.service.WikiKnowledgeSource")
    @patch("backend.knowledge.service.ReferenceFilesKnowledgeSource")
    @patch("backend.knowledge.service.ReportsKnowledgeSource")
    def test_get_sources_for_project_returns_four(
        self, mock_reports, mock_ref, mock_wiki, mock_findings
    ):
        sources = KnowledgeService.get_sources_for_project(project_id=1)
        assert len(sources) == 4


class TestGetSourcesForRole:
    @patch("backend.knowledge.service.FindingsKnowledgeSource")
    @patch("backend.knowledge.service.WikiKnowledgeSource")
    @patch("backend.knowledge.service.ReferenceFilesKnowledgeSource")
    @patch("backend.knowledge.service.ReportsKnowledgeSource")
    def test_researcher_gets_four_sources(
        self, mock_reports, mock_ref, mock_wiki, mock_findings
    ):
        sources = KnowledgeService.get_sources_for_role("researcher", project_id=1)
        assert len(sources) == 4

    @patch("backend.knowledge.service.FindingsKnowledgeSource")
    @patch("backend.knowledge.service.WikiKnowledgeSource")
    @patch("backend.knowledge.service.ReferenceFilesKnowledgeSource")
    def test_developer_gets_two_sources(self, mock_ref, mock_wiki, mock_findings):
        sources = KnowledgeService.get_sources_for_role("developer", project_id=1)
        assert len(sources) == 2

    @patch("backend.knowledge.service.WikiKnowledgeSource")
    def test_code_reviewer_gets_one_source(self, mock_wiki):
        sources = KnowledgeService.get_sources_for_role("code_reviewer", project_id=1)
        assert len(sources) == 1

    @patch("backend.knowledge.service.WikiKnowledgeSource")
    def test_unknown_role_falls_back_to_wiki_only(self, mock_wiki, caplog):
        import logging

        with caplog.at_level(logging.WARNING, logger="backend.knowledge.service"):
            sources = KnowledgeService.get_sources_for_role("unknown_role", project_id=1)

        assert len(sources) == 1
        assert "No knowledge source mapping" in caplog.text
