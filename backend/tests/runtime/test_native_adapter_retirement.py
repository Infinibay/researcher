"""Retired framework adapters cannot reintroduce command owners, generic SQL or hidden document-model calls."""

import importlib.machinery
import importlib.util
from pathlib import Path

import backend


def test_replaced_command_git_document_and_sql_adapters_are_unavailable():
    """Check installed import locations without importing still-pending historical web tools or requiring their optional frameworks."""
    for module in (
        'backend.tools.shell', 'backend.tools.git',
        'backend.tools.rag', 'backend.tools.data',
    ):
        assert importlib.util.find_spec(module) is None, module
    web = Path(backend.__file__).parent / 'tools' / 'web'
    for module in ('code_docs_search', 'crewai_tool_config'):
        assert importlib.machinery.PathFinder.find_spec(module, [str(web)]) is None
