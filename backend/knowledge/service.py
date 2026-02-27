"""KnowledgeService — provides role-appropriate knowledge sources for agents."""

from __future__ import annotations

import logging
from pathlib import Path
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
        """Build the embedder config dict expected by CrewAI's Agent.embedder.

        Returns a provider-specific dict matching CrewAI's typed specs, e.g.::

            {"provider": "ollama", "config": {"model_name": "nomic-embed-text", "url": "http://localhost:11434/api/embeddings"}}
            {"provider": "openai", "config": {"model": "text-embedding-3-small"}}
        """
        if cfg is None:
            cfg = settings

        provider = cfg.EMBEDDING_PROVIDER

        if provider == "ollama":
            base = cfg.EMBEDDING_BASE_URL or "http://localhost:11434"
            return {
                "provider": "ollama",
                "config": {
                    "model_name": cfg.EMBEDDING_MODEL,
                    "url": f"{base.rstrip('/')}/api/embeddings",
                },
            }

        if provider == "default":
            return {
                "provider": "huggingface",
                "config": {"model": "all-MiniLM-L6-v2"},
            }

        # openai / azure / google — pass through
        config: dict[str, Any] = {"model": cfg.EMBEDDING_MODEL}
        if cfg.EMBEDDING_BASE_URL:
            config["api_base"] = cfg.EMBEDDING_BASE_URL

        return {
            "provider": provider,
            "config": config,
        }

    @staticmethod
    def build_crew_memory_kwargs() -> dict[str, Any]:
        """Return kwargs for ``Crew(...)`` to enable/disable CrewAI native memory.

        When enabled, builds a ``crewai.Memory`` instance with the project
        LLM and embedder, as per CrewAI docs (Option 2).

        When disabled, returns ``{"memory": False}``.
        """
        if not settings.MEMORY_ENABLED:
            return {"memory": False}

        from crewai import Memory
        from backend.config.llm import get_llm

        _patch_telemetry_memory_attribute()

        # Store LanceDB alongside the rest of PABADA data in .data/
        memory_path = str(
            Path(settings.DB_PATH).resolve().parent / "memory"
        )

        memory = Memory(
            llm=get_llm(),
            storage=memory_path,
            embedder=KnowledgeService.configure_embedder(),
            # Composite scoring weights (must sum to 1.0)
            semantic_weight=0.5,
            recency_weight=0.3,
            importance_weight=0.2,
            recency_half_life_days=14,
            # Recall thresholds
            confidence_threshold_high=0.8,
            confidence_threshold_low=settings.MEMORY_SCORE_THRESHOLD,
        )
        return {"memory": memory}

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


# ---------------------------------------------------------------------------
# CrewAI telemetry bug workaround
# ---------------------------------------------------------------------------
# crewai 1.10.0a1 telemetry.py line 276 does:
#     span.set_attribute("crew_memory", crew.memory)
# When crew.memory is a Memory instance, OTel rejects it (primitives only).
# We patch _add_attribute to coerce Memory objects to bool.

_telemetry_patched = False


def _patch_telemetry_memory_attribute() -> None:
    global _telemetry_patched
    if _telemetry_patched:
        return
    _telemetry_patched = True

    try:
        from crewai.telemetry.telemetry import Telemetry

        _orig = Telemetry._add_attribute

        def _safe_add_attribute(self, span, key, value):
            if key == "crew_memory" and not isinstance(
                value, (bool, str, bytes, int, float, type(None))
            ):
                value = bool(value)
            return _orig(self, span, key, value)

        Telemetry._add_attribute = _safe_add_attribute
    except Exception:
        pass  # telemetry is optional, don't crash
