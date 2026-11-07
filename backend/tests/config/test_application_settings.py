"""Verify retained host configuration without reviving the retired provider/loop settings store."""

import pytest
from pydantic import ValidationError

from backend.config.settings import Settings


@pytest.mark.parametrize("obsolete", ["LLM_MODEL", "EMBEDDING_PROVIDER", "LOOP_MAX_ITERATIONS", "AUTONOMY_ENABLED"])
def test_retired_options_are_not_accepted_as_application_settings(obsolete):
    """Reject direct configuration of a removed runtime instead of pretending it is still supported."""
    with pytest.raises(ValidationError, match=obsolete):
        Settings(**{obsolete: "1"})


def test_retained_services_use_explicit_environment_without_loading_old_json(tmp_path, monkeypatch):
    """Keep DB, web retrieval and owner Git defaults while preserving historical settings bytes untouched."""
    historical = tmp_path / ".researcher" / "settings.json"
    historical.parent.mkdir()
    original = b'{"LLM_MODEL":"old-provider/model","DB_PATH":"wrong.db"}\n'
    historical.write_bytes(original)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("INFINIBAY_DB", str(tmp_path / "chosen.db"))
    monkeypatch.setenv("INFINIBAY_WEB_TIMEOUT", "19")
    monkeypatch.setenv("INFINIBAY_WEB_RPM_LIMIT", "9")
    monkeypatch.setenv("INFINIBAY_RETRIEVAL_ASSET_DIR", str(tmp_path / "offline-assets"))
    monkeypatch.setenv("INFINIBAY_FORGEJO_OWNER", "fixture-owner")
    configured = Settings()
    assert configured.DB_PATH == str(tmp_path / "chosen.db")
    assert configured.WEB_TIMEOUT == 19
    assert configured.WEB_RPM_LIMIT == 9
    assert configured.RETRIEVAL_ASSET_DIR == str(tmp_path / "offline-assets")
    assert configured.FORGEJO_OWNER == "fixture-owner"
    assert historical.read_bytes() == original
    assert not (tmp_path / "chosen.db").exists()
