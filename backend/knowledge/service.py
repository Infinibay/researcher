"""KnowledgeService — provides role-appropriate knowledge sources for agents."""

from __future__ import annotations

import logging
from typing import Any

from crewai.knowledge.source.base_knowledge_source import BaseKnowledgeSource

from backend.config.settings import Settings, settings
from backend.knowledge.sources import (
    FindingsKnowledgeSource,
    ReferenceFilesKnowledgeSource,
    ReportsKnowledgeSource,
    WikiKnowledgeSource,
)

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Manages CrewAI knowledge sources scoped to projects and roles."""

    @staticmethod
    def configure_embedder(cfg: Settings | None = None) -> dict[str, Any]:
        """Build the embedder config dict expected by CrewAI's knowledge system.

        Returns a dict like::

            {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                }
            }
        """
        if cfg is None:
            cfg = settings

        config: dict[str, Any] = {"model": cfg.EMBEDDING_MODEL}
        if cfg.EMBEDDING_BASE_URL:
            config["api_base"] = cfg.EMBEDDING_BASE_URL

        return {
            "provider": cfg.EMBEDDING_PROVIDER,
            "config": config,
        }

    @staticmethod
    def get_sources_for_project(project_id: int) -> list[BaseKnowledgeSource]:
        """Return all four knowledge sources scoped to *project_id*."""
        return [
            FindingsKnowledgeSource(project_id=project_id),
            WikiKnowledgeSource(project_id=project_id),
            ReferenceFilesKnowledgeSource(project_id=project_id),
            ReportsKnowledgeSource(project_id=project_id),
        ]

    @staticmethod
    def get_sources_for_role(
        role: str, project_id: int
    ) -> list[BaseKnowledgeSource]:
        """Return role-appropriate knowledge sources.

        Role mapping:

        ============== =============================================
        Role           Sources
        ============== =============================================
        researcher     All 4 sources
        research_rev.  Findings (min_conf=0.0), Wiki, Reports
        team_lead      Wiki, Findings (active, min_conf=0.6)
        project_lead   Wiki, Findings (active, min_conf=0.7)
        developer      Wiki, ReferenceFiles
        code_reviewer   Wiki
        ============== =============================================
        """
        role_sources: dict[str, list[BaseKnowledgeSource]] = {
            "researcher": [
                FindingsKnowledgeSource(project_id=project_id),
                WikiKnowledgeSource(project_id=project_id),
                ReferenceFilesKnowledgeSource(project_id=project_id),
                ReportsKnowledgeSource(project_id=project_id),
            ],
            "research_reviewer": [
                FindingsKnowledgeSource(
                    project_id=project_id, min_confidence=0.0,
                ),
                WikiKnowledgeSource(project_id=project_id),
                ReportsKnowledgeSource(project_id=project_id),
            ],
            "team_lead": [
                WikiKnowledgeSource(project_id=project_id),
                FindingsKnowledgeSource(
                    project_id=project_id,
                    status_filter="active",
                    min_confidence=0.6,
                ),
            ],
            "project_lead": [
                WikiKnowledgeSource(project_id=project_id),
                FindingsKnowledgeSource(
                    project_id=project_id,
                    status_filter="active",
                    min_confidence=0.7,
                ),
            ],
            "developer": [
                WikiKnowledgeSource(project_id=project_id),
                ReferenceFilesKnowledgeSource(project_id=project_id),
            ],
            "code_reviewer": [
                WikiKnowledgeSource(project_id=project_id),
            ],
        }

        sources = role_sources.get(role)
        if sources is None:
            logger.warning(
                "No knowledge source mapping for role '%s', returning wiki only",
                role,
            )
            return [WikiKnowledgeSource(project_id=project_id)]

        return sources
