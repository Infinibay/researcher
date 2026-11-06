"""Retired framework adapters cannot reintroduce command owners, generic SQL or hidden document-model calls."""

import importlib.machinery
import importlib.util
from pathlib import Path

import backend


def test_replaced_framework_adapters_are_unavailable():
    """Check installed import locations without loading retired frameworks or web packages."""
    for module in (
        'backend.tools.shell', 'backend.tools.git',
        'backend.tools.rag', 'backend.tools.data', 'backend.tools.web', 'backend.tools.task',
        'backend.tools.communication', 'backend.tools.project', 'backend.tools.knowledge', 'backend.communication.question_registry',
        'backend.communication.response_event_registry',
    ):
        assert importlib.util.find_spec(module) is None, module
    web = Path(backend.__file__).parent / 'tools' / 'web'
    for module in ('code_docs_search', 'crewai_tool_config'):
        assert importlib.machinery.PathFinder.find_spec(module, [str(web)]) is None
