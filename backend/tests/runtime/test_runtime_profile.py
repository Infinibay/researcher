"""Reject implicit or retired launchers before accessing host execution resources."""

import json

import pytest

from backend.api.runtime_dependencies import configured_runtime


@pytest.mark.parametrize("profile", [None, "legacy-codex", "unknown", "", 1])
def test_unsupported_profile_cannot_fall_back(tmp_path, monkeypatch, profile):
    """Old and malformed profiles fail before database, credentials or workers open."""
    path = tmp_path / "runtime.json"
    config = {} if profile is None else {"runtime_profile": profile}
    path.write_text(json.dumps(config))
    monkeypatch.setenv("INFINIBAY_RUNTIME_CONFIG", str(path))
    before = {item: item.read_bytes() for item in tmp_path.iterdir()}
    with pytest.raises(ValueError, match="explicit runtime_profile='owned-codex-v1'"):
        configured_runtime(object())
    assert {item: item.read_bytes() for item in tmp_path.iterdir()} == before


@pytest.mark.parametrize("config", [None, [], "owned-codex-v1", 42])
def test_runtime_configuration_requires_an_object(tmp_path, monkeypatch, config):
    """Invalid JSON shapes receive an actionable error before profile composition."""
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(config))
    monkeypatch.setenv("INFINIBAY_RUNTIME_CONFIG", str(path))
    with pytest.raises(ValueError, match="JSON object"):
        configured_runtime(object())


def test_unconfigured_product_keeps_readonly_access(monkeypatch):
    """Absence of runtime configuration leaves inspection available without fallback."""
    monkeypatch.delenv("INFINIBAY_RUNTIME_CONFIG", raising=False)
    assert configured_runtime(object()) is None
