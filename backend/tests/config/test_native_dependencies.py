"""Declared, locked and exported installations use the native runtime without retired provider/vector/parser stacks or a hidden legacy extra."""

import re
import tomllib
from pathlib import Path

LEGACY_DISTRIBUTIONS = {
    'crewai','crewai-tools','litellm','ollama','chromadb','tree-sitter',
    'tree-sitter-python','tree-sitter-javascript','tree-sitter-typescript',
    'tree-sitter-c','tree-sitter-rust',
}


def dependency_names(requirements):
    """Compare declared distribution identities independently of unchanged version constraints or extras."""
    return {re.split(r'[<>=!~;\[ ]',value,1)[0].lower().replace('_','-') for value in requirements}


def test_default_dependencies_exclude_retired_provider_vector_and_parser_stacks():
    """A normal native install cannot pull the old execution stack through mandatory project requirements."""
    spec = tomllib.loads((Path(__file__).resolve().parents[3]/'pyproject.toml').read_text())['project']
    assert not LEGACY_DISTRIBUTIONS & dependency_names(spec['dependencies'])
    assert {'fastapi','mcp','onnxruntime','pypdf','textual'} <= dependency_names(spec['dependencies'])


def test_extras_lock_and_export_cannot_reintroduce_retired_stacks():
    """Removal covers optional and transitive packaging routes, not only the default requirement list."""
    root = Path(__file__).resolve().parents[3]
    spec = tomllib.loads((root/'pyproject.toml').read_text())['project']
    extras = spec.get('optional-dependencies', {})
    assert not {'legacy','anthropic','gemini'} & set(extras)
    for requirements in extras.values():
        assert not LEGACY_DISTRIBUTIONS & dependency_names(requirements)
    locked = {package['name'] for package in tomllib.loads((root/'uv.lock').read_text())['package']}
    assert not LEGACY_DISTRIBUTIONS & locked
    exported = [line.strip().removesuffix('\\').strip() for line in (root/'requirements.txt').read_text().splitlines() if line.strip() and not line.lstrip().startswith(('#','--'))]
    assert not LEGACY_DISTRIBUTIONS & dependency_names(exported)


def test_shared_database_context_exports_do_not_load_a_framework_tool_base():
    """Native utilities remain importable while the retired lazy class export is unavailable."""
    from backend.tools import base

    assert callable(base.get_connection) and callable(base.set_context)
    assert 'InfinibayBaseTool' not in base.__all__
    assert not hasattr(base, 'InfinibayBaseTool')
