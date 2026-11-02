"""Knowledge entry points without importing legacy model integrations for native wiki use.

CrewAI-backed sources remain available only when explicitly requested by a legacy
consumer. Importing the maintained wiki records must not load a model stack or loop.
"""

from importlib import import_module

__all__ = [
    "FindingsKnowledgeSource",
    "KnowledgeService",
    "ReferenceFilesKnowledgeSource",
    "ReportsKnowledgeSource",
    "WikiKnowledgeSource",
]


def __getattr__(name):
    """Resolve the existing legacy API lazily, preserving class identity and import compatibility."""
    if name not in __all__:
        raise AttributeError(name)
    module = (
        "backend.knowledge.service"
        if name == "KnowledgeService"
        else "backend.knowledge.sources"
    )
    value = getattr(import_module(module), name)
    globals()[name] = value
    return value
