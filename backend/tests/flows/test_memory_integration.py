"""Tests for CrewAI native memory configuration.

Uses importlib to load KnowledgeService directly, avoiding the circular
import chain through backend.tools.__init__.
"""

import importlib
import sys
from unittest.mock import patch, MagicMock


def _load_knowledge_service():
    """Load KnowledgeService bypassing circular imports."""
    if "backend.knowledge.service" in sys.modules:
        return sys.modules["backend.knowledge.service"].KnowledgeService

    import backend.config.settings  # noqa: F401

    mock_sources = MagicMock()
    with patch.dict(sys.modules, {"backend.knowledge.sources": mock_sources}):
        mod = importlib.import_module("backend.knowledge.service")
    return mod.KnowledgeService


class TestMemoryConfiguration:
    def test_build_crew_memory_kwargs_disabled(self):
        KnowledgeService = _load_knowledge_service()
        with patch("backend.knowledge.service.settings") as mock:
            mock.MEMORY_ENABLED = False
            result = KnowledgeService.build_crew_memory_kwargs()
            assert result == {"memory": False}

    def test_build_crew_memory_kwargs_returns_memory_instance(self):
        KnowledgeService = _load_knowledge_service()
        with patch("backend.knowledge.service.settings") as mock:
            mock.MEMORY_ENABLED = True
            mock.MEMORY_SCORE_THRESHOLD = 0.35
            mock.EMBEDDING_PROVIDER = "default"
            mock.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
            mock.EMBEDDING_BASE_URL = ""
            result = KnowledgeService.build_crew_memory_kwargs()
            assert "memory" in result
            # Must be a Memory instance, not a boolean
            assert result["memory"] is not True
            assert result["memory"] is not False

            from crewai import Memory
            assert isinstance(result["memory"], Memory)

    def test_build_crew_memory_kwargs_openai_embedder(self):
        KnowledgeService = _load_knowledge_service()
        with patch("backend.knowledge.service.settings") as mock:
            mock.MEMORY_ENABLED = True
            mock.MEMORY_SCORE_THRESHOLD = 0.35
            mock.EMBEDDING_PROVIDER = "openai"
            mock.EMBEDDING_MODEL = "text-embedding-3-small"
            mock.EMBEDDING_BASE_URL = None
            result = KnowledgeService.build_crew_memory_kwargs()

            from crewai import Memory
            assert isinstance(result["memory"], Memory)

    def test_build_crew_memory_kwargs_ollama_embedder(self):
        KnowledgeService = _load_knowledge_service()
        with patch("backend.knowledge.service.settings") as mock:
            mock.MEMORY_ENABLED = True
            mock.MEMORY_SCORE_THRESHOLD = 0.35
            mock.EMBEDDING_PROVIDER = "ollama"
            mock.EMBEDDING_MODEL = "nomic-embed-text"
            mock.EMBEDDING_BASE_URL = "http://localhost:11434"
            result = KnowledgeService.build_crew_memory_kwargs()

            from crewai import Memory
            assert isinstance(result["memory"], Memory)

    def test_build_crew_memory_kwargs_respects_score_threshold(self):
        KnowledgeService = _load_knowledge_service()
        with patch("backend.knowledge.service.settings") as mock:
            mock.MEMORY_ENABLED = True
            mock.MEMORY_SCORE_THRESHOLD = 0.5
            mock.EMBEDDING_PROVIDER = "default"
            mock.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
            mock.EMBEDDING_BASE_URL = ""
            result = KnowledgeService.build_crew_memory_kwargs()

            from crewai import Memory
            mem = result["memory"]
            assert isinstance(mem, Memory)
