"""The default installation belongs to the selected native runtime; historical metadata libraries require explicit opt-in and cannot advertise an old provider backend."""

import re
import tomllib
from pathlib import Path

LEGACY_DISTRIBUTIONS = {
    'crewai','crewai-tools','litellm','ollama','chromadb','tree-sitter',
    'tree-sitter-python','tree-sitter-javascript','tree-sitter-typescript',
    'tree-sitter-c','tree-sitter-rust',
}
RETIRED_PARSERS = {name for name in LEGACY_DISTRIBUTIONS if name.startswith('tree-sitter')}


def dependency_names(requirements):
    """Compare declared distribution identities independently of unchanged version constraints or extras."""
    return {re.split(r'[<>=!~;\[ ]',value,1)[0].lower().replace('_','-') for value in requirements}


def test_default_dependencies_exclude_retired_provider_vector_and_parser_stacks():
    """A normal native install cannot pull the old execution stack through mandatory project requirements."""
    spec = tomllib.loads((Path(__file__).resolve().parents[3]/'pyproject.toml').read_text())['project']
    assert not LEGACY_DISTRIBUTIONS & dependency_names(spec['dependencies'])
    assert {'fastapi','mcp','onnxruntime','pypdf','textual'} <= dependency_names(spec['dependencies'])


def test_historical_metadata_is_explicit_and_old_backend_extras_are_not_advertised():
    """Optional metadata inspection is distinct from authorizing or configuring another production inference backend."""
    spec = tomllib.loads((Path(__file__).resolve().parents[3]/'pyproject.toml').read_text())['project']
    extras = spec['optional-dependencies']
    assert LEGACY_DISTRIBUTIONS - RETIRED_PARSERS == dependency_names(extras.get('legacy',[]))
    assert not RETIRED_PARSERS & dependency_names(extras.get('legacy',[]))
    assert not {'anthropic','gemini'} & set(extras)


def test_missing_historical_dependencies_explain_the_optional_reader_path(monkeypatch):
    """A core-only installation must reject an explicit legacy metadata request before partial tool/framework initialization."""
    from importlib.metadata import PackageNotFoundError

    import pytest

    from backend.tools._legacy_access import (
        LegacyMetadataUnavailable,
        require_legacy_extra,
    )

    def missing(_name):
        """Represent a core-only graph without importing a provider or modifying the running environment."""
        raise PackageNotFoundError(_name)

    monkeypatch.setattr('backend.tools._legacy_access.distribution',missing)
    with pytest.raises(LegacyMetadataUnavailable,match='legacy'):
        require_legacy_extra()
