"""Configuration helper for crewai_tools RAG-based tools.

Maps PABADA settings (embedding provider/model, LLM model) to the config
dict format that crewai_tools' RAG-based tools expect (CodeDocsSearchTool,
DOCXSearchTool, JSONSearchTool, XMLSearchTool, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.config.settings import settings

logger = logging.getLogger(__name__)

# Map PABADA embedding providers to crewai_tools provider names
_PROVIDER_MAP = {
    "openai": "openai",
    "ollama": "ollama",
    "google": "google",
    "azure": "azure_openai",
    "default": "openai",  # ChromaDB default uses local model, but crewai_tools needs a provider
}


def build_crewai_tools_config() -> dict[str, Any]:
    """Build a config dict for crewai_tools RAG-based tools.

    Returns a dict with ``embedder`` and optionally ``llm`` keys that
    crewai_tools tools accept as ``config`` parameter.
    """
    provider = _PROVIDER_MAP.get(settings.EMBEDDING_PROVIDER, "openai")

    embedder_config: dict[str, Any] = {
        "provider": provider,
        "config": {
            "model": settings.EMBEDDING_MODEL or "text-embedding-3-small",
        },
    }

    # Add base_url for providers that need it (Ollama, custom)
    if settings.EMBEDDING_BASE_URL:
        embedder_config["config"]["base_url"] = settings.EMBEDDING_BASE_URL

    config: dict[str, Any] = {
        "embedder": embedder_config,
    }

    # Add LLM config if available
    if settings.LLM_MODEL:
        llm_config: dict[str, Any] = {
            "provider": settings.LLM_MODEL.split("/")[0] if "/" in settings.LLM_MODEL else "openai",
            "config": {
                "model": settings.LLM_MODEL,
            },
        }
        if settings.LLM_API_KEY:
            llm_config["config"]["api_key"] = settings.LLM_API_KEY
        config["llm"] = llm_config

    return config
